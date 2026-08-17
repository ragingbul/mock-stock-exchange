# TRADEVERSE — Oracle Cloud Always Free Deployment

Zero-cost target: **₹0 / $0** using Oracle Always Free Ampere A1 compute, Docker Compose, PostgreSQL, Nginx, and self-signed TLS (IP-only) or optional free hostname + Certbot.

See also [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) and [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Architecture

```
                    INTERNET
                       │
                       ▼
                PUBLIC IP (443/80)
                       │
                       ▼
                ┌──────────────┐
                │    NGINX     │  HTTPS / WSS termination
                └──────┬───────┘
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
          FRONTEND          BACKEND (1 worker)
          Next.js           FastAPI + simulation
          :3000 internal    :8000 internal
                              │
                              ▼
                         PostgreSQL
                    (Docker volume, not public)
```

| Component | File |
|-----------|------|
| Production stack | [`docker-compose.prod.yml`](docker-compose.prod.yml) |
| Local dev stack | [`docker-compose.yml`](docker-compose.yml) |
| Nginx | [`nginx/conf.d/tradeverse.conf`](nginx/conf.d/tradeverse.conf) |
| Deploy script | [`scripts/oci/deploy.sh`](scripts/oci/deploy.sh) |

**Single simulation worker:** exactly one backend container, `uvicorn --workers 1`, PostgreSQL advisory lock fail-closed. Do not scale backend replicas.

---

## Always Free resource fit

| Resource | Recommendation | Cost |
|----------|----------------|------|
| VM | 1× Ampere A1, **2 OCPU / 12 GB RAM**, Ubuntu 22.04 LTS | Always Free |
| Boot volume | ≤ 200 GB total account block storage | Always Free |
| Public ports | 22, 80, 443 only | — |
| Postgres / Nginx / apps | All on same VM via Docker | — |

Do **not** enable paid shapes, load balancers, or managed databases.

---

## Blocker: IP-only HTTPS

Let's Encrypt **cannot** issue certificates for bare IP addresses.

**Default prep path:** self-signed cert via [`scripts/oci/generate-self-signed-cert.sh`](scripts/oci/generate-self-signed-cert.sh). Browsers show security warnings on every device until the cert is manually trusted — **risky for ~50 participants**.

**Zero-cost alternative (optional):** use a free DNS name pointing at your IP (e.g. `203-0-113-10.sslip.io`) and Certbot. No domain purchase required. Documented in [HTTPS](#https) below.

---

## Oracle VM setup (you run these steps)

### 1. Create Always Free VM

1. Oracle Cloud Console → Compute → Instances → Create
2. **Shape:** Ampere A1 (Always Free-eligible), 2 OCPU, 12 GB memory
3. **Image:** Ubuntu 22.04 LTS
4. **Networking:** assign public IP; note security list
5. **SSH:** paste your **public** key (no password auth)

### 2. Security list (Oracle firewall)

Ingress allow **only**:

| Port | Protocol | Purpose |
|------|----------|---------|
| 22 | TCP | SSH |
| 80 | TCP | HTTP → HTTPS redirect |
| 443 | TCP | HTTPS / WSS |

Do **not** open 5432, 8000, or 3000.

### 3. SSH access

```bash
ssh -i ~/.ssh/your_key ubuntu@YOUR_PUBLIC_IP
```

Use SSH keys only. Disable password login in `/etc/ssh/sshd_config` if not already (`PasswordAuthentication no`).

### 4. Install Docker

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl git openssl ufw
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

### 5. Host firewall (ufw)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### 6. Clone repository

```bash
git clone https://github.com/ragingbul/mock-stock-exchange.git tradeverse
cd tradeverse
git checkout cursor/fix-admin-bootstrap-news   # or your deploy branch
cp .env.example .env
```

### 7. Configure `.env`

Edit `.env` on the server (never commit). Replace `YOUR_PUBLIC_IP` and generate strong secrets:

```bash
ENVIRONMENT=production
DEBUG=false
AUTO_INIT_DB=false
SIMULATION_SPEED=1

POSTGRES_USER=mse
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=mock_stock_exchange

JWT_SECRET=<at-least-32-characters>
ADMIN_SECRET=<strong-admin-password>

FRONTEND_URL=https://YOUR_PUBLIC_IP
BACKEND_URL=https://YOUR_PUBLIC_IP
CORS_ORIGINS=https://YOUR_PUBLIC_IP

NEXT_PUBLIC_API_URL=https://YOUR_PUBLIC_IP
NEXT_PUBLIC_WS_URL=wss://YOUR_PUBLIC_IP
NEXT_PUBLIC_API_PREFIX=/api/v1
```

Production event: `SIMULATION_SPEED=1`. Rehearsal: temporarily set `SIMULATION_SPEED=60` in `.env`, redeploy backend, then restore to `1`.

### 8. TLS certificate

**IP-only (default):**

```bash
chmod +x scripts/oci/*.sh
./scripts/oci/generate-self-signed-cert.sh YOUR_PUBLIC_IP
```

**Optional free hostname + Let's Encrypt:**

1. Point `YOUR-IP.sslip.io` (or DuckDNS) to your public IP
2. Update `.env` URLs to `https://that-hostname`
3. Install certbot on host or use certbot container; mount certs into `nginx/certs/` as `fullchain.pem` and `privkey.pem`
4. Rebuild frontend with updated `NEXT_PUBLIC_*` URLs

### 9. Deploy

```bash
./scripts/oci/deploy.sh
./scripts/oci/health-check.sh
```

Expect: `"database": "ok"`, simulation status idle (not RUNNING).

### 10. Post-deploy (do NOT START simulation)

1. Open `https://YOUR_PUBLIC_IP/admin`
2. Enter `ADMIN_SECRET`
3. Run **RESET** once → `"Canonical stock universe loaded successfully"`
4. **Do not press START** until the live event

---

## Environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `ENVIRONMENT` | yes | `production` |
| `DEBUG` | yes | `false` |
| `AUTO_INIT_DB` | yes | `false` — use Alembic only |
| `SIMULATION_SPEED` | yes | `1` production; `60` rehearsal only |
| `POSTGRES_*` | yes | Postgres container credentials |
| `DATABASE_URL` | auto | Set in compose from `POSTGRES_*` |
| `JWT_SECRET` | yes | ≥ 32 characters |
| `ADMIN_SECRET` | yes | Admin bearer token |
| `FRONTEND_URL` | yes | Public HTTPS origin |
| `BACKEND_URL` | yes | Same origin through Nginx |
| `CORS_ORIGINS` | yes | Match frontend URL |
| `NEXT_PUBLIC_API_URL` | yes | Build-time; public HTTPS base |
| `NEXT_PUBLIC_WS_URL` | yes | Build-time; `wss://` base |
| `NEXT_PUBLIC_API_PREFIX` | yes | `/api/v1` |

---

## Database

- **Engine:** PostgreSQL 16 (Docker service `postgres`)
- **Persistence:** Docker volume `postgres_data` → `/var/lib/postgresql/data`
- **Not exposed** to the internet
- **Connection:** `DATABASE_URL` via compose environment

### Migrations

Run **once per deploy**, not on every backend restart:

```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

[`scripts/oci/deploy.sh`](scripts/oci/deploy.sh) runs this automatically. Do **not** use `Base.metadata.create_all()` in production.

### Backup

```bash
./scripts/oci/backup-db.sh
# writes backups/tradeverse-YYYYMMDD-HHMMSS.sql
```

**Pre-event:** deploy → RESET → rehearsal backup → RESET again → final backup.

**Post-event:** `./scripts/oci/backup-db.sh`

### Restore

```bash
./scripts/oci/restore-db.sh backups/tradeverse-YYYYMMDD-HHMMSS.sql
```

Stops backend during restore; database volume is preserved across app updates.

---

## Nginx routing

| Public path | Upstream |
|-------------|----------|
| `/` | `frontend:3000` |
| `/terminal`, `/admin`, `/market-screen` | Next.js (via `/`) |
| `/api/v1/*` | `backend:8000/api/v1/` |
| `/api/v1/ws` | WebSocket proxy with `Upgrade` / `Connection` headers |
| `/api/v1/health` | Health check (DB + engine status) |

Config: [`nginx/conf.d/tradeverse.conf`](nginx/conf.d/tradeverse.conf)

---

## WebSockets

Production flow: Browser → HTTPS → Nginx → WSS → FastAPI `/api/v1/ws?token=`

- Participant terminal appends JWT query param ([`frontend/src/lib/api.ts`](frontend/src/lib/api.ts))
- Private events (wallet, portfolio) require authenticated token
- Public market screen receives public events only
- Reconnect: terminal calls `GET /api/v1/session/bootstrap`

---

## Security checklist

| Item | Status |
|------|--------|
| SSH key auth | Configure on VM |
| HTTPS | Nginx TLS (self-signed or LE) |
| Postgres not public | No port 5432 in security list |
| Backend not public | Internal Docker network only |
| Admin START/STOP/RESET | `ADMIN_SECRET` bearer required |
| Participant trades | JWT; server derives `trader_id` |
| WebSocket private data | Token-scoped |
| Secrets in logs | Never log JWT/ADMIN/DATABASE passwords |

---

## Operations

### Update application

```bash
cd ~/tradeverse
./scripts/oci/deploy.sh
```

Does **not** delete `postgres_data` volume.

### Rollback

```bash
git checkout <previous-tag-or-commit>
./scripts/oci/deploy.sh
```

Database volume unchanged unless you explicitly restore from backup.

### Logs

```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.prod.yml logs -f postgres
```

Important log lines: server start, DATABASE CONNECTED, ADVISORY LOCK, START/STOP/RESET, WS connect/disconnect.

### Resource monitoring (free, local only)

```bash
docker stats
free -h
df -h
top
docker compose -f docker-compose.prod.yml ps
```

---

## Verification (after deploy)

Run on the VM or from a client against public URL:

| Check | Command / URL |
|-------|----------------|
| Health | `curl -sk https://YOUR_PUBLIC_IP/api/v1/health` |
| Terminal | `https://YOUR_PUBLIC_IP/terminal` |
| Admin | `https://YOUR_PUBLIC_IP/admin` |
| Market screen | `https://YOUR_PUBLIC_IP/market-screen` |
| Auth join | `POST /api/v1/auth/join` |
| WS | Connect to `wss://YOUR_PUBLIC_IP/api/v1/ws?token=...` |

**Canonical universe:** after RESET, ~40 stocks (35 tradable + 5 IPO pipeline). See [`backend/app/seed/tradeverse_stocks.py`](backend/app/seed/tradeverse_stocks.py).

**Server restart:** simulation state, wallets, timeline EXECUTED rows persist; executed events do not replay.

**Admin disconnect:** simulation continues; admin reconnect shows current state from DB.

---

## Load test (after basic checks pass)

From a machine with Python:

```bash
pip install httpx websockets
python backend/scripts/load_test_50_users.py --base-url https://YOUR_PUBLIC_IP --users 50
```

Use `-k` / trust self-signed cert or fix TLS first.

---

## Accelerated rehearsal

1. Set `SIMULATION_SPEED=60` in `.env`
2. `./scripts/oci/deploy.sh`
3. Admin RESET → START → verify full timeline (EUPHORIA → CRASH → RECOVERY, news, AI, IPO, dissolution)
4. Stop simulation; set `SIMULATION_SPEED=1`; redeploy
5. RESET before live event; **do not START** until event time

---

## Production live event

- `SIMULATION_SPEED=1`
- Final backup taken
- Admin START at event time only
- Do not run START during deployment prep

---

## Files added for OCI

| Path | Purpose |
|------|---------|
| `docker-compose.prod.yml` | Production stack |
| `nginx/nginx.conf` | Nginx main config |
| `nginx/conf.d/tradeverse.conf` | Reverse proxy + WSS |
| `nginx/certs/` | TLS certs (generated on server) |
| `scripts/oci/*.sh` | Deploy, backup, restore, certs, health |
| `backups/` | Local pg_dump output (gitignored content) |
| `.dockerignore` | Faster, safer builds |

Local development continues to use [`docker-compose.yml`](docker-compose.yml) unchanged.
