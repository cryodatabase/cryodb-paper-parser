#!/usr/bin/env python3
"""
Convert the original 126‑line INSERT into one that also stores a pgvector
embedding (OpenAI text‑embedding‑3‑small, 1536 dims) per row.

• Requires: pgvector‑python, openai >= 1.2
• OPENAI_API_KEY must be set in your environment.

Result saved to insert_cpa_with_embeddings.sql
"""
import re, json, os, sys, textwrap
import openai
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = "text-embedding-3-small"

# ----------------------------------------------------------------------
def extract_rows(sql_text: str):
    """
    Parse the existing INSERT statement; yield tuples
      (inchikey_or_None, preferred_name, synonyms_json)
    """
    pattern = re.compile(
        r"\(\s*(NULL|'[^']*')\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)", re.I
    )
    for inchikey_txt, pref_name, syn_json in pattern.findall(sql_text):
        inchikey = None if inchikey_txt.upper() == "NULL" else inchikey_txt.strip("'")
        yield inchikey, pref_name, syn_json


def get_embedding(text: str):
    return openai.embeddings.create(model=MODEL, input=text).data[0].embedding


def main():
    original_sql_file = "insertions_cpas.sql"  # <-- put your 126‑row file here
    with open(original_sql_file, "r", encoding="utf-8") as fh:
        sql_blob = fh.read()

    rows_out = []
    for inchikey, pref, syn_json in extract_rows(sql_blob):
        print(f"Embedding {pref} …")
        emb = get_embedding(pref.lower())
        rows_out.append(
            (
                inchikey,
                pref,
                syn_json,
                "[" + ",".join(f"{x:.6f}" for x in emb) + "]",  # pgvector literal
            )
        )

    with open("insert_cpa_with_embeddings.sql", "w", encoding="utf-8") as out:
        out.write(
            "INSERT INTO cpa_chemicals "
            "(inchikey, preferred_name, synonyms, embedding)\nVALUES\n"
        )
        values_sql = []
        for inchikey, pref, syn_json, vec in rows_out:
            inchikey_sql = "NULL" if inchikey is None else f"'{inchikey}'"
            # Escape single quotes in preferred_name for safe SQL literal
            escaped_pref = pref.replace("'", "''")
            values_sql.append(
                f" ({inchikey_sql}, '{escaped_pref}', "
                f"'{syn_json}'::jsonb, '{vec}')"
            )
        out.write(",\n".join(values_sql))
        out.write(
            "\nON CONFLICT (inchikey)\n"
            "DO UPDATE SET\n"
            "  preferred_name = EXCLUDED.preferred_name,\n"
            "  synonyms       = EXCLUDED.synonyms,\n"
            "  embedding      = EXCLUDED.embedding;\n"
        )

    print("⏩  File written: insert_cpa_with_embeddings.sql")


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("❌  Set OPENAI_API_KEY in your environment first")
    main()
