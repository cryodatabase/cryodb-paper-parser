from .helpers import _llm_extract
from distiller.schemas.agent import CPACoreData
from jinja2 import Environment, FileSystemLoader

_jinja = Environment(loader=FileSystemLoader("prompts"))

def extract_agents(paper_text: str) -> list[dict] | None:
    prompt = _jinja.get_template("agent_prompt.j2").render(
        PAPER_TEXT=paper_text, SCHEMA=CPACoreData.model_json_schema()
    )
    return _llm_extract(prompt, CPACoreData)
