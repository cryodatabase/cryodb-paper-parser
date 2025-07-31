import json
import os
from typing import Any, Dict, List
from openai import OpenAI
from pydantic import ValidationError
from distiller.schemas.papers import Paper
from distiller.utils.file_utils import clean_json_response
from distiller.postgres_connection import cursor_ctx
from collections.abc import Sequence
from distiller.schemas.structured_output import CPAPaperData
from psycopg.errors import NoDataFound 
import boto3
import logging
log = logging.getLogger(__name__)

s3 = boto3.client("s3")

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not _OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found in environment.")
client = OpenAI(api_key=_OPENAI_API_KEY)

_S3_TARGET_BUCKET = os.getenv("S3_TARGET_BUCKET")
if not _S3_TARGET_BUCKET:
    raise RuntimeError("S3_TARGET_BUCKET not found in environment.")


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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "schema.json")
PROMPT_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "gemini_prompt.txt")


def _build_meta_prompt(text: str) -> str:
    """Embed schema + paper text into the prompt template."""
    schema_json = json.dumps(Paper.model_json_schema(), indent=2)
    return (
        _METADATA_PROMPT
        .replace("{{SCHEMA}}", schema_json)
        .replace("{{PAPER_TEXT}}", text[:16_000])  # keep prompt inside token budget
    )


def _extract_metadata(fulltext: str) -> Dict[str, Any] | None:
    """GPT‑4, validate against Paper schema, retry once if invalid."""
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
        except json.JSONDecodeError as json_err:
            validation_exc = json_err
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

def update_metadata_from_fulltext(md5_hashes: str | Sequence[str], ocr_response: Any) -> None:
    if isinstance(md5_hashes, str):
        md5_hashes = [md5_hashes]

    for md5 in md5_hashes:
        paper_id = _update_single_metadata(md5, ocr_response)
    return paper_id

def _update_single_metadata(md5_hash: str, ocr_response: Any) -> None:
    paper_fulltext = (
            ocr_response
            if isinstance(ocr_response, str)
            else "\n\n".join(p.markdown for p in ocr_response.pages)
        )
    extracted = _extract_metadata(paper_fulltext)
    if not extracted:
        print(f"[WARN] Could not extract metadata for {md5_hash}; leaving row unchanged.")
        return

# -------- 3. pydantic validation ------------------------------
    try:
        paper_obj = Paper.model_validate(extracted)
    except ValidationError as err:
        print("[ERROR] Validation failure while updating metadata:", err)
        return _get_paper_id(md5_hash)

    # -------- 4. dynamic UPDATE only on changed / present fields --
    columns, values = [], []
    for field in paper_obj.model_fields_set:
        if field in {"id", "md5_hash", "status"}:
            continue
        value = getattr(paper_obj, field)
        if value is None:
            continue
        columns.append(f"{field} = %s")
        values.append(json.dumps(value) if field == "authors_json" else value)

    if columns:
        sql = f"""
            UPDATE papers
               SET {', '.join(columns)}
             WHERE md5_hash = %s
            RETURNING id;          -- <-- RETURNING goes here, inside the query
        """

        values.append(md5_hash)

        with cursor_ctx(commit=True) as cur:
            cur.execute(sql, tuple(values))
            paper_id = cur.fetchone()["id"]        # fetch the UUID you just returned

            log.info("metadata updated for %s", md5_hash)
            log.info("paper_id fetched for %s → %s", md5_hash, paper_id)
            return paper_id
    else:
        log.info("no new metadata for %s", md5_hash)
        return None

def _get_paper_id(md5_hash: str, cur) -> str | None:
    md5_hash = md5_hash.strip()
    cur.execute("SELECT id FROM papers WHERE md5_hash = %s;", (md5_hash,))
    row = cur.fetchone()
    if row:
        return row["id"]
    log.warning("paper not found for md5=%s", md5_hash)
    return None

