import json, backoff, time
from typing import Dict, Any, List
from openai import OpenAI
from langsmith.wrappers import wrap_openai
from pydantic import BaseModel, ValidationError
from distiller.utils.file_utils import clean_json_response
from distiller.schemas.extraction_passes import AgentPropertyPass, AgentsPass, ExperimentPass, FormulationPass
from anthropic import Anthropic, AsyncAnthropic
from jinja2 import Environment, FileSystemLoader
from langsmith.wrappers import wrap_anthropic  # LangSmith tracing wrapper
import os
# ensure tracing flag (do not overwrite if user set custom)
os.environ.setdefault("LANGSMITH_TRACING", "true")


_jinja = Environment(loader=FileSystemLoader("source/prompts"))
import os
from distiller.schemas.pipeline_config import PipelineConfig
# Wrapped OpenAI client for LangSmith tracing
client = wrap_openai(OpenAI(api_key=os.environ["OPENAI_API_KEY"]))
# Wrapped synchronous and asynchronous Anthropic clients
claude_client = wrap_anthropic(Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]))
async_claude_client = wrap_anthropic(AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"]))

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
        print("Model: ", model)
        if model == "o3-2025-04-16":
            print("Model (YES): o3-2025-04-16")
            return client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
            )
        if model == "o3-2025-04-16":
            print("Model (YES): gpt-5-2025-08-07")
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
            parsed_dict = json.loads(parsed.model_dump_json(by_alias=True))
            # additional check: if FormulationPass returns null formulations, treat as invalid and retry
            if schema_model.__name__ == "FormulationPass" and not parsed_dict.get("formulations"):  # None or empty
                raise ValueError("FormulationPass.formulations is None")
            return parsed_dict
        except (json.JSONDecodeError, ValidationError, ValueError) as err:
            if attempt == max_retries:
                print(f"[ERROR] LLM output invalid after {max_retries} tries: {err}")
                return None
            # feed validator errors back to the model
            # Tailor feedback depending on which schema we are validating
            if schema_model.__name__ == "FormulationPass":
                exp_context = messages[0]["content"] if messages else ""
                feedback = (
                    "The JSON did not pass validation for a FormulationPass object. "
                    "The top-level JSON must contain a non-empty `formulations` array, "
                    "each item following the required schema. MAKE SURE YOU PAY SPECIAL ATTENTION TO THE EXPERIMENTS QUOTE AND SOURCE CHUNK\n"
                    f"Validator error: {err}\n"
                    "Here are the experiment details again for reference:\n"
                    f"{exp_context}\n"
                    "Please correct and return ONLY the JSON object."
                )
            else:
                feedback = (
                    "The JSON did not pass validation:\n"
                    f"{err}\n"
                    "Please correct it and return ONLY the JSON object."
                )

            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": feedback},
            ]
def extract_agents(paper_text: str, llm_model: str, batch: bool = False) -> list[dict] | None:
    if batch:
        # we need to focus on generate the jsonl: {"custom_id": "request-1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4o", "messages": [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "What is the capital of France?"}]}}
        prompt = _jinja.get_template("agent_prompt_batch.j2").render(
            PAPER_TEXT=paper_text, SCHEMA=AgentsPass.model_json_schema()
        )
        
    else:
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
   # completed_parsed = _experiment_biological_context(parsed, llm_model)
    return parsed["experiments"] if parsed else None

def _experiment_biological_context(parsed: dict, llm_model: str) -> dict:
    """
    Complete biological_context for each experiment in one LLM pass.
    Returns a dict shaped exactly like ExperimentPass: {"experiments": [...]}
    """
    print("=== BIOLOGICAL CONTEXT COMPLETION PHASE ===")
    prompt_experiments_bio_context = Prompt(alias="biological_context_completion")
    prompt_experiments_bio_context.pull()

    prompt = prompt_experiments_bio_context.interpolate(
        SCHEMA=ExperimentPass.model_json_schema(),
        EXPERIMENTS=parsed["experiments"],  # pass only the experiments array to the prompt
    )

    llm_out = _llm_extract(prompt, ExperimentPass, model=llm_model)

    print("LLM OUT: ", llm_out)
    # --- normalize to ExperimentPass shape ---
    if not llm_out:
        return {"experiments": []}
    if isinstance(llm_out, list):
        # LLM returned a bare array; wrap it to the expected top-level object
        return {"experiments": llm_out}
    # If it's a Pydantic model, turn into a plain dict; otherwise assume dict already.
    if hasattr(llm_out, "model_dump"):
        return llm_out.model_dump()
    return llm_out

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
    MAX_ATTEMPTS = 3
    remaining_experiments = experiments  # start with all experiments
    collected_forms: list[dict] = []  # aggregated unique formulations

    for attempt in range(1, MAX_ATTEMPTS + 1):
        parsed = _llm_extract(prompt, FormulationPass, model=llm_model)
        if not parsed:
            print(f"[WARN] attempt {attempt}: no formulations returned")
        else:
            # merge while de-duplicating by formulation_id
            for form in parsed.get("formulations", []):
                fid = form.get("formulation_id")
                if fid and all(existing.get("formulation_id") != fid for existing in collected_forms):
                    collected_forms.append(form)

        # check coverage
        exp_ids = {str(exp["id"] if isinstance(exp, dict) else exp.get("id")) for exp in experiments}
        covered_ids = {f["experiment_id"] for f in collected_forms if f.get("experiment_id")}
        missing_ids = exp_ids - covered_ids
        if not missing_ids:
            break  # success

        if attempt == MAX_ATTEMPTS:
            print(f"[WARN] Still missing formulations for experiments after {MAX_ATTEMPTS} attempts: {missing_ids}")
            break

        # Build a new prompt focusing only on missing experiments
        remaining_experiments = [e for e in remaining_experiments if str(e["id"]) in missing_ids]
        print(f"[TRACE] Retrying for missing experiments: {remaining_experiments}")
        prompt_formulations_retry = Prompt(alias="formulations_extraction")
        prompt_formulations_retry.pull()
        prompt = prompt_formulations_retry.interpolate(
            SCHEMA=FormulationPass.model_json_schema(),
            PAPER_TEXT=paper_text,
            EXPERIMENTS=remaining_experiments,
        )

    return collected_forms
