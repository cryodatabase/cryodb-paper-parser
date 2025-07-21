"""Extract structured metadata from PMC XML files stored in S3.

The pipeline mirrors the logic in `source/extractor.py` but works
programmatically on rows in the `papers` table:

1. Query Postgres for PMC papers where free full text is available and STATUS = "PENDING" (not yet processed).
2. Stream their `file_s3_uri` (actually XML) from S3.
3. Send the content to Gemini 2.5-Pro with a prompt containing
   `schema.json`, asking for a JSON response.
4. Validate the response and update the `papers` row
   (`cpa_facts_json` column, create if not exists).

"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List

import boto3
import google.generativeai as genai
from dotenv import load_dotenv
from jsonschema import validate, ValidationError

# Local imports
from ..postgres_connection import cursor_ctx

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    sys.exit("[ERROR] GEMINI_API_KEY missing in .env")

# Bucket where PMC XML files live after `get_papers_from_pmc` has copied them.
S3_TARGET_BUCKET = os.getenv("S3_TARGET_BUCKET")
if not S3_TARGET_BUCKET:
    sys.exit("[ERROR] S3_TARGET_BUCKET missing in .env")

genai.configure(api_key=GEMINI_API_KEY)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "schema.json")
PROMPT_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "gemini_prompt_xml.txt")

with open(SCHEMA_PATH) as fh:
    SCHEMA_OBJ = json.load(fh)
    SCHEMA_STR = json.dumps(SCHEMA_OBJ, indent=2)

with open(PROMPT_PATH) as fh:
    PROMPT_TEMPLATE = fh.read()

s3 = boto3.client("s3")

# ---------- helpers ----------

def _strip_code_block(text: str) -> str:
    """Remove ```json ... ``` wrappers if present."""
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)


def stream_s3_text(file_s3_uri: str) -> str:
    prefix = f"s3://{S3_TARGET_BUCKET}/"
    if not file_s3_uri.startswith(prefix):
        raise ValueError(
            f"Expected URI to start with {prefix!r}, got {file_s3_uri!r}"
        )
    key = file_s3_uri[len(prefix):]
    obj = s3.get_object(Bucket=S3_TARGET_BUCKET, Key=key)
    return obj["Body"].read().decode("utf-8", errors="replace")


def extract_with_gemini(xml_text: str) -> Dict[str, Any] | None:
    prompt = (
        PROMPT_TEMPLATE.replace("{{SCHEMA}}", SCHEMA_STR)
        .replace("{{PAPER_TEXT}}", xml_text)
    )
    model = genai.GenerativeModel("gemini-2.5-pro")
    try:
        response = model.generate_content(prompt)
    except Exception as e:
        print("[ERROR] Gemini API call failed:", e)
        return None

    raw = _strip_code_block(response.text)
    try:
        data = json.loads(raw)
        validate(instance=data, schema=SCHEMA_OBJ)
        return data
    except (json.JSONDecodeError, ValidationError) as e:
        print("[ERROR] Gemini output invalid:", e)
        return None

# ---------- main routine ----------

def get_cpa_facts_from_papers(limit: int = 10) -> None:
    """Process up to *limit* un-extracted PMC papers."""
    with cursor_ctx() as cur:
        cur.execute(
            """
            SELECT id, file_s3_uri
            FROM papers
            WHERE source = 'PMC'
              AND is_free_fulltext = TRUE
              AND status = 'PENDING'
              AND cpa_facts_json IS NULL
              AND file_s3_uri IS NOT NULL
            LIMIT %s;
            """,
            (limit,),
        )
        rows = cur.fetchall()

    if not rows:
        print("[TRACE] No pending papers found.")
        return

    processed = 0
    for paper_id, s3_uri in rows:
        print(f"[TRACE] Processing {s3_uri} …")
        xml_text = stream_s3_text(s3_uri)
        parsed = extract_with_gemini(xml_text)

        if not parsed:
            print(f"[WARN] Extraction failed for {s3_uri}; marking as FAILED")
            with cursor_ctx(commit=True) as cur:
                cur.execute(
                    """
                    UPDATE papers
                    SET status = 'FAILED'
                    WHERE id = %s;
                    """,
                    (paper_id,),
                )
            continue  # skip to next row

        with cursor_ctx(commit=True) as cur:
            cur.execute(
                """
                UPDATE papers
                SET cpa_facts_json = %s,
                    status = 'COMPLETED'
                WHERE id = %s;
                """,
                (json.dumps(parsed), paper_id),
            )
        processed += 1
        print(f"[TRACE] Stored metadata and marked COMPLETED for {s3_uri}.")

    print(f"[TRACE] Completed. {processed}/{len(rows)} papers updated.")
