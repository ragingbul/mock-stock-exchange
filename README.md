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

## Features

- **Trading terminal** — minimal black/white UI with **BUY NOW** / **SELL NOW** market orders, live price chart from executed trades, portfolio strip, news feed, and **leaderboard**
- **Advanced mode** — limit orders, order book, and open-order management (full matching engine unchanged)
- **Admin panel** — bootstrap market, session control (start / pause / resume), AI ticks, news release, halt controls, live status clock, and **leaderboard**
- **AI traders** — same order gateway as humans; strategies react to news and book state
- **Leaderboard** — human traders ranked by return % (`GET /api/v1/leaderboard`)
- **Market liquidity** — market-maker quotes so solo testers and events get immediate fills when the book is thin

## Quick start

```bash
cp .env.example .env
# Without Docker, add:
# DATABASE_URL=sqlite+pysqlite:///./backend/mse_dev.db

cd backend
python -m venv .venv
.\.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# other terminal
cd frontend
npm install
npm run dev
```

Open:

| Page | URL |
|------|-----|
| Trading terminal | http://localhost:3000/terminal |
| Admin | http://localhost:3000/admin |
| API docs | http://localhost:8000/docs |

### Host an event (admin)

1. Open **Admin** → **Bootstrap market** (seeds stocks, AI agents, liquidity, opens session).
2. Click **Run AI tick** a few times to seed activity (or use the demo script below).
3. Optional: release news from the admin form.
4. Share the terminal link with participants (`http://<your-ip>:3000/terminal` on the same Wi‑Fi).

### Trade as a participant

1. Open **Terminal** → enter your name → **Start**.
2. Pick a stock, set quantity, **BUY NOW** or **SELL NOW** → confirm.
3. Watch the chart, portfolio, news, and leaderboard update live.

Bootstrap a full market from admin **Bootstrap market**, or:

```bash
curl -X POST http://localhost:8000/api/v1/admin/bootstrap
```

### Multi-trader demo (realistic charts & leaderboard)

With the API running, simulate ~24 mock traders, AI ticks, mixed orders, and news:

```bash
cd backend
.\.venv\Scripts\python.exe scripts/run_demo_traders.py
```

Then refresh the terminal — charts and leaderboard reflect live multi-participant trading.

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

## Contributors

Ordered list of project contributors:

1. **Raghav Singh** — [GitHub](https://github.com/ragingbul) · [LinkedIn](https://www.linkedin.com/in/raghav-singh-b24064279)
2. **Soumil Tiwary** — [GitHub](https://github.com/S0UMIL) · [LinkedIn](https://www.linkedin.com/in/soumiltiwary)
3. **Ishan Dhawan** — [GitHub](https://github.com/ishan1818) · [LinkedIn](https://www.linkedin.com/in/ishan-dhawan-130a17351)

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for the full text.

Copyright (c) 2026 Mock Stock Exchange Contributors
