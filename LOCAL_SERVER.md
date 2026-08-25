# TRADEVERSE Local Server (Docker + optional ngrok)

Run TRADEVERSE on your **laptop** with Docker. Participants can join via:

1. **Same Wi‑Fi (LAN)** — `http://YOUR_LAN_IP/...`
2. **Internet (ngrok)** — `https://….ngrok-free.dev/...` so people off your network can join

Oracle cloud files ([`OCI_DEPLOYMENT.md`](OCI_DEPLOYMENT.md), [`docker-compose.prod.yml`](docker-compose.prod.yml)) are **not used** in local mode.

---

## Architecture

```
YOUR LAPTOP (Docker)
├── nginx          → only service exposed on host :80  ← ngrok points here
├── frontend       → internal :3000
├── backend        → internal :8000, 1 uvicorn worker, 1 sim worker
└── postgres       → internal, persistent volume
```

WebSockets: `ws://` (LAN) or `wss://` (ngrok HTTPS) at `/api/v1/ws`, proxied through nginx.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) running (WSL2 backend OK on Windows)
- [ngrok](https://ngrok.com/download) installed **only if** you want to share outside your LAN
  - One-time: `ngrok config add-authtoken <your-token>` from the ngrok dashboard

---

## Quick start (Windows)

### 1. Create `.env`

From the repo root:

```powershell
.\scripts\local\setup-env.ps1
```

That copies [`.env.local.example`](.env.local.example), generates secrets, and prints `ADMIN_SECRET` (save it for `/admin`).

Leave `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` **empty** — same-origin auto works for localhost, LAN, and ngrok.

### 2. Start Docker stack

```powershell
.\scripts\local\start.ps1
```

First run builds images (can take several minutes). Then verify:

```powershell
.\scripts\local\health-check.ps1
```

| Page | URL |
|------|-----|
| Home | http://localhost/ |
| Terminal | http://localhost/terminal |
| Admin | http://localhost/admin |
| Market screen | http://localhost/market-screen |
| Health | http://localhost/api/v1/health |

### 3. Share over the internet (ngrok)

With the stack healthy:

```powershell
.\scripts\local\share.ps1
```

This starts `ngrok http 80` (if needed), reads the public HTTPS URL, writes it into `.env` (`CORS_ORIGINS`, `FRONTEND_URL`, `BACKEND_URL`), and restarts backend + nginx.

Share the printed links (example):

| Role | URL |
|------|-----|
| Participant | `https://….ngrok-free.dev/terminal` |
| Admin | `https://….ngrok-free.dev/admin` |
| Public screen | `https://….ngrok-free.dev/market-screen` |

**Notes**

- Free ngrok shows a one-time browser interstitial; the app sends `ngrok-skip-browser-warning` on API calls.
- If the ngrok URL changes, run `share.ps1` again (or `.\scripts\local\apply-public-url.ps1 https://NEW-URL`).
- Keep the laptop awake; do not close Docker or the ngrok process during the event.

### 4. Stop

```powershell
.\scripts\local\stop.ps1
```

Database volume `postgres_data_local` is **preserved**.

---

## Quick start (macOS / Linux)

```bash
./scripts/local/setup-env.sh
./scripts/local/start.sh
./scripts/local/health-check.sh
./scripts/local/share.sh          # optional: internet via ngrok
./scripts/local/stop.sh
```

---

## LAN only (same Wi‑Fi, no ngrok)

Find your LAN IP (`ipconfig` on Windows → IPv4 under Wi‑Fi), then:

```powershell
.\scripts\local\apply-public-url.ps1 http://192.168.1.42
```

Or edit `.env` manually:

```
CORS_ORIGINS=http://localhost,http://127.0.0.1,http://192.168.1.42
FRONTEND_URL=http://192.168.1.42
BACKEND_URL=http://192.168.1.42
```

Then restart backend:

```powershell
docker compose -f docker-compose.local.yml restart backend
```

| Role | URL |
|------|-----|
| Participant | http://192.168.x.x/terminal |
| Admin | http://192.168.x.x/admin |
| Public screen | http://192.168.x.x/market-screen |

### Windows Firewall

Allow inbound **TCP port 80** on your Private network profile:

1. Windows Security → Firewall & network protection → Advanced settings
2. Inbound Rules → New Rule → Port → TCP 80 → Allow → Private networks

Do **not** open 5432, 8000, or 3000.

---

## Manual Docker commands

```powershell
docker compose -f docker-compose.local.yml build
docker compose -f docker-compose.local.yml up -d postgres
docker compose -f docker-compose.local.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.local.yml up -d
```

---

## CORS when URL / LAN IP changes

1. Prefer `.\scripts\local\apply-public-url.ps1 <url>` (or `share.ps1` for ngrok)
2. Or edit `CORS_ORIGINS`, `FRONTEND_URL`, `BACKEND_URL` in `.env`, then:

```powershell
docker compose -f docker-compose.local.yml restart backend nginx
```

Frontend rebuild is **not** required (same-origin API resolution).

---

## Admin RESET (before event)

1. Open http://localhost/admin (or LAN admin URL)
2. Enter `ADMIN_SECRET` from `.env`
3. Press **RESET** → expect `"Canonical stock universe loaded successfully"` (~40 stocks)
4. **Do not press START** until the live event

---

## Simulation speed

| Mode | `SIMULATION_SPEED` |
|------|-------------------|
| Live event | `1` |
| Rehearsal | `60` (change in `.env`, restart backend) |

---

## Multi-device test

1. Laptop: http://localhost/terminal — join as participant A
2. Phone (same Wi‑Fi): http://\<LAN_IP\>/terminal — join as participant B
3. Second laptop: same URL — participant C
4. Verify: same prices, trades visible to all, leaderboard/P&L/news update via WebSocket
5. Admin START → close admin browser → simulation continues → reconnect admin shows current state

---

## Load test ramp

After basic checks pass:

```powershell
pip install httpx websockets
python backend/scripts/load_test_50_users.py --base-url http://192.168.x.x --users 1
python backend/scripts/load_test_50_users.py --base-url http://192.168.x.x --users 3
python backend/scripts/load_test_50_users.py --base-url http://192.168.x.x --users 5
python backend/scripts/load_test_50_users.py --base-url http://192.168.x.x --users 10
python backend/scripts/load_test_50_users.py --base-url http://192.168.x.x --users 50
```

Monitor resources:

```powershell
docker stats
```

---

## Event safety checklist

- Keep laptop **plugged in**
- Disable **sleep/hibernate** during the event
- Do **not** stop Docker or shut down the laptop while simulation is RUNNING
- Close unnecessary apps to free CPU/RAM
- Take a DB backup before go-live: `scripts/oci/backup-db.sh` works if pointed at local compose (or use manual `pg_dump` via compose exec)

---

## Logs

```powershell
docker compose -f docker-compose.local.yml logs -f backend
docker compose -f docker-compose.local.yml logs -f nginx
docker compose -f docker-compose.local.yml logs -f frontend
```

---

## Files

| File | Purpose |
|------|---------|
| [`docker-compose.local.yml`](docker-compose.local.yml) | Local LAN / ngrok stack |
| [`nginx/conf.d/tradeverse.local.conf`](nginx/conf.d/tradeverse.local.conf) | HTTP nginx routes |
| [`.env.local.example`](.env.local.example) | Env template |
| [`scripts/local/setup-env.ps1`](scripts/local/setup-env.ps1) | Create `.env` + secrets |
| [`scripts/local/start.ps1`](scripts/local/start.ps1) | Start stack |
| [`scripts/local/share.ps1`](scripts/local/share.ps1) | ngrok tunnel + CORS wiring |
| [`scripts/local/apply-public-url.ps1`](scripts/local/apply-public-url.ps1) | Set public/LAN URL in `.env` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Phone cannot connect | Check firewall port 80; same Wi‑Fi; correct LAN IP |
| CORS errors from LAN | Add `http://<LAN_IP>` to `CORS_ORIGINS`, restart backend |
| Port 80 in use | Stop other web servers or change host mapping in compose |
| WS disconnects | Check nginx logs; ensure `/api/v1/ws` Upgrade headers |
