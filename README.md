# Mock Stock Exchange

A web-based multiplayer trading simulation for ~40–50 participants. Humans trade fictional stocks against each other and against AI agents through a real **order book** and **matching engine**. Market prices come from **executed trades** — news and mathematical models shape behaviour and expectations, not arbitrary price overrides.

**Repo:** https://github.com/ragingbul/mock-stock-exchange  
**Product spec:** [`docs/MASTER_PLAN.pdf`](docs/MASTER_PLAN.pdf)

---

## Overview

This is a full exchange simulation, not a simple price-clicking game. The backend implements order books, matching, settlement, AI traders, news, and portfolio accounting. The **participant terminal** is deliberately minimal: most users never need to see an order book.

**Design goal:** keep the sophisticated simulation intact while making the default experience simple enough for a first trade in under 30 seconds.

---

## For participants

### Default workflow

**Select stock → enter quantity → BUY NOW or SELL NOW → confirm → see result → portfolio updates**

No order book, bid/ask, limit orders, or matching concepts are required for normal play.

### What you see on the terminal

| Area | Label in the UI |
|------|-----------------|
| Stock | Stock name |
| Last traded price | **Current price** |
| Day change | **Percentage change** |
| Trade history chart | Price chart (from real executions) |
| Shares to trade | **Quantity** |
| Instant trade | **BUY NOW** / **SELL NOW** |
| Cash balance | **Available cash** |
| Positions | **Holdings** |
| Total worth | **Portfolio value** |
| Gain/loss | **Current profit/loss** |
| Your activity | **Your recent trades** |
| Headlines | News feed |
| Standings | **Leaderboard** |

**Advanced orders & order book** (optional): limit orders, bid/ask depth, and open orders — hidden until expanded.

### After you trade

A successful market order shows a plain summary, for example:

```
ORDER EXECUTED

Bought 100 TECHNOVA
Average execution price: ₹104.35
Total: ₹10,435
```

If the order cannot fill, you get a short human-readable reason — not matching-engine jargon.

---

## For hosts

### Quick start (Docker + share via ngrok)

Recommended for events / multiplayer. Full guide: [`LOCAL_SERVER.md`](LOCAL_SERVER.md).

```powershell
.\scripts\local\setup-env.ps1
.\scripts\local\start.ps1
.\scripts\local\share.ps1    # optional: public HTTPS URL via ngrok
```

| Page | URL |
|------|-----|
| Trading terminal | http://localhost/terminal |
| Admin | http://localhost/admin |
| Health | http://localhost/api/v1/health |

### Quick start (dev without Docker)

```bash
cp .env.example .env
# Without Docker, add to .env:
# DATABASE_URL=sqlite+pysqlite:///./backend/mse_dev.db

cd backend
python -m venv .venv
.\.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# second terminal
cd frontend
npm install
npm run dev
```

| Page | URL |
|------|-----|
| Trading terminal | http://localhost:3000/terminal |
| Admin | http://localhost:3000/admin |
| API docs | http://localhost:8000/docs |

### Run an event

1. Open **Admin** → **Bootstrap market** (stocks, AI agents, liquidity, open session).
2. Click **Run AI tick** a few times, or run the demo script below.
3. Optionally release news from the admin panel.
4. Share the terminal link with participants (`http://<your-ip>:3000/terminal` on the same network).

### Simulate a busy market

Populates mock traders, releases mixed news, and drives AI activity for realistic charts and leaderboard movement:

```bash
cd backend
.\.venv\Scripts\python.exe scripts/run_demo_traders.py
```

---

## Architecture

```
Human / AI decision
        ↓
Order gateway (order_service)
        ↓
Order book
        ↓
Matching engine
        ↓
Settlement → last traded price
        ↓
Market data → terminals (REST + WebSocket)
```

Market orders from participants flow through the same path as AI orders. When the book is thin, `liquidity_service` posts market-maker quotes so normal **BUY NOW / SELL NOW** orders can execute immediately (subject to session status, halts, cash, and holdings checks).

---

## Design principles

### Preserve the backend

Do **not** rebuild or duplicate existing modules. Inspect and extend only where needed:

| Module | Location |
|--------|----------|
| Order book & matching | `backend/app/exchange/` |
| Order gateway | `backend/app/services/order_service.py` |
| AI traders | `backend/app/ai/` |
| News engine | `backend/app/services/news_service.py` |
| Market model | `backend/app/services/market_model.py` |
| Portfolio / P&L | `backend/app/services/portfolio_service.py` |

Limit orders, partial fills, market makers, and full matching remain supported in the backend. They stay out of the default UI.

### Price authority

The frontend is never authoritative for stock price, cash, holdings, P&L, execution price, or trade ownership. All values come from the server via API and WebSocket updates.

### Key rules

1. The matching engine does not depend on AI, news, sentiment, UI, or charts.
2. AI traders use the same order gateway as humans.
3. News does not directly set last traded price (optional fair-value shift on release).
4. Admin does not manually set stock prices.
5. Coefficients and defaults live in config / environment — not hard-coded.

---

## Market simulation (backend)

These formulas drive AI expectations and reference behaviour. They are **not shown to participants**. Weights and coefficients are configurable in `backend/app/core/config.py` and `.env`.

| Concept | Formula |
|---------|---------|
| Human pressure | `P = (B − S) / (B + S)` |
| AI pressure | `A = (AB − AS) / (AB + AS)` |
| Fundamental pressure | `Fp = (F − R) / R` |
| Combined pressure | `M = 0.40·P + 0.25·N + 0.15·Fp + 0.20·A` |
| Reference price | `R(t+1) = R(t) × (1 + k·M)` |
| News decay | `I(t) = I₀ × e^(−λ·t)` |
| Fair-value correction | `C = α(F − R)` |

**Last traded price** updates only when trades execute in settlement — not from news or the UI.

### Event volatility (optional)

For larger swings during live events (~30–40 news releases), tune `.env` (see `.env.example`):

`MARKET_INTENSITY_MULTIPLIER`, `NEWS_PRESSURE_AMPLIFIER`, `MM_SPREAD_BPS`, `MM_QUOTE_SIZE`, `MARKET_NOISE_STD`, and related settings.

---

## Features

- **Terminal** — BUY NOW / SELL NOW, chart, portfolio, news, leaderboard
- **Advanced** — limit orders, order book, cancel open orders
- **Admin** — bootstrap, session control, AI ticks, news, halts, leaderboard
- **Leaderboard API** — `GET /api/v1/leaderboard`
- **Liquidity** — market-maker quotes for immediate participant fills

---

## Testing

```bash
cd backend
pytest
```

The suite covers health, order book, matching, settlement, portfolio math, circuit limits, news decay, AI intents, and **immediate market-order execution** (`tests/test_market_orders.py`).

Before changing behaviour, read the existing modules under `backend/app/exchange/`, `backend/app/ai/`, and `backend/app/services/`.

---

## Project status

All planned phases (foundation through load/simulation tests) are complete.

---

## Contributors

1. **Raghav Singh** — [GitHub](https://github.com/ragingbul) · [LinkedIn](https://www.linkedin.com/in/raghav-singh-b24064279)
2. **Soumil Tiwary** — [GitHub](https://github.com/S0UMIL) · [LinkedIn](https://www.linkedin.com/in/soumiltiwary)
3. **Ishan Dhawan** — [GitHub](https://github.com/ishan1818) · [LinkedIn](https://www.linkedin.com/in/ishan-dhawan-130a17351)

---

## License

MIT License — see [LICENSE](LICENSE).

Copyright (c) 2026 Mock Stock Exchange Contributors
