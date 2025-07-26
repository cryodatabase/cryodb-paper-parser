from __future__ import annotations

import json
import os
import boto3
from openai import OpenAI
from pydantic import ValidationError

from distiller.postgres_connection import cursor_ctx
from distiller.utils.file_utils import clean_json_response
from distiller.schemas.structured_output import CPAPaperData

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not _OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found in environment.")

_S3_TARGET_BUCKET = os.getenv("S3_TARGET_BUCKET")
if not _S3_TARGET_BUCKET:
    raise RuntimeError("S3_TARGET_BUCKET not found in environment.")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "gpt_prompt.txt")

client = OpenAI(api_key=_OPENAI_API_KEY)
s3 = boto3.client("s3")


with open(PROMPT_PATH, encoding='utf-8') as fh:
    PROMPT_TEMPLATE = fh.read()  # Should contain {{PAPER_TEXT}} and {{SCHEMA}}

def _stream_s3_text(uri: str) -> str:
    prefix = f"s3://{_S3_TARGET_BUCKET}/"
    if not uri.startswith(prefix):
        raise ValueError(f"URI must start with {prefix!r}")
    key = uri[len(prefix):]
    obj = s3.get_object(Bucket=_S3_TARGET_BUCKET, Key=key)
    return obj["Body"].read().decode()

def _build_prompt(paper_text: str) -> str:
    schema_json = json.dumps(CPAPaperData.model_json_schema(), indent=2)
    prompt = PROMPT_TEMPLATE.replace("{{PAPER_TEXT}}", paper_text)
    prompt = prompt.replace("{{SCHEMA}}", schema_json)
    return prompt

def _extract(paper_text: str) -> dict | None:
    """Send the extraction prompt and, if validation fails, give the
    validation errors back to the model for one corrective attempt."""

    base_prompt = _build_prompt(paper_text)
    messages = [{"role": "user", "content": base_prompt}]

    for attempt in (1, 2):  # max two tries
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
            continue
        with cursor_ctx(commit=True) as cur:
            cur.execute(
                "UPDATE papers SET cpa_facts_json=%s, status='COMPLETED' WHERE id=%s;",
                (json.dumps(parsed), paper_id),
            )
        done += 1
        print("[TRACE] Paper updated and marked COMPLETED.")

    print(f"[TRACE] {done}/{len(rows)} papers updated." if not single_paper else "[TRACE] Done.")
