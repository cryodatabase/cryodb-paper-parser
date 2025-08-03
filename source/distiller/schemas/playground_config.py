from typing import List
from pydantic import BaseModel

ALLOWED_MODELS = {
    "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-20241022",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4"
}

class PlaygroundConfig(BaseModel):
    playground_enabled: bool
    distiller: str
    evaluation_models: List[str]

    def validate_models(self):
        for model in self.evaluation_models:
            if model not in ALLOWED_MODELS:
                raise ValueError(f"Invalid evaluation model: '{model}'")
