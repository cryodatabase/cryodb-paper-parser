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
from distiller.schemas.pipeline_config import PipelineConfig
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
claude_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

from deepeval.prompt import Prompt

with open('config.json', 'r') as f:
    json_str = f.read()
config = PipelineConfig.model_validate_json(json_str)

backoff.on_exception(backoff.expo, Exception, max_tries=3)
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
        if model == "gpt-5-2025-08-07":
            return client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
            )
        elif model == "gpt-4.1-mini":
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

def extract_experiments(paper_text: str, llm_model: str, prompt_to_llm: str | None = None) -> list[dict] | None:
    """Run a single ExperimentPass over the full paper."""
    if prompt_to_llm:
        prompt = prompt_to_llm
    else:
        prompt_experiments = Prompt(alias="experiments_extraction")
        prompt_experiments.pull()
        experiments_prompt_interpolate = prompt_experiments.interpolate(
            SCHEMA=ExperimentPass.model_json_schema(),
            PAPER_TEXT=paper_text
        )
        prompt = experiments_prompt_interpolate
        #prompt = _jinja.get_template(f"{config.version}/experiment_extraction/experiment_prompt.j2").render(
        #    PAPER_TEXT=paper_text,
        #    SCHEMA=ExperimentPass.model_json_schema(),
        #)
    
    parsed = _llm_extract(prompt, ExperimentPass, model=llm_model)
    return parsed["experiments"] if parsed else None

def extract_agent_properties(paper_text: str, llm_model: str) -> list[dict] | None:
    prompt = _jinja.get_template(f"{config.version}/molecule_extraction/agent_property_prompt.j2").render(
        PAPER_TEXT=paper_text,
        SCHEMA=AgentPropertyPass.model_json_schema(),
    )
    parsed = _llm_extract(prompt, AgentPropertyPass, model=llm_model)
    return parsed["properties"] if parsed else None

def extract_formulations(paper_text: str, experiments: list[dict], llm_model: str) -> list[dict]:
    all_forms: list[dict] = []

    print("EXPERIMENTS: ", experiments)
    for exp in experiments:
        prompt = _jinja.get_template(f"{config.version}/formulation_extraction/formulation_prompt.j2").render(
            PAPER_TEXT = paper_text,            # single prompt per exp
            EXPERIMENT_ID = exp["id"],
            SCHEMA = FormulationPass.model_json_schema(),
        )
        print(f'SCHEMA FORMULATIONS: {FormulationPass.model_json_schema()}')
        parsed = _llm_extract(prompt, FormulationPass, model=llm_model)
        if not parsed:
            continue

        for form in parsed["formulations"]:
            form["experiment_id"] = exp["id"]      #  ← restore link

        all_forms.extend(parsed["formulations"])

    return all_forms


def extract_formulations_all_experiments(
    paper_text: str,
    experiments: list[dict],
    llm_model: str,
    prompt_to_llm: str | None = None,
) -> list[dict]:
    """Single-pass formulation extraction for all experiments.

    This variant avoids the O(n) loop over individual experiments by sending one
    prompt that lists every experiment ID. The LLM must include the appropriate
    `experiment_id` on each formulation it returns. The `FormulationPass` schema
    is enforced exactly as in `extract_formulations`.
    """
    if prompt_to_llm:
        prompt = prompt_to_llm
    else:
        print("EXPERIMENTS: ", experiments)
        prompt_formulations = Prompt(alias="formulations_extraction")
        prompt_formulations.pull()
        prompt_formulations_interpolate = prompt_formulations.interpolate(
            SCHEMA=FormulationPass.model_json_schema(),
            PAPER_TEXT=paper_text,
            EXPERIMENTS=experiments,
        )
        prompt = prompt_formulations_interpolate
       # prompt = _jinja.get_template(
       #     f"{config.version}/formulation_extraction/formulation_prompt_multi.j2"
       # ).render(
       #     PAPER_TEXT=paper_text,
       #     EXPERIMENTS=experiments,  # full JSON list so template can reference IDs
       #     SCHEMA=FormulationPass.model_json_schema(),
       # )

    parsed = _llm_extract(prompt, FormulationPass, model=llm_model)
    return parsed["formulations"] if parsed else []
