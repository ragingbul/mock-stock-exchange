# Supabase setup

TRADEVERSE uses **Supabase PostgreSQL** as the single source of truth. The Python API worker (Railway/Render) connects with a **direct** connection string; the Next.js frontend on Vercel talks to the API only (not directly to Postgres).

## 1. Create project

1. [supabase.com](https://supabase.com) → New project
2. Save the database password
3. Note **Project URL** and **anon/service** keys (for future optional Realtime/Auth)

## 2. Connection string (API worker)

In **Project Settings → Database → Connection string → URI** (Session mode / direct, port **5432**):

```
postgresql://postgres.[ref]:[password]@db.[ref].supabase.co:5432/postgres
```

Append `?sslmode=require` if not present.

Set as `DATABASE_URL` on Railway/Render. The backend normalizes `postgres://` → `postgresql+psycopg://`.

**Do not** use the transaction pooler (port 6543) for the simulation worker — advisory locks and long sessions need a direct connection.

## 3. Run migrations

From `backend/` with `DATABASE_URL` set:

```bash
pip install -r requirements.txt
alembic upgrade head
```

Or rely on Railway `releaseCommand` in [`backend/railway.toml`](../backend/railway.toml).

## 4. Optional: Realtime (phase 2)

Enable replication for read-heavy tables if you add Supabase Realtime clients later:

- `stocks`, `trades`, `traders`, `simulation_state`

**Order submission and matching stay on the API worker** — do not move trading logic to Edge Functions.

## 5. Backup

Use Supabase dashboard → Database → Backups, or `pg_dump` with the direct connection string before live events.
