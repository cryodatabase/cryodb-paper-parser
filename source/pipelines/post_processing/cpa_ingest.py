"""
Utility that ingests the JSON produced by the LLM pipeline
into the 4‑table normalised store.
"""
from __future__ import annotations
import re
import json, hashlib
from typing import Dict, Any
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from distiller.schemas.cpa_chemical import (
    CPAChemical, ChemicalPropertyValue)
from distiller.schemas.structured_output import CPAPaperData
from distiller.postgres_connection import connection_ctx
from pipelines.utils.embeddings import get_embedding
SIMILARITY_THRESHOLD = 0.38
_INCHI_PAT = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$", re.I)

def _is_valid_inchikey(k: str | None) -> bool:
    return bool(k and _INCHI_PAT.match(k))

def _canon(text: str) -> str:
    """Return the canonical form used for dedup + embedding."""
    return text.strip().lower()

def _upsert_aliases(cur, chem_id: str, preferred: str, syns: list[str]) -> None:
    """
    • Insert the preferred name (is_preferred = True)
    • Insert each synonym once (is_preferred = False)
    • Skip duplicates within the same call
    • Use the canonical text to compute the embedding
    """
    seen: set[str] = set()

    # Step 1: Enqueue names with preference flags
    names_with_preference: list[tuple[str, bool]] = []
    names_with_preference.append((preferred, True))
    for synonym in syns:
        names_with_preference.append((synonym, False))

    # Step 2: Process names, skipping canonical duplicates
    for name, is_preferred in names_with_preference:
        canonical_name = _canon(name)
        if canonical_name in seen:
            continue
        seen.add(canonical_name)

        vec = get_embedding(canonical_name)
        cur.execute(
            """
            INSERT INTO cpa_chemical_aliases
              (chemical_id, alias, embedding, is_preferred)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (chem_id, name, vec, is_preferred),
        )

def _upsert_chemical(cur, chem: CPAChemical, paper_id: str | None = None) -> str:
    """Safe upsert: semantic → attach valid, unique InChIKey → fallback."""
    canon_name = _canon(chem.preferred_name)
    q_vec      = get_embedding(canon_name)

    # ── 1.  semantic match in alias table  ──────────────────────────
    cur.execute(
        """
        SELECT chemical_id, alias, embedding <-> %s::vector AS dist
        FROM   cpa_chemical_aliases
        ORDER  BY dist
        LIMIT  1;
        """,
        (q_vec,),
    )
    row = cur.fetchone()
    if row and row["dist"] < SIMILARITY_THRESHOLD:
        chem_id = row["chemical_id"]

        _upsert_aliases(cur, chem_id, chem.preferred_name, chem.synonyms)
        return chem_id

    # ── 2.  No semantic hit → try InChIKey upsert if key looks OK ───
    if _is_valid_inchikey(chem.inchikey):
        cur.execute(
            """
            INSERT INTO cpa_chemicals (inchikey, preferred_name, embedding)
            VALUES (%s, %s, %s)
            ON CONFLICT (inchikey) DO UPDATE
              SET preferred_name = EXCLUDED.preferred_name,
                  embedding      = EXCLUDED.embedding
            RETURNING id;
            """,
            (chem.inchikey, chem.preferred_name, q_vec),
        )
        chem_id = cur.fetchone()["id"]
        _upsert_aliases(cur, chem_id, chem.preferred_name, chem.synonyms)
        return chem_id

    # ── 3.  Last resort: new row without inchikey + log suspect key ─
    print(f"[TRACE] Inserting chemical: '{chem.preferred_name}' (no InChIKey) distance: {row['dist']} compared with: '{row['alias']}')")
    cur.execute(
        """
        INSERT INTO cpa_chemicals (preferred_name, embedding)
        VALUES (%s, %s)
        ON CONFLICT (preferred_name) DO UPDATE
          SET embedding = EXCLUDED.embedding
        RETURNING id;
        """,
        (chem.preferred_name, q_vec),
    )
    chem_id = cur.fetchone()["id"]
    _upsert_aliases(cur, chem_id, chem.preferred_name, chem.synonyms)

    # Store the hallucinated or malformed key for later inspection
    if chem.inchikey:
        cur.execute(
            "INSERT INTO cpa_unverified_inchikeys "
            "(supplied_key, source_paper, note) VALUES (%s, %s, %s)",
            (
                chem.inchikey,
                paper_id,
                "Failed validation or duplicate; not stored in chemicals table.",
            ),
        )
    return chem_id
def _get_property_id(cur, chemical_id: str, ptype: PropertyType) -> str:
    """
    Ensure (chemical_id, prop_type) exists in `chemical_properties`
    and return its UUID.

    • INSERT if missing.
    • Otherwise fetch the existing row.
    """
    cur.execute(
        """
        INSERT INTO chemical_properties (chemical_id, prop_type)
        VALUES (%s, %s)
        ON CONFLICT (chemical_id, prop_type) DO NOTHING
        RETURNING id;
        """,
        (chemical_id, ptype.value),
    )
    row = cur.fetchone()
    if row:                      # inserted just now
        return row["id"]

    # already existed → fetch
    cur.execute(
        "SELECT id FROM chemical_properties WHERE chemical_id = %s AND prop_type = %s",
        (chemical_id, ptype.value),
    )
    return cur.fetchone()["id"]

def _get_property_value_id(
    cur, prop_id: str, cpv: ChemicalPropertyValue
) -> str:
    try:
        cur.execute(
            """
            INSERT INTO chemical_property_values
              (property_id, value_kind, numeric_value, range_min, range_max,
               raw_value, extra, unit)
        VALUES
          (%(property_id)s,%(value_kind)s,%(numeric_value)s,%(range_min)s,
           %(range_max)s,%(raw_value)s,%(extra)s,%(unit)s)
        RETURNING id;
        """,
        {
            "property_id": prop_id,
            "value_kind": cpv.value_kind.value,
            "numeric_value": cpv.numeric_value,
            "range_min": cpv.range_min,
            "range_max": cpv.range_max,
            "raw_value": cpv.raw_value,
            "extra": json.dumps(cpv.extra) if cpv.extra is not None else None,
            "unit": cpv.unit,
        },
        )   
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute(
            """
            SELECT id FROM chemical_property_values
            WHERE property_id = %s
            """,
            (prop_id,),
        )
        return cur.fetchone()["id"]
    except Exception as e:
        print(f"[WARN] Failed to insert property value: {e}")
        return None


def store_cpa_data(md5_hash: str) -> None:
    """
    Fetch `cpa_facts_json` for one paper and persist all AgentProperty
    objects into the normalised CPA tables.
    """
    print(f'[TRACE] store_cpa_data: {md5_hash}')
    with connection_ctx() as conn, conn.cursor(row_factory=dict_row) as cur:
        # 1. pull JSON
        cur.execute(
            "SELECT cpa_facts_json, doi FROM papers WHERE md5_hash = %s", (md5_hash,)
        )
        row = cur.fetchone()
        if not row or not row["cpa_facts_json"]:
            raise RuntimeError(f"No CPA facts stored for md5={md5_hash}")

        paper_json: Dict[str, Any] = row["cpa_facts_json"]
        paper = CPAPaperData.model_validate(paper_json)
        now = datetime.now()
        # 2. loop over agent properties
        for ap in paper.agent_properties:
            # 2.1 ensure chemical row exists
            chem = CPAChemical(
                inchikey=ap.agent_id,
                preferred_name=ap.agent_label,
                synonyms=[],
            )
            chemical_id = _upsert_chemical(cur, chem, row["doi"])

            # 2.2 ensure (chemical, prop_type) row exists
            prop_id = _get_property_id(cur, chemical_id, ap.prop_type)

            # 2.3 build value row
            cpv = ChemicalPropertyValue.from_fact_value(
                property_id=prop_id,
                value=ap.value,
                unit=ap.unit,
                created_at=now,
            )
            prop_val_id = _get_property_value_id(cur, prop_id, cpv)

            if row['doi']:
                paper_id = row['doi']
            else:
                paper_id = paper.paper_id
            # 2.4 always add reference (duplicates are negligible)
            cur.execute(
                """
                INSERT INTO cpa_references
                    (property_value_id, paper_id, quote, link)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING    -- idempotent if you later add UNIQUE
                """,
                (
                    prop_val_id,
                    paper_id,
                    ap.quote,
                    str(paper_id) if paper_id is not None else None,
                ),
            )

        conn.commit()
