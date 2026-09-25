"""asyncpg connection pool for the backend services.

Backend services connect with the Postgres connection string (SUPABASE_DB_URL), which
bypasses RLS. Tenant isolation is therefore enforced by the repositories, which always
take an org_id. The dashboard goes through supabase-js and RLS instead.
"""

import json
from urllib.parse import urlparse

import asyncpg

# Supabase's transaction-mode pooler (Supavisor, port 6543) does not support
# prepared statements, so asyncpg's statement cache must be off there.
_TRANSACTION_POOLER_PORT = 6543


async def init_connection(conn: asyncpg.Connection) -> None:
    """Decode json/jsonb to Python objects and encode dicts/lists back."""
    for typename in ("json", "jsonb"):
        await conn.set_type_codec(
            typename,
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )


def _connect_kwargs(dsn: str) -> dict[str, object]:
    kwargs: dict[str, object] = {"init": init_connection}
    if urlparse(dsn).port == _TRANSACTION_POOLER_PORT:
        kwargs["statement_cache_size"] = 0
    return kwargs


async def create_pool(dsn: str, *, min_size: int = 1, max_size: int = 10) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(
        dsn, min_size=min_size, max_size=max_size, **_connect_kwargs(dsn)
    )
    if pool is None:  # only None when used as an un-awaited context manager
        raise RuntimeError("asyncpg.create_pool returned None")
    return pool


async def connect(dsn: str) -> asyncpg.Connection:
    """Single connection (scripts, tests) with the same codecs as the pool."""
    kwargs = _connect_kwargs(dsn)
    kwargs.pop("init")
    conn = await asyncpg.connect(dsn, **kwargs)
    await init_connection(conn)
    return conn
