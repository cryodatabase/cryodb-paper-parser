
from pydantic import BaseModel

class PipelineConfig(BaseModel):
    distiller: str
    llm_model_parser: str