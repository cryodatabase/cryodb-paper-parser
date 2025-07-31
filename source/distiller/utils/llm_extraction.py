import json, backoff, time
from typing import Dict, Any, List
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from distiller.utils.file_utils import clean_json_response
from distiller.schemas.extraction_passes import AgentPropertyPass, AgentsPass, ExperimentPass, FormulationPass
from jinja2 import Environment, FileSystemLoader
_jinja = Environment(loader=FileSystemLoader("source/prompts"))
import os

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def _llm_extract(
    prompt: str,
    schema_model: type[BaseModel],
    model: str =    "gpt-4o-mini",
    max_retries: int = 3,
) -> dict | None:
    """Generic: send prompt, coerce to schema, retry with validator feedback."""
    messages: List[Dict[str, str]] = [{"role": "user", "content": prompt}]

    @backoff.on_exception(backoff.expo, Exception, max_tries=max_retries)
    def _call(messages):
        return client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )

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
def extract_agents(paper_text: str) -> list[dict] | None:
    prompt = _jinja.get_template("agent_prompt.j2").render(
        PAPER_TEXT=paper_text, SCHEMA=AgentsPass.model_json_schema()
    )
    return _llm_extract(prompt, AgentsPass)

def extract_experiments(paper_text: str) -> list[dict] | None:
    """Run a single ExperimentPass over the full paper."""
    prompt = _jinja.get_template("experiment_extraction/v4_experiment_prompt.j2").render(
        PAPER_TEXT=paper_text,
        SCHEMA=ExperimentPass.model_json_schema(),
    )
    parsed = _llm_extract(prompt, ExperimentPass)
    return parsed["experiments"] if parsed else None

def extract_agent_properties(paper_text: str) -> list[dict] | None:
    prompt = _jinja.get_template("agent_property_prompt.j2").render(
        PAPER_TEXT=paper_text,
        SCHEMA=AgentPropertyPass.model_json_schema(),
    )
    parsed = _llm_extract(prompt, AgentPropertyPass)
    return parsed["properties"] if parsed else None

def extract_formulations(paper_text: str, experiments: list[dict]) -> list[dict]:
    all_forms: list[dict] = []

    for exp in experiments:
        prompt = _jinja.get_template("formulation_extraction/v5_formulation_prompt.j2").render(
            PAPER_TEXT = paper_text,            # single prompt per exp
            EXPERIMENT_ID = exp["id"],
            SCHEMA = FormulationPass.model_json_schema(),
        )
        parsed = _llm_extract(prompt, FormulationPass)
        if not parsed:
            continue

        for form in parsed["formulations"]:
            form["experiment_id"] = exp["id"]      #  ← restore link

        all_forms.extend(parsed["formulations"])

    return all_forms
