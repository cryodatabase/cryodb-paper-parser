"""
COPY raw JSON rows into a staging table.

Relies on:
    • distiller.postgres_connection.cursor_ctx
    • psycopg 3.1+
"""
from __future__ import annotations
import io, json
from psycopg import sql
from distiller.postgres_connection import cursor_ctx


def copy_json(rows: list[dict], staging_table: str) -> None:
    """
    Bulk‑insert a list of JSON‑serialisable dicts into `<staging_table>`,
    using `COPY … FROM STDIN` for maximum throughput.
    """
    if rows == []:
        raise Exception("No rows to copy")
    if not rows:
        return

    # Minified newline‑separated JSON for COPY
    payload = "\n".join(json.dumps(r, separators=(",", ":")) for r in rows)

    with cursor_ctx(commit=True) as cur:
        # Safely quote the table name
        stmt = sql.SQL("COPY {} (data_json) FROM STDIN").format(
            sql.Identifier(staging_table)
        )

        # Context‑manager copy object
        with cur.copy(stmt) as copy:
            copy.write(payload) 