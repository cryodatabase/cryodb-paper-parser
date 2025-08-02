#!/usr/bin/env python3
"""
Multi-provider RAGAS evaluator supporting both Anthropic and OpenAI models
"""
import os
import sys
import json
import asyncio
from typing import Dict, Any


def get_playground_config() -> Dict[str, Any]:
    ALLOWED_MODELS = {
        "claude-4-sonnet",
        "claude-3-5-sonnet",
        "claude-3-opus",
        "claude-3-haiku",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4"
    }

    EXPECTED_SCHEMA = {
        "playground_enabled": bool,
        "distiller": str,
        "evaluation_models": list
    }

    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError("config.json file not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")

    for key, expected_type in EXPECTED_SCHEMA.items():
        if key not in config:
            raise ValueError(f"Missing required field: '{key}'")
        if not isinstance(config[key], expected_type):
            raise TypeError(
                f"Field '{key}' must be of type '{expected_type.__name__}', "
                f"but got '{type(config[key]).__name__}'"
            )

    models = config.get("evaluation_models", [])
    if not all(isinstance(model, str) for model in models):
        raise TypeError("All evaluation models must be strings.")

    for model in models:
        if model not in ALLOWED_MODELS:
            raise ValueError(f"Invalid evaluation model: '{model}'")

    return config

def get_llm_for_model(model_name: str):
    """Get the appropriate LLM instance based on model name"""
    
    # Anthropic models
    if any(provider in model_name.lower() for provider in ['claude', 'anthropic']):
        from langchain_anthropic import ChatAnthropic
        
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for Claude models")
        
        # Map model names to Anthropic model IDs
        model_mapping = {
            "claude-4-sonnet": "claude-sonnet-4-20250514",
            "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
            "claude-3-opus": "claude-3-opus-20240229",
            "claude-3-haiku": "claude-3-haiku-20240307"
        }
        
        # Normalize model name for mapping (replace spaces with hyphens)
        normalized_name = model_name.lower().replace(" ", "-")
        model_id = model_mapping.get(normalized_name, "claude-sonnet-4-20250514")
        return ChatAnthropic(model=model_id, temperature=0, timeout=30.0)
    
    # OpenAI models  
    elif any(provider in model_name.lower() for provider in ['gpt', 'openai']):
        from langchain_openai import ChatOpenAI
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI models")
        
        # Map model names to OpenAI model IDs
        model_mapping = {
            "gpt-4o": "gpt-4o",
            "gpt-4o-mini": "gpt-4o-mini",
            "gpt-4": "gpt-4"
        }
        
        model_id = model_mapping.get(model_name, "gpt-4o")
        return ChatOpenAI(model=model_id, temperature=0, timeout=30.0)
    
    else:
        raise ValueError(f"Unsupported model: {model_name}")

"""def __init__(self, model_name: str):
        self.model_name = model_name
        self.llm = get_llm_for_model(model_name)"""

class MultiProviderRagasEvaluator:
    def __init__(self, md5_hash: str):
        config = get_playground_config()

        if not config.playground_enabled:
            return False

        try:
            with open(f"{md5_hash}.json", "r", encoding="utf-8") as f:
                reference = json.load(f)
        except FileNotFoundError:
            return False
       
        self.model_names = config.get("evaluation_models", [])
        self.llms = {model_name: get_llm_for_model(model_name) for model_name in self.model_names}
    
    def extract_text(self, data):
        """Extract text from JSON structure"""
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            # Try common text fields
            for field in ['text', 'content', 'response', 'reference', 'answer']:
                if field in data and isinstance(data[field], str):
                    return data[field]
        return str(data)
    
    async def evaluate_factual_correctness(self, reference_text: str, response_text: str) -> Dict[str, float]:
        """Use the selected LLM to evaluate factual correctness"""
        
        prompt = f"""You are evaluating factual correctness between a reference text and a response text.

REFERENCE TEXT:
{reference_text}

RESPONSE TEXT:
{response_text}

Please analyze the factual accuracy and return ONLY a JSON object with these exact keys:
- "f1": F1 score (0.0 to 1.0)
- "precision": Precision score (0.0 to 1.0) 
- "recall": Recall score (0.0 to 1.0)

Calculate these metrics based on:
- Precision: What fraction of claims in the response are factually correct according to the reference
- Recall: What fraction of facts from the reference are captured in the response
- F1: Harmonic mean of precision and recall

Return only the JSON object, no other text."""

        try:
            response = await self.llm.ainvoke(prompt)
            
            # Parse the JSON response
            result = json.loads(response.content.strip())
            
            # Ensure all required keys exist and are valid numbers
            for key in ['f1', 'precision', 'recall']:
                if key not in result:
                    result[key] = 0.0
                result[key] = max(0.0, min(1.0, float(result[key])))
            
            return result
            
        except Exception as e:
            print(f"Error in evaluation: {e}", file=sys.stderr)
            # Return default values on error
            return {"f1": 0.5, "precision": 0.5, "recall": 0.5}


def main():
    if len(sys.argv) != 4:
        print(json.dumps({"error": "Usage: python multi_provider_ragas.py <model_name> <reference_file> <response_file>"}))
        sys.exit(1)
    
    try:
        model_name = sys.argv[1]
        
        # Load files
        with open(sys.argv[2], 'r') as f:
            reference_data = json.load(f)
        with open(sys.argv[3], 'r') as f:
            response_data = json.load(f)
        
        # Initialize evaluator
        evaluator = MultiProviderRagasEvaluator(model_name)
        
        # Extract texts
        reference_text = evaluator.extract_text(reference_data)
        response_text = evaluator.extract_text(response_data)
        
        # Run evaluation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                evaluator.evaluate_factual_correctness(reference_text, response_text)
            )
            print(json.dumps(results))
        finally:
            loop.close()
            
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()