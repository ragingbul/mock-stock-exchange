# TRADEVERSE Production Readiness Checklist

Use this checklist before a live ~50-participant event on Railway.

## Infrastructure

- [ ] Railway backend deployed (root: `backend/`, **1 replica**)
- [ ] Railway frontend deployed (root: `frontend/`)
- [ ] PostgreSQL connected (`DATABASE_URL` auto-normalized to `+psycopg`)
- [ ] Migrations run via **release command** (`alembic upgrade head`), not on every restart
- [ ] HTTPS working on frontend and API
- [ ] WSS working (`NEXT_PUBLIC_WS_URL` or derived from API URL)
- [ ] Health check: `GET /api/v1/health` returns `database: ok`

## Auth

- [ ] Participant authentication via `POST /api/v1/auth/join`
- [ ] Admin authentication via `ADMIN_SECRET` bearer
- [ ] Trader identity server-authoritative (JWT on orders/wallet/portfolio)
- [ ] Admin endpoints protected
- [ ] Open `POST /traders` disabled in production
- [ ] WebSocket private events require participant token (`?token=`)

## Market

- [ ] Canonical stock universe complete after RESET (`Canonical stock universe loaded successfully`)
- [ ] Tradable count matches source (`canonical_tradable_count()`)
- [ ] Every stock mapped to a sector (including metals + IPO listings)
- [ ] Sector averages correct on `/market/sectors`
- [ ] BUY / SELL work with JWT
- [ ] Wallet and P&L correct after trades

## Simulation

- [ ] One simulation worker (`--workers 1`, `numReplicas = 1`)
- [ ] Advisory lock fail-closed (`pg_try_advisory_lock`)
- [ ] `SIMULATION_SPEED=1` in production (explicit env override only)
- [ ] START / STOP / RESET via admin
- [ ] Timeline idempotency (EXECUTED events not replayed)
- [ ] News, AI, IPO, dissolution timeline-driven
- [ ] 03:00 completion (`sim_duration_sec`)

## Realtime

- [ ] WebSocket authentication (participant token)
- [ ] Public market screen receives public events only
- [ ] Terminal reconnect + `/session/bootstrap` resync
- [ ] Leaderboard / wallet / IPO state in bootstrap

## Reliability

- [ ] Local load test: `python backend/scripts/load_test_50_users.py --base-url http://localhost:8000 --users 50`
- [ ] Cloud load test against Railway HTTPS URL
- [ ] Simultaneous trades (50 users)
- [ ] Reconnect/bootstrap subset during load test
- [ ] IPO cycle rehearsal (`SIMULATION_SPEED=60` on staging)
- [ ] Dissolution checkpoint verified
- [ ] PostgreSQL backup taken before event (see DEPLOYMENT.md)

## Localhost audit (production bugs only)

| Location | Classification |
|----------|----------------|
| `frontend/src/lib/api.ts` | Dev fallback only; prod build requires `NEXT_PUBLIC_API_URL` |
| `backend/app/core/config.py` defaults | Dev-only; set env on Railway |
| `docker-compose.yml` localhost CORS | Local reference stack only |
| `.env.example` | Documentation |
| Load test `--base-url` default | CLI default for local runs |

## Remaining architectural constraints

- Single backend instance only (WS + sim worker in-memory)
- WS connect without token = public events only
- Restart mid-RUNNING resumes from DB state; EXECUTED timeline rows are not replayed
- Baseline Alembic migration only — future schema changes need new revisions
