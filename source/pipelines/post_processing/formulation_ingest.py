# pipelines/post_processing/formulation_ingest.py
from __future__ import annotations

import json
import re
from typing import List, Dict, Any, Tuple
from uuid import UUID
from pipelines.utils.pipeline_utils import resolve_alias_id

from distiller.postgres_connection import cursor_ctx
from psycopg.types.json import Json
from pipelines.utils.embeddings import (
    get_embedding,
    SIMILARITY_THRESHOLD,
)
def insert_placeholder_chemical(
    cur,
    *,
    label: str,
    role: str = "CARRIER",   # CPA | ADJUVANT | CARRIER
) -> tuple[UUID, UUID]:
    """
    Ensure a stub chemical & its preferred alias exist, then return
    (alias_id, chemical_id).

    • If the alias already exists globally, re-use it (and its chemical).
    • Otherwise: create a new chemical (inchikey = NULL, role = <role>)
      and make <label> its preferred alias.
    """
    canon = label.strip().lower()
    emb   = get_embedding(canon)

    # 0️⃣  Does the alias already exist globally?
    cur.execute(
        "SELECT id, chemical_id FROM cpa_chemical_aliases WHERE alias = %s;",
        (label,),
    )
    row = cur.fetchone()
    if row:
        return row["id"], row["chemical_id"]

    # 1️⃣  Create a stub chemical
    cur.execute(
        """
        INSERT INTO cpa_chemicals
              (inchikey, preferred_name, role, embedding)
        VALUES (NULL, %s, %s::cryoprotectant_roles, %s)
        RETURNING id;
        """,
        (label, role, emb),
    )
    chemical_id: UUID = cur.fetchone()["id"]

    # 2️⃣  Insert preferred alias (guaranteed unique now)
    cur.execute(
        """
        INSERT INTO cpa_chemical_aliases
              (chemical_id, alias, embedding, is_preferred)
        VALUES (%s, %s, %s, TRUE)
        RETURNING id;
        """,
        (chemical_id, label, emb),
    )
    alias_id: UUID = cur.fetchone()["id"]

    return alias_id, chemical_id

# ───────────────────────── generic helpers ─────────────────────────

def _paper_uuid_from_md5(cur, md5_hash: str) -> str | None:
    cur.execute("SELECT id FROM papers WHERE md5_hash = %s;", (md5_hash,))
    r = cur.fetchone()
    return r["id"] if r else None

def _experiment_uuid_from_map_or_db(
    cur, paper_uuid: str, local_id: str, experiments: dict[str, str] | None
) -> str | None:

    cur.execute(
        "SELECT id FROM experiments "
        "WHERE paper_id = %s AND local_id = %s;",
        (paper_uuid, local_id),
    )
    row = cur.fetchone()
    return row["id"] if row else None

def _amount_as_columns(
    amt: dict | float | int | None,
) -> Tuple[float | None, float | None, float | None, str | None]:
    if amt is None:
        return None, None, None, None
    if isinstance(amt, (int, float)):
        return float(amt), None, None, "POINT"

    vtype = amt.get("value_type")
    if vtype == "point":
        return amt["value"], None, None, "POINT"
    if vtype == "range":
        return None, amt["min"], amt["max"], "RANGE"

    return None, None, None, "STRUCT"

# ─────────────────────────── ingest API ────────────────────────────

