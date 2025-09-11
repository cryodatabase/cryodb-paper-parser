
from pydantic import BaseModel
from typing import List

class PipelineConfig(BaseModel):
    version: str
    distiller: str
    llm_model_parser: List[str]
    playground_enabled: bool
    available_models: List[str]
    