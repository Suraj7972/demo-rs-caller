"""Run the DB repository tests on a throwaway embedded Postgres (no Docker needed).

    uv run --with pgserver python infra/scripts/test_db_embedded.py [extra pytest args]

Starts Postgres in a temp dir, installs minimal Supabase stand-ins (auth/storage/roles),
applies supabase/migrations/*.sql in order, loads supabase/seed.sql, then runs pytest
with TEST_DATABASE_URL pointing at it. Prefer `supabase start` when Docker is available;
this exists so the suite runs on laptops/CI without it.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import asyncpg
import pgserver  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[2]
STUB = ROOT / "packages/shared/tests/db/supabase_stub.sql"
MIGRATIONS = sorted((ROOT / "supabase/migrations").glob("*.sql"))
SEED = ROOT / "supabase/seed.sql"


async def apply_sql(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        for sql_file in [STUB, *MIGRATIONS, SEED]:
            print(f"applying {sql_file.relative_to(ROOT)}")
            await conn.execute(sql_file.read_text(encoding="utf-8"))  # raises on any error
    finally:
        await conn.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="propcall-pg-") as data_dir:
        server = pgserver.get_server(data_dir, cleanup_mode="stop")
        try:
            asyncio.run(apply_sql(server.get_uri()))
            env = {
                **os.environ,
                "TEST_DATABASE_URL": server.get_uri(),
                # no tz database in this build; POSIX spec for IST (UTC+05:30, no DST)
                "TEST_DB_TZ": "<+0530>-05:30",
            }
            cmd = [sys.executable, "-m", "pytest", "packages/shared/tests/db", *sys.argv[1:]]
            return subprocess.call(cmd, cwd=ROOT, env=env)  # noqa: S603 (fixed argv)
        finally:
            server.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
