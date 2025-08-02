"""
Python‑only merge from MoleculeCoreData JSON → live tables.

Depends on:
    • distiller.postgres_connection.cursor_ctx
    • pipelines.utils.embeddings.get_embedding
"""
from __future__ import annotations
from typing import Iterable
import re
from distiller.postgres_connection import cursor_ctx
from distiller.schemas.extraction_passes import MoleculeCoreData
from pipelines.utils.embeddings import get_embedding

SIMILARITY_THRESHOLD = 0.38
_INCHI_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")

# ── SQL snippets ─────────────────────────────────────────────────
_SQL_NEAREST_ALIAS = """
SELECT chemical_id,
       embedding <-> (%(qvec)s)::vector AS dist
  FROM cpa_chemical_aliases
 ORDER BY embedding <-> (%(qvec)s)::vector
 LIMIT 1;
"""


_SQL_INSERT_CHEM = """
INSERT INTO cpa_chemicals (inchikey, preferred_name, role, embedding)
VALUES (%(inchikey)s, %(pref)s, %(role)s, %(emb)s)
ON CONFLICT (inchikey) DO UPDATE
   SET preferred_name = EXCLUDED.preferred_name,
       role           = EXCLUDED.role,
       embedding      = EXCLUDED.embedding
RETURNING id;
"""

_SQL_INSERT_CHEM_TEXT = """
INSERT INTO cpa_chemicals (preferred_name, role, embedding)
VALUES (%(pref)s, %(role)s, %(emb)s)
ON CONFLICT (preferred_name) DO UPDATE
   SET role      = EXCLUDED.role,
       embedding = EXCLUDED.embedding
RETURNING id;
"""

_SQL_INSERT_ALIAS = """
INSERT INTO cpa_chemical_aliases
    (chemical_id, alias, embedding, is_preferred)
VALUES (%s, %s, %s, %s)
ON CONFLICT DO NOTHING;
"""

# ── main entry point ────────────────────────────────────────────
def merge_agents(rows: Iterable[dict]) -> int:
    """
    Upsert a batch of MoleculeCoreData rows.

    Returns
    -------
    int
        Number of agent JSON objects processed (for logging/metrics).
    """
    processed = 0

    with cursor_ctx(commit=True) as cur:
        for raw in rows:
            print("RAW: ", raw)
            agent = MoleculeCoreData.model_validate(raw)

            # 1. Find closest alias
            qvec = get_embedding(agent.preferred_name.lower().strip())
            cur.execute(_SQL_NEAREST_ALIAS, {"qvec": qvec})
            hit = cur.fetchone()

            # 2. Choose insert strategy
            if hit and hit["dist"] < SIMILARITY_THRESHOLD:
                chem_id = hit["chemical_id"]
            else:
                if agent.inchikey and _INCHI_RE.match(agent.inchikey):
                    cur.execute(
                        _SQL_INSERT_CHEM,
                        dict(
                            inchikey=agent.inchikey,
                            pref=agent.preferred_name,
                            role=agent.role.value,
                            emb=qvec,
                        ),
                    )
                else:
                    cur.execute(
                        _SQL_INSERT_CHEM_TEXT,
                        dict(
                            pref=agent.preferred_name,
                            role=agent.role.value,
                            emb=qvec,
                        ),
                    )
                chem_id = cur.fetchone()["id"]

            # 3. Insert aliases in bulk with executemany
            alias_rows = [
                (
                    chem_id,
                    name,
                    get_embedding(name.lower().strip()),
                    is_pref,
                )
                for name, is_pref in (
                    [(agent.preferred_name, True)]
                    + [(s, False) for s in agent.synonyms]
                )
            ]
            cur.executemany(_SQL_INSERT_ALIAS, alias_rows)

            processed += 1

    return processed