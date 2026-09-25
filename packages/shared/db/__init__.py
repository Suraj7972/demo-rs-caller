"""Database access: pydantic row models + thin asyncpg repositories.

Why asyncpg (not supabase-py) for the backend:
- The voice path is latency-critical; asyncpg talks the Postgres wire protocol directly
  (no extra HTTP hop through PostgREST) and is natively async.
- We need real transactions and row locks (e.g. site-visit capacity), which PostgREST
  can't express without writing RPC functions for each case.
- supabase-py is still used where Supabase-specific APIs are needed (Storage uploads).
The dashboard uses supabase-js + RLS; the backend uses the DB URL and scopes by org_id.
"""

from shared.db.pool import connect, create_pool, init_connection

__all__ = ["connect", "create_pool", "init_connection"]
