# TRADEVERSE deployment guide

See also [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for the full pre-event checklist.

**Local LAN server (laptop hosts event):** see [LOCAL_SERVER.md](LOCAL_SERVER.md) — HTTP on port 80, same Wi‑Fi participants.

**Oracle Cloud Always Free (₹0 / $0):** see [OCI_DEPLOYMENT.md](OCI_DEPLOYMENT.md) for Docker Compose + Nginx + PostgreSQL on a single Ubuntu VM.

## Architecture audit (Railway target)

| Layer | Component | Notes |
|-------|-----------|-------|
| Frontend | Next.js 15 (App Router) | `/terminal`, `/admin`, `/market-screen`; standalone Docker build |
| Backend | FastAPI + uvicorn | Prefix `/api/v1`; in-process simulation worker |
| Database | PostgreSQL (Railway plugin) | Alembic baseline migration; `AUTO_INIT_DB=false` in prod |
| WebSockets | `GET /api/v1/ws?token=` | Public events to all; private events to authenticated participant only |
| Auth | JWT (`/auth/join`) + `ADMIN_SECRET` | Participant orders/wallet/portfolio require bearer token |
| Simulation | Postgres advisory lock | Fail-closed (`pg_try_advisory_lock`); `--workers 1` |

**Canonical universe:** `canonical_tradable_count()` tradable stocks at RESET + 5 IPO companies listed during simulation = `canonical_total_count()` (40). Derived from [`backend/app/seed/tradeverse_stocks.py`](backend/app/seed/tradeverse_stocks.py) — never hard-code counts.

**Operational constraints (v1):**

- Exactly **1 backend replica** and **1 uvicorn worker**
- Railway `DATABASE_URL` uses `postgresql://` — backend normalizes to `postgresql+psycopg://`
- Frontend `NEXT_PUBLIC_*` vars are **build-time** on Railway

**Manifests:** [`backend/railway.toml`](backend/railway.toml), [`frontend/railway.toml`](frontend/railway.toml)

---

## Railway deployment steps

### Backend service

- **Root directory:** `backend/`
- **Release command:** `alembic upgrade head` (runs once per deploy)
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
- **Health check:** `/api/v1/health`
- **Replicas:** 1

### SIMULATION_SPEED precedence

1. If `SIMULATION_SPEED` is **explicitly set** in the environment → overrides DB/admin speed
2. Otherwise → preserves DB/admin `sim_speed_multiplier`

Production event: `SIMULATION_SPEED=1`. Staging rehearsal: `SIMULATION_SPEED=60`.

### Pre-event RESET

Admin **RESET** returns `"Canonical stock universe loaded successfully"` with tradable count from source.

---

## Database backup (before live event)

1. Deploy final build; run release migration.
2. Admin **RESET** → verify canonical universe + timeline.
3. Run rehearsal with `SIMULATION_SPEED=60`.
4. Take PostgreSQL snapshot/backup (Railway plugin → backup, or `pg_dump`).
5. **RESET** again immediately before go-live.
6. Take final clean backup.

Do not rely on RESET as the only recovery method.

---

## Load testing

**Local:**

```bash
python backend/scripts/load_test_50_users.py --base-url http://localhost:8000 --users 50
```

**Cloud (required final test):**

```bash
python backend/scripts/load_test_50_users.py --base-url https://YOUR-API.up.railway.app --users 50
```

The script exercises: auth join, concurrent orders, wallet reads, bootstrap reconnect, leaderboard, and WebSocket connections (requires `websockets` package).

---

## Critical runtime rules

- Migrations via **release command** only — not on every server restart
- Participants join via `POST /api/v1/auth/join`; terminal stores bearer token
- WebSocket: append `?token=` for private wallet/portfolio updates
- After WS disconnect, terminal calls `GET /api/v1/session/bootstrap` to resync
- Open `POST /traders` disabled in production

## Health checks

| Path | Purpose |
|------|---------|
| `GET /api/v1/health` | Primary liveness (DB + sim status) |
| `GET /api/v1/ready` | Readiness (DB reachable) |
| `GET /api/v1/session/bootstrap` | Participant resync after reconnect |

## Docker Compose (local reference)

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

## Restart mid-simulation

On restart the engine reloads `SimulationState` and pending timeline rows. **EXECUTED** events are not re-run.
