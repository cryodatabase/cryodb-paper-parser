import json
import os
from typing import Any, Dict, List
from openai import OpenAI
from pydantic import ValidationError

from distiller.schemas.papers import Paper
from distiller.utils.file_utils import clean_json_response

# ───────────────────────────────────────────
# ENV & CLIENTS
# ───────────────────────────────────────────
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not _OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found in environment.")
client = OpenAI(api_key=_OPENAI_API_KEY)

# Prompt template (put this wherever you keep templates; inline here for brevity)
_METADATA_PROMPT = """
You are an information‑extraction agent.
Extract the required bibliographic metadata from the PAPER TEXT and return **ONLY** a JSON object
that strictly conforms to the supplied JSON SCHEMA.

• If a field cannot be found, omit it (do NOT invent values).
• Dates: try to split year / month / day when possible.
• authors_json should be a list of objects, each with at least "name".
• authors_flat should be a single string with authors separated by "; ".

JSON SCHEMA:
{{SCHEMA}}

PAPER TEXT (truncated to first 16 000 chars):
{{PAPER_TEXT}}
""".strip()


# ───────────────────────────────────────────
# HELPERS
# ───────────────────────────────────────────
def _build_meta_prompt(text: str) -> str:
    """Embed schema + paper text into the prompt template."""
    schema_json = json.dumps(Paper.model_json_schema(), indent=2)
    return (
        _METADATA_PROMPT
        .replace("{{SCHEMA}}", schema_json)
        .replace("{{PAPER_TEXT}}", text[:16_000])  # keep prompt inside token budget
    )


def _extract_metadata(fulltext: str) -> Dict[str, Any] | None:
    """Chat w/ GPT‑4, validate against Paper schema, retry once if invalid."""
    base_prompt = _build_meta_prompt(fulltext)
    messages: List[Dict[str, str]] = [{"role": "user", "content": base_prompt}]

    for attempt in (1, 2):
        try:
            resp = client.chat.completions.create(
                model="gpt-4.1-mini-2025-04-14",
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw_content = resp.choices[0].message.content
        except Exception as e:
            print("[ERROR] OpenAI API failed:", e)
            return None

        # Normalise content → dict
        content_str = raw_content if isinstance(raw_content, str) else json.dumps(raw_content)
        if "clean_json_response" in globals():
            content_str = clean_json_response(content_str)

        try:
            data_dict = json.loads(content_str)
        except json.JSONDecodeError as jerr:
            validation_exc = jerr
            data_dict = None
        else:
            try:
                # Validate (will coerce types & drop extras)
                Paper.model_validate(data_dict)
                return data_dict
            except ValidationError as verr:
                validation_exc = verr

        # Retry path
        if attempt == 1:
            err_msg = (
                "The JSON failed validation with these errors:\n"
                f"{validation_exc}\n"
                "Please fix the JSON and return ONLY the corrected object."
            )
            messages.append({"role": "assistant", "content": raw_content})
            messages.append({"role": "user", "content": err_msg})
            continue

        print("[ERROR] Metadata validation failed after second attempt:", validation_exc)
        return None


# ───────────────────────────────────────────
# MAIN FUNCTION
# ───────────────────────────────────────────
def update_metadata_from_fulltext(
    md5_hash: str,
    ocr_response: Any,
    source: str,
    cur,
) -> None:
    if isinstance(ocr_response, str):
        extracted = _extract_metadata(ocr_response)
    else:
        full_markdown = "\n\n".join(page.markdown for page in ocr_response.pages)
        extracted = _extract_metadata(full_markdown)
    if not extracted:
        print(f"[WARN] Could not extract metadata for {md5_hash}; leaving row unchanged.")
        return

    # Guarantee required `source`
    extracted["source"] = extracted.get("source") or source

    try:
        paper_obj = Paper.model_validate(extracted)
    except ValidationError as err:
        # Should be rare – additional guard
        print("[ERROR] Unexpected validation error:", err)
        return

    # Build dynamic UPDATE statement with only non‑None fields
    columns, values = [], []
    for field in paper_obj.model_fields_set:  # only fields present in JSON
        value = getattr(paper_obj, field)
        if value is None or field in {"id", "md5_hash", "status"}:
            continue
        columns.append(f"{field} = %s")
        # authors_json must be stored as JSONB → dump to str
        values.append(json.dumps(value) if field == "authors_json" else value)

    if not columns:
        print(f"[TRACE] No new metadata for {md5_hash}.")
        return

    values.append(md5_hash)
    sql = f"UPDATE papers SET {', '.join(columns)} WHERE md5_hash = %s;"
    cur.execute(sql, tuple(values))
    cur.connection.commit()
    print(f"[TRACE] Metadata updated for {md5_hash}.")