import json, backoff, time
from typing import Dict, Any, List
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from distiller.utils.file_utils import clean_json_response
from distiller.schemas.extraction_passes import AgentPropertyPass, AgentsPass, ExperimentPass, FormulationPass
from anthropic import Anthropic
from jinja2 import Environment, FileSystemLoader
_jinja = Environment(loader=FileSystemLoader("source/prompts"))
import os

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
claude_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def _llm_extract(
    prompt: str,
    schema_model: type[BaseModel],
    model: str = "claude-sonnet-4-20250514",
    max_retries: int = 3,
) -> dict | None:
    """Generic: send prompt, coerce to schema, retry with validator feedback."""
    messages: List[Dict[str, str]] = [{"role": "user", "content": prompt}]
    @backoff.on_exception(backoff.expo, Exception, max_tries=max_retries)
    def _call(messages):
        if model == "gpt-4.1-mini":
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
        elif model == "claude-sonnet-4-20250514":
            print("[TRACE] Sending prompt to Claude with streaming...")
            
            # Use streaming for large responses
            full_content = ""
            with claude_client.messages.stream(
                model=model,
                messages=messages,
                max_tokens=64000,
                temperature=0,
            ) as stream:
                for text in stream.text_stream:
                    full_content += text

            # Wrap response to mimic OpenAI's interface
            class _Msg:
                def __init__(self, content):
                    self.content = content
            class _Choice:
                def __init__(self, content):
                    self.message = _Msg(content)
            class _Wrapper:
                def __init__(self, content):
                    self.choices = [_Choice(content)]
            
            return _Wrapper(full_content)
        else:
            raise ValueError(f"Unsupported model: {model}")
    for attempt in range(1, max_retries + 1):
        raw = _call(messages).choices[0].message.content
        text = raw if isinstance(raw, str) else json.dumps(raw)
        text = clean_json_response(text) if "clean_json_response" in globals() else text

        try:
            data = json.loads(text)
            parsed = schema_model.model_validate(data)     # <- strict validation
            return json.loads(parsed.model_dump_json(by_alias=True))
        except (json.JSONDecodeError, ValidationError) as err:
            if attempt == max_retries:
                print(f"[ERROR] LLM output invalid after {max_retries} tries: {err}")
                return None
            # feed validator errors back to the model
            messages += [
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": (
                        "The JSON did not pass validation:\n"
                        f"{err}\n"
                        "Please correct it and return ONLY the JSON object."
                    ),
                },
            ]
def extract_agents(paper_text: str, llm_model: str) -> list[dict] | None:
    prompt = _jinja.get_template("agent_prompt.j2").render(
        PAPER_TEXT=paper_text, SCHEMA=AgentsPass.model_json_schema()
    )
    return _llm_extract(prompt, AgentsPass, model=llm_model)

def extract_experiments(paper_text: str, llm_model: str) -> list[dict] | None:
    """Run a single ExperimentPass over the full paper."""
    prompt = _jinja.get_template("experiment_extraction/v4_experiment_prompt.j2").render(
        PAPER_TEXT=paper_text,
        SCHEMA=ExperimentPass.model_json_schema(),
    )
    parsed = _llm_extract(prompt, ExperimentPass, model=llm_model)
    return parsed["experiments"] if parsed else None

def extract_agent_properties(paper_text: str, llm_model: str) -> list[dict] | None:
    prompt = _jinja.get_template("molecule_extraction/v2_agent_property_prompt.j2").render(
        PAPER_TEXT=paper_text,
        SCHEMA=AgentPropertyPass.model_json_schema(),
    )
    parsed = _llm_extract(prompt, AgentPropertyPass, model=llm_model)
    return parsed["properties"] if parsed else None

def extract_formulations(paper_text: str, experiments: list[dict], llm_model: str) -> list[dict]:
    all_forms: list[dict] = []

    for exp in experiments:
        prompt = _jinja.get_template("formulation_extraction/v5_formulation_prompt.j2").render(
            PAPER_TEXT = paper_text,            # single prompt per exp
            EXPERIMENT_ID = exp["id"],
            SCHEMA = FormulationPass.model_json_schema(),
        )
        parsed = _llm_extract(prompt, FormulationPass, model=llm_model)
        if not parsed:
            continue

        for form in parsed["formulations"]:
            form["experiment_id"] = exp["id"]      #  ← restore link

        all_forms.extend(parsed["formulations"])

    return all_forms
