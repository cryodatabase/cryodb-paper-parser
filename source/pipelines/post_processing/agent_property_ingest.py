"""
Insert AgentProperty objects directly into the CPA core tables.

Resolution strategy
───────────────────
1. Exact match on InChIKey (fast path).
2. Semantic match on any alias embedding within `SIMILARITY_THRESHOLD`.
   • Uses pgvector `<->` distance against cpa_chemical_aliases.embedding.
3. If no match → skip property and log a warning.  (The agents pass
   should have inserted the chemical already, so this is rare.)
"""

from __future__ import annotations

import json
import re
from typing import List, Dict, Any, Tuple
from uuid import UUID

from distiller.postgres_connection import cursor_ctx
from pipelines.utils.embeddings import get_embedding  # same helper you use elsewhere
from pipelines.utils.embeddings import SIMILARITY_THRESHOLD

# ----------------------------------------------------------------------
# helpers identical to ingest-CPA code (kept local to avoid circular deps)
# ----------------------------------------------------------------------
_INCHI_PAT = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$", re.I)

def _is_valid_inchikey(k: str | None) -> bool:
    return bool(k and _INCHI_PAT.match(k))

def _canon(text: str) -> str:
    return text.strip().lower()


# ----------------------------------------------------------------------
# value-mapping helper
# ----------------------------------------------------------------------
def _value_kind_and_columns(val: Any) -> Tuple[str, Dict[str, Any]]:
    if isinstance(val, (int, float)):
        return "POINT", {"numeric_value": val}
    if isinstance(val, str):
        return "RAW", {"raw_value": val}

    vtype = val.get("value_type")
    if vtype == "point":
        return "POINT", {"numeric_value": val["value"]}
    if vtype == "range":
        return "RANGE", {"range_min": val["min"], "range_max": val["max"]}

    return "STRUCT", {"extra": json.dumps(val)}


# ----------------------------------------------------------------------
# chemical resolution (InChIKey ► exact  ·  name ► embedding)
# ----------------------------------------------------------------------
_EMBED_SQL = """
SELECT chemical_id, alias, embedding <-> %s::vector AS dist
FROM   cpa_chemical_aliases
ORDER  BY dist
LIMIT  1;
"""

def _resolve_chemical_id(cur, inchikey: str | None, label: str) -> UUID | None:
    # 1. exact InChIKey
    if _is_valid_inchikey(inchikey):
        cur.execute("SELECT id FROM cpa_chemicals WHERE inchikey = %s;", (inchikey,))
        row = cur.fetchone()
        if row:
            return row["id"]

    # 2. semantic alias match
    vec = get_embedding(_canon(label))
    cur.execute(_EMBED_SQL, (vec,))
    row = cur.fetchone()
    if row and row["dist"] < SIMILARITY_THRESHOLD:
        return row["chemical_id"]

    return None


# ----------------------------------------------------------------------
# main API
# ----------------------------------------------------------------------
def insert_agent_properties(
    paper_id: str,
    props: List[Dict[str, Any]],
) -> None:
    """
    Insert each AgentProperty into
      chemical_properties → chemical_property_values → cpa_references
    If the chemical cannot be resolved, the property is skipped.
    """
    if not props:
        return

    skipped = 0
    with cursor_ctx(commit=True) as cur:
        print(f'[TRACE] insert_agent_properties:')
        for p in props:
            print(f'\t{p}')
            chem_id = _resolve_chemical_id(cur, p.get("agent_id"), p["agent_label"])
            if chem_id is None:
                skipped += 1
                continue   # cannot attach property

            # 1. ensure header row exists
            cur.execute(
                """
                INSERT INTO chemical_properties (chemical_id, prop_type)
                VALUES (%s, %s::property_type)
                ON CONFLICT (chemical_id, prop_type) DO NOTHING
                RETURNING id;
                """,
                (chem_id, p["prop_type"]),
            )
            row = cur.fetchone()
            if row:
                prop_id = row["id"]
            else:
                cur.execute(
                    "SELECT id FROM chemical_properties "
                    "WHERE chemical_id = %s AND prop_type = %s::property_type",
                    (chem_id, p["prop_type"]),
                )
                prop_id = cur.fetchone()["id"]

            # 2. value row
            kind, colmap = _value_kind_and_columns(p["value"])
            columns = ["property_id", "value_kind", *colmap.keys(), "unit"]
            values  = [prop_id, kind, *colmap.values(), p.get("unit")]

            cols_sql = ", ".join(columns)
            ph_sql   = ", ".join(["%s"] * len(values))

            cur.execute(
                f"INSERT INTO chemical_property_values ({cols_sql}) "
                f"VALUES ({ph_sql}) RETURNING id;",
                tuple(values),
            )
            val_id = cur.fetchone()["id"]

            # 3. provenance
            cur.execute(
                """
                INSERT INTO cpa_references (property_value_id, paper_id, quote)
                VALUES (%s, %s, %s);
                """,
                (val_id, paper_id, p["quote"]),
            )

    if skipped:
        print(f"[WARN] insert_agent_properties: {skipped} properties skipped "
              f"(chemical not found via InChIKey or embedding)")