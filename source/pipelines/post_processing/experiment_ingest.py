# pipelines/post_processing/experiment_ingest.py
from __future__ import annotations
from typing import List, Dict, Any
from distiller.postgres_connection import cursor_ctx
from psycopg.types.json import Json

def _paper_uuid_from_md5(cur, md5_hash: str) -> str | None:
    cur.execute("SELECT id FROM papers WHERE md5_hash = %s;", (md5_hash,))
    row = cur.fetchone()
    return row["id"] if row else None


def insert_experiments(paper_md5: str, experiments: List[Dict[str, Any]]) -> None:
    if not experiments:
        return

    with cursor_ctx(commit=True) as cur:
        paper_uuid = _paper_uuid_from_md5(cur, paper_md5)
        if paper_uuid is None:
            raise RuntimeError(f"No `papers` row for md5={paper_md5}")

        rows = [
            (
                paper_uuid,
                e.get("id"),
                e.get("performed_in_this_paper", True),
                e.get("label"),
                e.get("method"),
                Json(e["biological_context"]) if e.get("biological_context") else None,
                e["quote"],
            )
            for e in experiments
        ]

        cur.executemany(
            """
            INSERT INTO experiments
                (paper_id, local_id, performed_in_this_paper, label, method,
                biological_context, quote)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING;
            """,
            rows,
        )
