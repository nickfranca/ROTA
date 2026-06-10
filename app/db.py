from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import DATABASE_URL


pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row},
    open=False,
)


def open_pool() -> None:
    if pool.closed:
        pool.open()
        pool.wait()


def close_pool() -> None:
    if not pool.closed:
        pool.close()


@contextmanager
def connection() -> Iterator[Connection]:
    open_pool()
    with pool.connection() as conn:
        yield conn


def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, params)
        return list(cursor.fetchall())


def fetch_one(query: str, params: tuple = ()) -> dict:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchone() or {}
