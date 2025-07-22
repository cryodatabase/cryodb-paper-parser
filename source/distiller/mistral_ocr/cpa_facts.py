from __future__ import annotations
import json, os
from typing import Any, Dict
import boto3, google.generativeai as genai
from jsonschema import validate, ValidationError
from ..postgres_connection import cursor_ctx
from distiller.utils.file_utils import clean_json_response

_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not _GEMINI_API_KEY:
    raise RuntimeError("Gemini API key not found in .env file.")

_S3_TARGET_BUCKET = os.getenv("S3_TARGET_BUCKET")
if not _S3_TARGET_BUCKET:
    raise RuntimeError("S3_TARGET_BUCKET not found in .env file.")

genai.configure(api_key=_GEMINI_API_KEY)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "schema.json")
PROMPT_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "gemini_prompt.txt")

with open(SCHEMA_PATH) as fh:
    SCHEMA_OBJ = json.load(fh)
    SCHEMA_STR = json.dumps(SCHEMA_OBJ, indent=2)

with open(PROMPT_PATH) as fh:
    PROMPT_TEMPLATE = fh.read()

s3 = boto3.client("s3")


def _stream_s3_text(uri: str) -> str:
    prefix = f"s3://{_S3_TARGET_BUCKET}/"
    if not uri.startswith(prefix):
        raise ValueError(f"URI must start with {prefix!r}")
    key = uri[len(prefix):]
    return s3.get_object(Bucket=_S3_TARGET_BUCKET, Key=key)["Body"].read().decode()

def _extract(text: str) -> Dict[str, Any] | None:
    prompt = PROMPT_TEMPLATE.replace("{{SCHEMA}}", SCHEMA_STR).replace("{{PAPER_TEXT}}", text)
    try:
        raw = genai.GenerativeModel("gemini-2.5-pro").generate_content(prompt).text
    except Exception as e:
        print("[ERROR] Gemini API failed:", e); return None

    try:
        data = json.loads(clean_json_response(raw))
        validate(data, SCHEMA_OBJ)
        return data
    except (json.JSONDecodeError, ValidationError) as e:
        print("[ERROR] Gemini output bad:", e); return None

def get_cpa_facts_from_fulltext(file_md5_hash: str | None = None, limit: int = 100) -> None:
    if not file_md5_hash:
        
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT id, fulltext_s3_uri
                FROM papers
                WHERE fulltext_s3_uri IS NOT NULL
                AND cpa_facts_json IS NULL
                AND status = 'DOWNLOADED'
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

        if not rows:
            print("[TRACE] No pending papers."); return

        done = 0
        for paper_id, uri in rows:
            print(f"[TRACE] Extracting CPAs from {uri} …")
            parsed = _extract(_stream_s3_text(uri))
            if not parsed:
                print("[WARN] Failed — marking FAILED")
                with cursor_ctx(commit=True) as cur:
                    cur.execute("UPDATE papers SET status='FAILED' WHERE id=%s;", (paper_id,))
                continue

            with cursor_ctx(commit=True) as cur:
                cur.execute(
                    "UPDATE papers SET cpa_facts_json=%s, status='COMPLETED' WHERE id=%s;",
                    (json.dumps(parsed), paper_id),
                )
            done += 1
            print("[TRACE] OK")

        print(f"[TRACE] {done}/{len(rows)} papers updated.")
    else:
        with cursor_ctx() as cur:
            cur.execute(
                """
                SELECT id, fulltext_s3_uri
                FROM papers
                WHERE md5_hash = %s
                  AND fulltext_s3_uri IS NOT NULL
                  AND cpa_facts_json IS NULL
                  AND status = 'DOWNLOADED';
                """,
                (file_md5_hash,),
            )
            row = cur.fetchone()

        if not row:
            print(f"[TRACE] No pending paper found with md5_hash={file_md5_hash}.")
            return

        paper_id, uri = row
        print(f"[TRACE] Extracting CPAs from {uri} …")
        parsed = _extract(_stream_s3_text(uri))
        if not parsed:
            print("[WARN] Extraction failed; marking FAILED")
            with cursor_ctx(commit=True) as cur:
                cur.execute("UPDATE papers SET status='FAILED' WHERE id=%s;", (paper_id,))
            return

        with cursor_ctx(commit=True) as cur:
            cur.execute(
                "UPDATE papers SET cpa_facts_json=%s, status='COMPLETED' WHERE id=%s;",
                (json.dumps(parsed), paper_id),
            )
        print("[TRACE] Paper updated and marked COMPLETED.")