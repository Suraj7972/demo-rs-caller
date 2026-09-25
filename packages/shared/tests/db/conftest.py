"""Repository tests run against a real Postgres that has the migrations + seed applied.

- Local Supabase:  `supabase start`, then
      TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres make test
- No Docker:       `uv run --with pgserver python infra/scripts/test_db_embedded.py`

Every test runs inside a transaction that is rolled back, so the DB is left untouched.
Never point TEST_DATABASE_URL at production.
"""

import os
from collections.abc import AsyncIterator
from uuid import UUID

import asyncpg
import pytest

from shared.db import connect

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# Fixed ids from supabase/seed.sql
BUILDER_ORG = UUID("11111111-1111-4111-8111-111111111111")
BROKER_ORG = UUID("22222222-2222-4222-8222-222222222222")
PROJECT_HINJEWADI = UUID("aaaaaaaa-0000-4000-8000-000000000001")
PROJECT_KHARADI = UUID("aaaaaaaa-0000-4000-8000-000000000002")
CAMPAIGN_BUILDER = UUID("cccccccc-0000-4000-8000-000000000001")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set (see tests/db/conftest.py)")
    for item in items:
        if "tests/db/" in item.nodeid.replace("\\", "/"):
            item.add_marker(skip)


@pytest.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    assert TEST_DATABASE_URL
    conn = await connect(TEST_DATABASE_URL)
    tx = conn.transaction()
    await tx.start()
    try:
        yield conn
    finally:
        await tx.rollback()
        await conn.close()
