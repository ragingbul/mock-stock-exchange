# Mock Stock Exchange

Web-based simulated multiplayer stock exchange for ~40–50 participants. Humans and AI agents trade fictional stocks through a real **order book** and **matching engine**. Executed trades determine the observed market price — news and mathematical models influence behaviour and expectations only.

> Source of truth: [`docs/MASTER_PLAN.pdf`](docs/MASTER_PLAN.pdf)

**Repo:** https://github.com/ragingbul/mock-stock-exchange

## Architecture

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

## Quick start

```bash
cp .env.example .env
# Without Docker, add:
# DATABASE_URL=sqlite+pysqlite:///./backend/mse_dev.db

cd backend
python -m venv .venv
.\.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# other terminal
cd frontend
npm install
npm run dev
```

Open:
- Terminal: http://localhost:3000/terminal
- Admin: http://localhost:3000/admin
- API docs: http://localhost:8000/docs

Bootstrap a full market from admin **Bootstrap market**, or:

```bash
curl -X POST http://localhost:8000/api/v1/admin/bootstrap
```

## Tests

```bash
cd backend
pytest
```

## Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Foundation | Done |
| 1 | Entities | Done |
| 2 | Orders | Done |
| 3 | Order books | Done |
| 4 | Matching | Done |
| 5 | Settlement | Done |
| 6 | REST APIs | Done |
| 7 | Trading terminal | Done |
| 8 | WebSockets | Done |
| 9 | AI traders | Done |
| 10 | News engine | Done |
| 11 | Market model | Done |
| 12 | Leaderboard | Done |
| 13 | Admin panel | Done |
| 14 | Load/simulation tests | Done |

## Key design rules

1. Matching engine does not depend on AI, news, sentiment, UI, or charts.
2. AI traders use the same order gateway as humans.
3. News never directly sets last traded price (optional fair-value update only).
4. Admin does not manually set stock prices.
5. Configuration over hard-coding for weights, capital, circuits, ticks.
