"""
Utility that ingests the JSON produced by the LLM pipeline
into the 4‑table normalised store.
"""
from __future__ import annotations

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
SIMILARITY_THRESHOLD = 0.20            # cosine distance (0 = identical)

def _merge_synonyms(cur, chem_id: str, new_syns: List[str]) -> None:
    """
    Merge new synonyms into existing JSONB array; keeps them unique.
    """
    if not new_syns:
        return
    cur.execute(
        """
        UPDATE cpa_chemicals
        SET synonyms = (
              SELECT jsonb_agg(DISTINCT x)
              FROM   jsonb_array_elements_text(synonyms || %s::jsonb) AS t(x)
        )
        WHERE id = %s
        """,
        (json.dumps(new_syns), chem_id),
    )
# ----------------------------------------------------------------
def _upsert_chemical(cur, chem: CPAChemical) -> str:
    """
    Insert or update the chemical; return its UUID (text).
    inchikey is preferred unique key; fallback = preferred_name.
    """
    if chem.inchikey:
        cur.execute(
            """
            INSERT INTO cpa_chemicals (inchikey, preferred_name, synonyms, embedding)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (inchikey)
            DO UPDATE SET preferred_name = EXCLUDED.preferred_name,
            synonyms = EXCLUDED.synonyms,
            embedding = EXCLUDED.embedding
            RETURNING id;
            """,
            (chem.inchikey, chem.preferred_name, json.dumps(chem.synonyms), get_embedding(chem.preferred_name.lower())),
        )
        chem_id = cur.fetchone()["id"]
        _merge_synonyms(cur, chem_id, chem.synonyms)
        return chem_id

    # 2. Semantic path – no inchikey available
    query_vec = get_embedding(chem.preferred_name.lower())
    # nearest neighbour + its distance
    cur.execute(
        """
        SELECT id,
            embedding <-> %s::vector AS distance
        FROM   cpa_chemicals
        WHERE  embedding IS NOT NULL
        ORDER  BY distance
        LIMIT  1;
        """,
        (query_vec,),
    )
    row = cur.fetchone()
    if row and row["distance"] is not None:
        print(f'[TRACE] distance: {row["distance"]} for {chem}')
        if row["distance"] < SIMILARITY_THRESHOLD:
            chem_id = row["id"]
            _merge_synonyms(cur, chem_id, [chem.preferred_name, *chem.synonyms])
            return chem_id
    # 3. Truly new – insert
    print(f'[TRACE] Inserting new chemical: {chem}')
    cur.execute(
        """
        INSERT INTO cpa_chemicals (preferred_name, synonyms, embedding)
        VALUES (%s, %s, %s)
        RETURNING id;
        """,
        (
            chem.preferred_name,
            json.dumps(chem.synonyms),
            query_vec,
        ),
    )
    return cur.fetchone()["id"]


def _get_property_id(cur, chemical_id: str, ptype: PropertyType) -> str:
    print(f'[TRACE] _get_property_id: {chemical_id}, {ptype}')
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
    if row:                                # we inserted
        return row["id"]
    # already existed
    cur.execute(
        "SELECT id FROM chemical_properties WHERE chemical_id = %s AND prop_type = %s",
        (chemical_id, ptype.value),
    )
    return cur.fetchone()["id"]


def _get_property_value_id(
    cur, prop_id: str, cpv: ChemicalPropertyValue
) -> str:
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
    if row:            # inserted
        return row["id"]
    # already exists — retrieve id
    cur.execute(
        """
        SELECT id FROM chemical_property_values
        WHERE property_id = %s
        """,
        (prop_id,),
    )
    return cur.fetchone()["id"]


def store_cpa_data(md5_hash: str) -> None:
    """
    Fetch `cpa_facts_json` for one paper and persist all AgentProperty
    objects into the normalised CPA tables.
    """
    print(f'[TRACE] store_cpa_data: {md5_hash}')
    with connection_ctx() as conn, conn.cursor(row_factory=dict_row) as cur:
        # 1. pull JSON
        cur.execute(
            "SELECT cpa_facts_json FROM papers WHERE md5_hash = %s", (md5_hash,)
        )
        row = cur.fetchone()
        if not row or not row["cpa_facts_json"]:
            raise RuntimeError(f"No CPA facts stored for md5={md5_hash}")

        paper_json: Dict[str, Any] = row["cpa_facts_json"]
        paper = CPAPaperData.model_validate(paper_json)
        now = datetime.now()

        print(f'[TRACE] AGENT PROPERTIES: {paper.agent_properties}')
        # 2. loop over agent properties
        for ap in paper.agent_properties:
            # 2.1 ensure chemical row exists
            chem = CPAChemical(
                inchikey=ap.agent_id,
                preferred_name=ap.agent_label,
                synonyms=[],
            )
            chemical_id = _upsert_chemical(cur, chem)

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
                    paper.paper_id,
                    ap.quote,
                    str(paper.link) if paper.link is not None else None,
                ),
            )

        conn.commit()
