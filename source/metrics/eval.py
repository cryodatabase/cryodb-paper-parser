"""
Multi-provider RAGAS evaluator supporting both Anthropic and OpenAI models
"""
import os
import sys
import json
import asyncio
from typing import Dict, Any
from pydantic import ValidationError
from source.distiller.schemas.playground_config import PlaygroundConfig
from jinja2 import Environment, FileSystemLoader

_jinja = Environment(loader=FileSystemLoader("source/prompts"))


def get_playground_config() -> PlaygroundConfig:
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            raw_config = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError("config.json file not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")

    try:
        config = PlaygroundConfig(**raw_config)
        config.validate_models()
        return config
    except ValidationError as e:
        raise ValueError(f"Configuration validation error:\n{e}")


def get_llm_for_model(model_id: str):
    if any(provider in model_id.lower() for provider in ['claude', 'anthropic']):
        from langchain_anthropic import ChatAnthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return ChatAnthropic(model=model_id, temperature=0, timeout=30.0)

    elif any(provider in model_id.lower() for provider in ['gpt', 'openai']):
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        return ChatOpenAI(model=model_id, temperature=0, timeout=30.0)

    else:
        raise ValueError(f"Unsupported model ID: {model_id}")


def extract_text(data: Any) -> str: # TODO Improve this
    """Extract text from common fields in a dictionary"""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for field in ['text', 'content', 'response', 'reference', 'answer']:
            if field in data and isinstance(data[field], str):
                return data[field]
    return str(data)


async def evaluate_factual_correctness(llm, reference_text: str, response_text: str) -> Dict[str, float]:
    """Use the given LLM to evaluate factual correctness"""
    prompt = _jinja.get_template("evaluation.j2").render(
        REF_TEXT=reference_text, RES_TEXT=response_text
    )

    try:
        response = await llm.ainvoke(prompt)
        result = json.loads(response.content.strip())

        for key in ['f1', 'precision', 'recall']:
            if key not in result:
                result[key] = 0.0
            result[key] = max(0.0, min(1.0, float(result[key])))

        return result

    except Exception as e:
        print(f"Error in evaluation: {e}", file=sys.stderr)
        return {"f1": 0.5, "precision": 0.5, "recall": 0.5}


async def run_playground_pipeline(md5_hash: str, response_data: Any):
    config = get_playground_config()

    if not config.playground_enabled:
        print("Playground evaluation is disabled.")
        return
    
    # TODO Implement mistral and llama parse text extraction

    try:
        with open(f"{md5_hash}.json", "r", encoding="utf-8") as f:
            reference_data = json.load(f)
    except FileNotFoundError:
        print(f"Reference file {md5_hash}.json not found.", file=sys.stderr)
        return

    reference_text = extract_text(reference_data)
    response_text = extract_text(response_data)

    for model_id in config.evaluation_models:
        llm = get_llm_for_model(model_id)
        result = await evaluate_factual_correctness(llm, reference_text, response_text)
        print(f"Model: {model_id}") 
        print(json.dumps(result)) # TODO Make this dump all the json from one paper into a single file 


def main():
    if len(sys.argv) != 3:
        print(json.dumps({"error": "Usage: python eval.py <md5_hash> <response_file>"}))
        sys.exit(1)

    md5_hash = sys.argv[1]
    response_path = sys.argv[2]

    try:
        with open(response_path, 'r') as f:
            response_data = json.load(f)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_playground_pipeline(md5_hash, response_data))
        finally:
            loop.close()

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
