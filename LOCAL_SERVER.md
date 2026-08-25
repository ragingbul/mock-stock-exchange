# TRADEVERSE Local LAN Server

Run TRADEVERSE on your **laptop** as the event server. Participants on the same Wi‑Fi connect via your LAN IP. **No cloud, no HTTPS** for this mode.

Oracle cloud files ([`OCI_DEPLOYMENT.md`](OCI_DEPLOYMENT.md), [`docker-compose.prod.yml`](docker-compose.prod.yml)) remain available but are **not used** in local mode.

---

## Architecture

```
YOUR LAPTOP (Docker)
├── nginx          → only service exposed on host :80
├── frontend       → internal :3000
├── backend        → internal :8000, 1 uvicorn worker, 1 sim worker
└── postgres       → internal, persistent volume
```

WebSockets: `ws://<host>/api/v1/ws` proxied through nginx.

---

## Quick start (Windows)

### 1. Configure environment

```powershell
cd "C:\Users\Slim 5\mock market simulation"
copy .env.local.example .env
# Edit .env: set POSTGRES_PASSWORD, JWT_SECRET (32+ chars), ADMIN_SECRET
# Add your LAN IP to CORS_ORIGINS, FRONTEND_URL, BACKEND_URL
```

Find your LAN IP:

```powershell
ipconfig
```

Look for **IPv4 Address** under your Wi‑Fi adapter (e.g. `192.168.1.42`).

Update `.env`:

```
CORS_ORIGINS=http://localhost,http://127.0.0.1,http://192.168.1.42
FRONTEND_URL=http://192.168.1.42
BACKEND_URL=http://192.168.1.42
```

Leave `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` **empty** for same-origin auto (works for both `localhost` and LAN IP).

### 2. Start

```powershell
.\scripts\local\start.ps1
```

Or manually:

```powershell
docker compose -f docker-compose.local.yml build
docker compose -f docker-compose.local.yml up -d postgres
docker compose -f docker-compose.local.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.local.yml up -d
```

### 3. Verify on laptop

```powershell
.\scripts\local\health-check.ps1
```

Open in browser:

| Page | URL |
|------|-----|
| Home | http://localhost/ |
| Terminal | http://localhost/terminal |
| Admin | http://localhost/admin |
| Market screen | http://localhost/market-screen |
| Health | http://localhost/api/v1/health |

### 4. Stop

```powershell
.\scripts\local\stop.ps1
```

Database volume `postgres_data_local` is **preserved**.

---

## LAN participant URLs

Replace `192.168.x.x` with your laptop IP:

| Role | URL |
|------|-----|
| Participant | http://192.168.x.x/terminal |
| Admin | http://192.168.x.x/admin |
| Public screen | http://192.168.x.x/market-screen |

---

## Windows Firewall

Allow inbound **TCP port 80** on your Private network profile so phones/laptops on the same Wi‑Fi can connect:

1. Windows Security → Firewall & network protection → Advanced settings
2. Inbound Rules → New Rule → Port → TCP 80 → Allow → Private networks

Do **not** open 5432, 8000, or 3000.

---

## ngrok (public internet access)

Expose your local stack (nginx on **port 80**) via ngrok so participants outside your LAN can connect.

### 1. Start the Docker stack first

```powershell
.\scripts\local\start.ps1
```

Verify http://localhost/api/v1/health returns OK.

### 2. Start ngrok (separate terminal)

```powershell
ngrok http 80
```

Example tunnel: `https://module-coziness-unwitting.ngrok-free.dev` → `http://localhost:80`

### 3. Configure `.env`

Set your ngrok URL in `.env` (see [`.env.local.example`](.env.local.example)):

```
CORS_ORIGINS=http://localhost,http://127.0.0.1,https://module-coziness-unwitting.ngrok-free.dev
FRONTEND_URL=https://module-coziness-unwitting.ngrok-free.dev
BACKEND_URL=https://module-coziness-unwitting.ngrok-free.dev
```

Leave `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` **empty** — the frontend uses same-origin automatically.

Restart backend + nginx after changing `.env`:

```powershell
docker compose -f docker-compose.local.yml restart backend nginx
```

If you changed frontend env vars, rebuild: `docker compose -f docker-compose.local.yml up -d --build frontend`

### 4. Participant URLs

| Role | URL |
|------|-----|
| Participant | https://module-coziness-unwitting.ngrok-free.dev/terminal |
| Admin | https://module-coziness-unwitting.ngrok-free.dev/admin |
| Public screen | https://module-coziness-unwitting.ngrok-free.dev/market-screen |
| Health | https://module-coziness-unwitting.ngrok-free.dev/api/v1/health |

### Notes

- ngrok free tier shows a browser warning page once; the app sends `ngrok-skip-browser-warning` on API calls.
- WebSockets use `wss://` automatically when the page is loaded over HTTPS.
- If your ngrok URL changes, update `CORS_ORIGINS`, `FRONTEND_URL`, and `BACKEND_URL`, then restart backend.

---

## CORS when LAN IP changes

If you switch networks and your IP changes:

1. Update `CORS_ORIGINS`, `FRONTEND_URL`, `BACKEND_URL` in `.env`
2. Restart backend only:

```powershell
docker compose -f docker-compose.local.yml restart backend
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
| [`docker-compose.local.yml`](docker-compose.local.yml) | Local LAN stack |
| [`nginx/conf.d/tradeverse.local.conf`](nginx/conf.d/tradeverse.local.conf) | HTTP nginx routes |
| [`.env.local.example`](.env.local.example) | Env template |
| [`scripts/local/start.ps1`](scripts/local/start.ps1) | Start stack |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Phone cannot connect | Check firewall port 80; same Wi‑Fi; correct LAN IP |
| CORS errors from LAN | Add `http://<LAN_IP>` to `CORS_ORIGINS`, restart backend |
| Port 80 in use | Stop other web servers or change host mapping in compose |
| WS disconnects | Check nginx logs; ensure `/api/v1/ws` Upgrade headers |
