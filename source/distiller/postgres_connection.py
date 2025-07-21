from __future__ import annotations
import os
from contextlib import contextmanager
from typing import Iterator, Generator, Optional, Any
import psycopg
from psycopg import Connection as _PGConnection
from psycopg import Cursor as _PGCursor


_DB_NAME: str = os.getenv("PGDATABASE", "postgres")
_DB_USER: str = os.getenv("PGUSER", "postgres")
_DB_PASSWORD: str = os.getenv("PGPASSWORD", "postgres")
_DB_HOST: str = os.getenv("PGHOST", "localhost")
_DB_PORT: str | int = os.getenv("PGPORT", "5432")  # int or str OK for psycopg


def get_connection(
    dbname: str | None = None,
    user: str | None = None,
    password: str | None = None,
    host: str | None = None,
    port: str | int | None = None,
) -> _PGConnection:
    return psycopg.connect(
        dbname=dbname or _DB_NAME,
        user=user or _DB_USER,
        password=password or _DB_PASSWORD,
        host=host or _DB_HOST,
        port=port or _DB_PORT,
    )


@contextmanager
def connection_ctx(**kwargs: Any) -> Generator[_PGConnection, None, None]:
    conn = get_connection(**kwargs)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def cursor_ctx(commit: bool = False, **kwargs: Any) -> Generator[_PGCursor, None, None]:
    with connection_ctx(**kwargs) as conn:
        cur = conn.cursor()
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


__all__ = [
    "get_connection",
    "connection_ctx",
    "cursor_ctx",
]