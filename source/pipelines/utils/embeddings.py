
from __future__ import annotations
import functools, os, openai
from typing import List

openai.api_key = os.getenv("OPENAI_API_KEY")

@functools.lru_cache(maxsize=4096)
def get_embedding(text: str) -> List[float]:
    rsp = openai.embeddings.create(
        input=text,
        model="text-embedding-3-large"
    )
    return rsp.data[0].embedding
