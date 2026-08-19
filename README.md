# TRADEVERSE

Multiplayer stock market simulation for live events (~40–50 participants). Humans and AI agents trade through a real **order book** and **matching engine**. Prices come from **executed trades** — everyone sees the same market because one cloud database and one API worker serve all devices.

**Deploy:** [DEPLOYMENT.md](DEPLOYMENT.md) (Vercel + Supabase + Railway)

---

## Live URLs (after deploy)

| Role | Path |
|------|------|
| Participants | `https://your-app.vercel.app/terminal` |
| Admin / host | `https://your-app.vercel.app/admin` |
| Projector screen | `https://your-app.vercel.app/market-screen` |
| API health | `https://your-api.up.railway.app/api/v1/health` |

---

## Features

- **Terminal** — join with a name, BUY NOW / SELL NOW, wallet, holdings, leaderboard, IPOs, news
- **Admin** — START / STOP / RESET simulation, timeline checkpoints, released news
- **Market screen** — public phase clock, sector matrix, latest headline (no auth)
- **Backend** — 3-hour TRADEVERSE timeline, 40-stock universe, AI traders, conditional orders, WebSocket live updates

---

## Architecture

- **Vercel** — Next.js 15 frontend
- **Supabase** — PostgreSQL (single source of truth)
- **Railway / Render** — Python FastAPI worker (simulation + matching + WebSockets)

Trading logic is **never** on the client. Portfolio, prices, and leaderboard are always fetched from the API.

---

## Development

See [DEPLOYMENT.md § Local development](DEPLOYMENT.md#6-local-development-optional). Run tests:

```bash
cd backend && pip install -r requirements.txt && pytest
cd frontend && npm ci && npm run lint && npm run build
```

---

## Docs

- [DEPLOYMENT.md](DEPLOYMENT.md) — cloud setup
- [supabase/README.md](supabase/README.md) — database migration
- [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) — pre-event checklist
- [docs/MASTER_PLAN.pdf](docs/MASTER_PLAN.pdf) — product spec
