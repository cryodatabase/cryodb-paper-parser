import re
from typing import List
from uuid import UUID
from pipelines.utils.embeddings import get_embedding
from distiller.schemas.papers import PaperStatus
import logging
from distiller.postgres_connection import cursor_ctx
SIMILARITY_THRESHOLD = 0.38

# ────────────────────────── alias helpers ──────────────────────────

_INCHI_PAT  = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$", re.I)
_EMBED_SQL  = """
SELECT id, chemical_id, alias, embedding <-> %s::vector AS dist
FROM   cpa_chemical_aliases
ORDER  BY dist
LIMIT  1;
"""

def _is_inchikey(k: str | None) -> bool:
    return bool(k and _INCHI_PAT.match(k))

def _canon(txt: str) -> str:
    return txt.strip().lower()

def _ensure_alias(
    cur, *, chemical_id: UUID, label: str, emb: List[float]
) -> UUID:
    """Insert the label as a new alias (or refresh the embedding)."""
    cur.execute(
        """
        INSERT INTO cpa_chemical_aliases (chemical_id, alias, embedding)
        VALUES (%s, %s, %s)
        ON CONFLICT (chemical_id, alias) DO UPDATE
              SET embedding = EXCLUDED.embedding
        RETURNING id;
        """,
        (chemical_id, label, emb),
    )
    return cur.fetchone()["id"]

def resolve_alias_id(
    cur, *, inchikey: str | None, label: str
) -> tuple[UUID | None, UUID | None]:
    """
    Return **(alias_id, chemical_id)** for a component.

    1.  Exact InChIKey → cpa_chemicals, create alias if “label” missing.
    2.  Otherwise: semantic match on `cpa_chemical_aliases` (pgvector).
    """
    # 1️⃣  direct InChIKey
    if _is_inchikey(inchikey):
        cur.execute("SELECT id FROM cpa_chemicals WHERE inchikey = %s;", (inchikey,))
        row = cur.fetchone()
        if row:
            chem_id = row["id"]

            cur.execute(
                "SELECT id FROM cpa_chemical_aliases "
                "WHERE chemical_id = %s AND alias = %s;",
                (chem_id, label),
            )
            alias_row = cur.fetchone()
            if alias_row:
                return alias_row["id"], chem_id   # alias already present

            # create missing alias
            emb = get_embedding(_canon(label))
            alias_id = _ensure_alias(cur, chemical_id=chem_id, label=label, emb=emb)
            return alias_id, chem_id

    # 2️⃣  embedding search
    vec = get_embedding(_canon(label))
    cur.execute(_EMBED_SQL, (vec,))
    row = cur.fetchone()
    if row and row["dist"] < SIMILARITY_THRESHOLD:
        return row["id"], row["chemical_id"]

    return None, None   # not found

def stage_and_merge(stage_table: str, rows: list[dict], merge_fn: str):
    if not rows:
        return []
    with cursor_ctx(commit=True) as cur:
        # 1. COPY rows into the staging table (as JSONB)
        tmp_json = [json.dumps(r) for r in rows]
        cur.copy_from(io.StringIO("\n".join(tmp_json)),
                      stage_table, columns=("data_json",))

        # 2. Call the merge function; it returns (json_id, live_table_id)
        cur.execute(f"SELECT * FROM {merge_fn}();")
        return cur.fetchall()

def update_workflow_status(paper_md5_hash: str, status: PaperStatus):
    try:
        with cursor_ctx(commit=True) as cur:
            cur.execute(
                "UPDATE papers SET status = %s WHERE md5_hash = %s;",
                (status, paper_md5_hash),
            )
    except Exception as err:
        logging.error(f"Failed to update workflow status for {paper_md5_hash}: {err}")