# ──────────────────────────────────────────────────────────────────
# Evaluation logger  ➜  playground_evaluation
# ──────────────────────────────────────────────────────────────────
import json
import uuid
from typing import Optional
from distiller.postgres_connection import connection_ctx

def run_evaluation(
    *,
    extractor_model: str,                  # model that produced the extraction
    agents: dict,                          # value of `agents`  (aliases)
    props:  dict | list,                   # value of `props`   (properties)
    experiments: dict | list,              # value of `experiments`
    formulations: dict | list,             # value of `formulations`
    judge_model: Optional[str] = None,     # model used for grading (optional)
) -> int:
    """
    Persists a single extraction package into `playground_evaluation`
    and returns the inserted row id.
    """
    print(f"[TRACE] Running evaluation for {extractor_model}")
    # ---- 1.  normalise the four payload sections ----------------------
    def _unwrap(node, key):
        """
        Accept either a plain list *or* a wrapper object and always
        return a list.  Raises if key is missing.
        """
        if node is None:
            return []
        if isinstance(node, list):
            return node
        if isinstance(node, dict):
            if key not in node:
                raise KeyError(f"expected key '{key}' in {node.keys()}")
            return node[key]
        raise TypeError(f"Unsupported payload type for {key}: {type(node)}")

    extracted_data = {
        # Up‑convert aliases: the DSL returns {"agents": [...]}
        "agents_aliases":   _unwrap(agents,       "agents"),
        "agents_properties": _unwrap(props,       "properties"),
        "experiments":      _unwrap(experiments,  "experiments"),
        "formulations":     _unwrap(formulations, "formulations"),
    }

    # ---- 2.  insert row ------------------------------------------------
    insert_sql = """
        INSERT INTO playground_evaluation
            (extractor_model, judge_model, extracted_data)
        VALUES
            (%(ext)s, %(judge)s, %(payload)s::jsonb)
        RETURNING id;
    """

    params = dict(
        ext     = extractor_model,
        judge   = judge_model,
        payload = json.dumps(extracted_data),
    )

    with connection_ctx() as conn, conn.cursor() as cur:
        cur.execute(insert_sql, params)
        new_id: int = cur.fetchone()[0]
        conn.commit()
        return new_id