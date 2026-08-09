# Mock Stock Exchange

Web-based simulated multiplayer stock exchange for ~40–50 participants. Humans and AI agents trade fictional stocks through a real **order book** and **matching engine**. Executed trades determine the observed market price — news and mathematical models influence behaviour and expectations only.

> Source of truth: [`docs/MASTER_PLAN.pdf`](docs/MASTER_PLAN.pdf)

## Architecture (conceptual layers)

```
Human / AI decision
        ↓
Buy / Sell order  →  Order gateway
        ↓
Order book
        ↓
Matching engine
        ↓
Executed trade → Settlement
        ↓
Last traded price → Market data → Terminals (WebSocket)
```

| Layer | Responsibility |
|-------|----------------|
| Human traders | Place market/limit orders via trading terminals |
| AI traders | Strategies decide side, price, quantity — same order API |
| News engine | Pre-loaded, manually rated events with decay |
| Strategy engine | Converts signals into agent decisions |
| Order gateway | Validates and accepts orders |
| Order books | Bids/asks per stock, price-time priority |
| Matching engine | Matches compatible orders (independent of AI/news/UI) |
| Settlement | Atomic cash/share transfers |
| Market data | LTP, OHLC, depth, volume |
| Portfolio / P&L | Holdings, cash, equity |
| Leaderboard | Configurable scoring |
| Admin panel | Session, news, halts — not manual price setting |

## Tech stack

| Area | Choice |
|------|--------|
| Frontend | Next.js, TypeScript, React, Tailwind CSS |
| Backend | Python, FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL |
| Realtime | WebSockets (Phase 8) |
| Infra | Docker Compose (Postgres), Git / GitHub |

## Repository layout

```
mock-stock-exchange/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/             # HTTP routes
│   │   ├── core/            # Config, database
│   │   ├── models/          # ORM (Phase 1+)
│   │   ├── schemas/         # Pydantic (Phase 1+)
│   │   ├── services/        # Domain services (later)
│   │   ├── exchange/        # Order book + matching (Phase 3–5)
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Next.js trading / admin UI
├── docs/                    # MASTER_PLAN and design notes
├── docker-compose.yml       # PostgreSQL for local dev
├── .env.example
└── README.md
```

## Development phases

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Project setup, health API, frontend skeleton | **Current** |
| 1 | Database models & core entities | Pending |
| 2 | Order system | Pending |
| 3 | Order books | Pending |
| 4 | Matching engine | Pending |
| 5 | Settlement & portfolio | Pending |
| 6 | REST APIs | Pending |
| 7 | Trading terminal | Pending |
| 8 | WebSockets | Pending |
| 9 | AI traders | Pending |
| 10 | News engine | Pending |
| 11 | Mathematical models | Pending |
| 12 | Leaderboard | Pending |
| 13 | Admin panel | Pending |
| 14 | Load testing & polish | Pending |

## Prerequisites

- Python 3.12+ (3.13 works for Phase 0)
- Node.js 20+ / npm
- Docker Desktop (recommended for PostgreSQL)
- Git

## Quick start

### 1. Environment

```bash
cp .env.example .env
```

### 2. PostgreSQL

With Docker:

```bash
docker compose up -d db
```

Without Docker, point `POSTGRES_*` in `.env` at a local Postgres instance.

### 3. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/api/v1/health  
- Docs: http://localhost:8000/docs  

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### 5. Tests

```bash
cd backend
pytest
```

## Design rules (do not violate)

1. Matching engine must not depend on AI, news, sentiment, UI, or charts.
2. AI traders use the same order interface as humans.
3. News must not directly set last traded price.
4. Admin should not normally manually set stock prices.
5. Prefer configuration over hard-coded behaviour.
6. Commit after each working phase; do not skip layers.

## License

Private / educational use for a controlled college event simulation.