def add_paper_to_db(paper: Paper, cur):
    cur.execute(
                    """
                    INSERT INTO papers (
                        md5_hash,
                        file_s3_uri,
                        fulltext_s3_uri,
                        file_size_bytes,
                        status,
                        source,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        paper.md5_hash.strip(),
                        paper.file_s3_uri,
                        paper.fulltext_s3_uri,
                        paper.file_size_bytes,
                        paper.status.value,
                        paper.source,
                        paper.created_at,
                    ),
                )



def _stream_s3_text(uri: str) -> str:
    prefix = f"s3://{_S3_TARGET_BUCKET}/"
    if not uri.startswith(prefix):
        raise ValueError(f"URI must start with {prefix!r}")
    key = uri[len(prefix):]
    obj = s3.get_object(Bucket=_S3_TARGET_BUCKET, Key=key)
    return obj["Body"].read().decode()

def _build_prompt(paper_text: str) -> str:
    with open(PROMPT_PATH, encoding='utf-8') as fh:
        PROMPT_TEMPLATE = fh.read()
    schema_json = json.dumps(CPAPaperData.model_json_schema(), indent=2)
    prompt = PROMPT_TEMPLATE.replace("{{PAPER_TEXT}}", paper_text)
    prompt = prompt.replace("{{SCHEMA}}", schema_json)
    return prompt

def _extract(paper_text: str) -> dict | None:
    """Send the extraction prompt and, if validation fails, give the
    validation errors back to the model for one corrective attempt."""

    base_prompt = _build_prompt(paper_text)
    messages = [{"role": "user", "content": base_prompt}]

    for attempt in (1, 2, 3):  # max three tries
        try:
            resp = client.chat.completions.create(
                model="gpt-4.1-mini-2025-04-14",
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
        except Exception as e:
            print("[ERROR] OpenAI API failed:", e)
            return None

        # Clean and parse
        content_str = raw if isinstance(raw, str) else json.dumps(raw)
        if "clean_json_response" in globals():
            content_str = clean_json_response(content_str)

        try:
            data_dict = json.loads(content_str)
        except json.JSONDecodeError as jerr:
            # If JSON cannot even be parsed, treat as validation error path
            data_dict = None
            validation_exc = jerr
        else:
            try:
                CPAPaperData.model_validate(data_dict)
                # Success — return normalized JSON with aliases
                return json.loads(
                    CPAPaperData.model_validate(data_dict).model_dump_json(by_alias=True)
                )
            except ValidationError as verr:
                validation_exc = verr

        # If we reach here there was a validation / parsing problem.
        if attempt == 1:
            # Feed the errors back for a second attempt.
            err_text = (
                "The JSON you provided did not pass validation. "
                "Here are the problems:\n"
                f"{validation_exc}\n"
                "Please correct the JSON and return ONLY the corrected JSON object."
            )
            # Record model's previous (invalid) answer so it has context
            messages.append({"role": "assistant", "content": raw})
            # Ask model to fix
            messages.append({"role": "user", "content": err_text})
            continue  # second loop iteration
        elif attempt == 2:
            # Feed the errors back for a second attempt.
            err_text = (
                "The JSON you provided did not pass validation. "
                "Here are the problems:\n"
                f"{validation_exc}\n"
                "Please correct the JSON and return ONLY the corrected JSON object."
            )
            # Record model's previous (invalid) answer so it has context
            messages.append({"role": "assistant", "content": raw})
            # Ask model to fix
            messages.append({"role": "user", "content": err_text})
            continue  # second loop iteration
        else:
            # Second attempt also failed
            print("[ERROR] Validation/JSON error after retry:", validation_exc)
            return None


def get_cpa_facts_from_fulltext(file_md5_hash: str | None = None, limit: int = 100) -> None:
    if file_md5_hash:
        query = """
            SELECT id, fulltext_s3_uri
            FROM papers
            WHERE md5_hash = %s
              AND fulltext_s3_uri IS NOT NULL
              AND cpa_facts_json IS NULL
              AND status = 'DOWNLOADED';
        """
        params = (file_md5_hash,)
        single_paper = True
    else:
        query = """
            SELECT id, fulltext_s3_uri
            FROM papers
            WHERE fulltext_s3_uri IS NOT NULL
              AND cpa_facts_json IS NULL
              AND status = 'DOWNLOADED'
            LIMIT %s;
        """
        params = (limit,)
        single_paper = False

    with cursor_ctx() as cur:
        cur.execute(query, params)
        rows = cur.fetchall() if not single_paper else [cur.fetchone()] if cur.rowcount else []

    if not rows or rows == [None]:
        msg = f"[TRACE] No pending paper found with md5_hash={file_md5_hash}." if file_md5_hash \
            else "[TRACE] No pending papers."
        print(msg)
        return

    done = 0
    for row in rows:
        if not row:
            continue
        paper_id, uri = row
        print(f"[TRACE] Extracting CPAs from {uri} …")
        parsed = _extract(_stream_s3_text(uri))
        if not parsed:
            print("[WARN] Extraction failed; marking FAILED")
            with cursor_ctx(commit=True) as cur:
                cur.execute("UPDATE papers SET status='FAILED' WHERE id=%s;", (paper_id,))
            return "FAILED"
        with cursor_ctx(commit=True) as cur:
            cur.execute(
                "UPDATE papers SET cpa_facts_json=%s, status='COMPLETED' WHERE id=%s;",
                (json.dumps(parsed), paper_id),
            )
        done += 1
        print("[TRACE] Paper updated and marked COMPLETED.")

    print(f"[TRACE] {done}/{len(rows)} papers updated." if not single_paper else "[TRACE] Done.")