def insert_formulations(
    paper_md5: str,
    formulations: List[Dict[str, Any]],
    experiments: dict[str, str] | None = None,
) -> None:
    if not formulations:
        return

    with cursor_ctx(commit=True) as cur:
        paper_uuid = _paper_uuid_from_md5(cur, paper_md5)
        if paper_uuid is None:
            raise RuntimeError(f"No `papers` row for md5={paper_md5}")

        for f in formulations:
            experiment_id = _experiment_uuid_from_map_or_db(
                cur, paper_uuid, f["experiment_id"], experiments
            )
            if experiment_id is None:
                print(
                    f"[WARN] formulation skipped – "
                    f"experiment {f['experiment_id']} not found for paper {paper_md5}"
                )
                continue

            # 1️⃣  formulation header
            cur.execute(
                """
                INSERT INTO formulations (experiment_id, label, quote)
                VALUES (%s, %s, %s)
                ON CONFLICT (experiment_id, label) DO UPDATE
                      SET quote = EXCLUDED.quote
                RETURNING id;
                """,
                (experiment_id, f["label"], f["quote"]),
            )
            formulation_id = cur.fetchone()["id"]

            # 2️⃣  components
            comp_rows: list[Tuple] = []
            prop_to_create: list[Tuple] = []   # (comp_dict, aux_tuple)

            for comp in f["components"]:
                # alias / chemical resolution for CPA + ADJUVANT
                alias_id, chem_id = (None, None)
                if comp["role"] in ("CPA", "ADJUVANT"):
                    alias_id, chem_id = resolve_alias_id(
                        cur,
                        inchikey = comp.get("agent_id"),
                        label    = comp["label"],
                    )
                if chem_id is None:
                    alias_id, chem_id = insert_placeholder_chemical(
                        cur,
                        label = comp["label"],
                        role  = comp["role"],
                    )

                num_val, rng_min, rng_max, vkind = _amount_as_columns(comp.get("amount"))

                comp_rows.append(
                    (
                        formulation_id,
                        comp["role"],
                        chem_id,   # may be NULL
                        alias_id,  # may be NULL
                        num_val,
                        comp.get("unit"),
                        comp["quote"],
                        comp.get("note"),
                    )
                )

                if vkind in ("RANGE", "STRUCT"):
                    prop_to_create.append((comp, (rng_min, rng_max, vkind, alias_id)))

            if comp_rows:
                cur.executemany(
                    """
                    INSERT INTO formulation_components
                           (formulation_id, role, chemical_id, alias_id,
                            amount, unit, quote, note)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING;
                    """,
                    comp_rows,
                )

            # map alias_id → component_id
            cur.execute(
                """
                SELECT id, alias_id
                  FROM formulation_components
                 WHERE formulation_id = %s;
                """,
                (formulation_id,),
            )
            alias_to_compid = {r["alias_id"]: r["id"] for r in cur.fetchall()}

            # 3️⃣  dependent props for RANGE / STRUCT
            for comp_dict, (rmin, rmax, vkind, alias_id) in prop_to_create:
                comp_id = alias_to_compid.get(alias_id)
                if comp_id is None:
                    continue   # defensive; should not happen

                # 3.a header
                cur.execute(
                    """
                    INSERT INTO formulation_properties
                           (experiment_id, component_id, prop_type)
                    VALUES (%s, %s, 'LOADING_TEMPERATURE')
                    ON CONFLICT (experiment_id, prop_type,
                                 formulation_id, component_id)
                    DO NOTHING
                    RETURNING id;
                    """,
                    (experiment_id, comp_id),
                )
                prop_id = cur.fetchone()["id"]

                # 3.b value row
                cur.execute(
                    """
                    INSERT INTO formulation_property_values
                           (property_id, value_kind,
                            range_min, range_max, extra, unit)
                    VALUES (%s,%s,%s,%s,%s,%s);
                    """,
                    (
                        prop_id,
                        vkind,
                        rmin,
                        rmax,
                        Json(comp_dict["amount"]) if vkind == "STRUCT" else None,
                        comp_dict.get("unit"),
                    ),
                )

# NOTE: make sure you ran the schema patch:
#   ALTER TABLE formulation_components
#     ADD COLUMN IF NOT EXISTS alias_id uuid,
#     ADD CONSTRAINT fk_formcomp_alias
#         FOREIGN KEY (alias_id)
#         REFERENCES cpa_chemical_aliases(id) ON DELETE RESTRICT;
#   CREATE INDEX IF NOT EXISTS idx_formcomp_alias
#       ON formulation_components(alias_id);
