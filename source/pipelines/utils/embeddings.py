
from __future__ import annotations
import functools, os, openai
from typing import List

openai.api_key = os.getenv("OPENAI_API_KEY")

@functools.lru_cache(maxsize=4096)
def get_embedding(text: str) -> List[float]:
    """
    Returns a 1536‑dim OpenAI embedding for the given text.
    Cached for the lifetime of the process.
    """
    rsp = openai.embeddings.create(
        input=text,
        model="text-embedding-3-small"  # 1536 dims, inexpensive
    )
    return rsp.data[0].embedding
