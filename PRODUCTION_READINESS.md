# Production readiness — TRADEVERSE (cloud)

Use this checklist before a live event. Deployment target: **Vercel + Supabase + Railway** (see [DEPLOYMENT.md](DEPLOYMENT.md)).

## Infrastructure

- [ ] Supabase project created; `alembic upgrade head` succeeded on production `DATABASE_URL`
- [ ] API worker: **1 replica**, `workers=1`, health `/api/v1/health` returns `database: ok`
- [ ] Vercel: `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` point to API worker (HTTPS/WSS)
- [ ] `CORS_ORIGINS` includes production Vercel URL (and preview pattern if testing previews)
- [ ] `JWT_SECRET` and `ADMIN_SECRET` are strong, unique secrets (not defaults)
- [ ] `SIMULATION_SPEED=1` for live event (`60` only for rehearsal)

## Pre-event

- [ ] Admin **RESET** → `"Canonical stock universe loaded successfully"`
- [ ] Do **not** press START until go-live
- [ ] Supabase backup taken after final RESET
- [ ] Load test: `python backend/scripts/load_test_50_users.py --base-url https://your-api... --users 50`
- [ ] Sync smoke test: `python backend/scripts/smoke_test_sync.py --base-url https://your-api...`

## Multi-device sync verification

- [ ] Three browsers join as different traders — same LTP on all screens after a trade
- [ ] Trade on device A → device B wallet updates within ~2s (WebSocket)
- [ ] Admin START → all terminals show trading enabled
- [ ] Market screen phase/news matches admin status

## During event

- [ ] Do not redeploy API worker mid-simulation (in-memory order books)
- [ ] Monitor API logs and Supabase connection pool
- [ ] Keep laptop/plugged power if hosting admin from a local browser (participants use Vercel URL only)

## Removed deployment modes

Local Docker, LAN nginx, OCI VM, and ngrok workflows are **not supported** in this branch. All participants connect via the public Vercel URL.
