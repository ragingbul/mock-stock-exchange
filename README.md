# Mock Stock Exchange

Web-based simulated multiplayer stock exchange for ~40–50 participants. Humans and AI agents trade fictional stocks through a real **order book** and **matching engine**. Executed trades determine the observed market price — news and mathematical models influence behaviour and expectations only.

> Source of truth: [`docs/MASTER_PLAN.pdf`](docs/MASTER_PLAN.pdf)

**Repo:** https://github.com/ragingbul/mock-stock-exchange

---

## Project approach

We already have an existing mock stock exchange implementation.

**Do not rebuild the project.** Read the existing code and docs first.

Our goal is to keep the sophisticated backend market simulation while making the **participant experience extremely simple**.

### User experience change

Participants should **not** need to understand:

- order books
- bid/ask mechanics
- price-time priority
- matching engines
- limit orders
- settlement mechanics

The default participant workflow is:

**Select stock → enter quantity → BUY NOW / SELL NOW → immediate execution → see result → portfolio updates**

The existing backend order-book and matching architecture remains in place. The simplified UI routes market orders through the same execution system. The market-maker / AI liquidity layer ensures normal participant market orders can execute immediately when the stock is open and risk checks pass.

Limit orders remain available under **Advanced orders & order book** — they are not required for normal participation. There is no mandatory order-book UI on the main screen.

**Target:** a first-time participant should understand the interface and place their first trade in under 30 seconds.

### Participant interface

The main terminal screen shows:

| Shown to participants | Simple label |
|----------------------|--------------|
| Stock name | Stock name |
| LTP | **Current price** |
| % change | **Percentage change** |
| Price chart | Simple price chart (from executed trades) |
| Quantity input | **Quantity** |
| Market buy/sell | **BUY NOW** / **SELL NOW** |
| Cash | **Available cash** |
| Holdings | **Holdings** |
| Portfolio value | **Portfolio value** |
| P&L | **Current profit/loss** |
| User trades | **Your recent trades** |
| News | Simple news feed |
| Rankings | **Leaderboard** |

Advanced information (limit orders, order book, open orders) is hidden under **Advanced orders & order book**.

### Important: preserve the existing backend

Do not duplicate or rewrite existing:

- order-book logic (`backend/app/exchange/`)
- matching engine
- trade execution and settlement
- AI trader system (`backend/app/ai/`)
- news engine (`backend/app/services/news_service.py`)
- market simulation (`backend/app/services/market_model.py`)
- portfolio accounting (`backend/app/services/portfolio_service.py`)

Inspect the implementation before changing behaviour. Only modify what is necessary.

### Price authority

The frontend is **never** authoritative for:

- stock price
- cash
- holdings
- P&L
- execution price
- trade ownership

All of these are determined server-side via REST APIs and WebSocket updates.

### Immediate market orders

When a participant chooses TECHNOVA, BUY, 100 shares, and presses **BUY NOW**, the backend routes through `order_service` → matching engine → settlement, with `liquidity_service` provisioning MM quotes when the book is thin.

The participant sees a human-readable summary, for example:

```
ORDER EXECUTED

Bought 100 TECHNOVA
Average execution price: ₹104.35
Total: ₹10,435
```

If execution cannot happen, a simple reason is shown (not matching-engine jargon unless Advanced is open).

### Keep advanced features

The backend continues to support limit orders, order books, partial fills, market makers, AI traders, liquidity, and full matching — invisible to beginners until they open Advanced.

---

## Architecture

```
Human / AI decision
        ↓
Buy / Sell order  →  Order gateway (order_service)
        ↓
Order book
        ↓
Matching engine
        ↓
Executed trade → Settlement
        ↓
Last traded price → Market data → Terminals (WebSocket)
```

## Market simulation (backend only)

These formulas drive AI expectations and reference behaviour. They are **not** shown to normal participants. Coefficients are configurable via environment / `backend/app/core/config.py` and `.env`.

**Human trading pressure:**

`P = (B − S) / (B + S)`

**AI trading pressure:**

`A = (AB − AS) / (AB + AS)`

**Fundamental pressure:**

`Fp = (F − R) / R`

**Combined market pressure** (weights configurable):

`M = 0.40·P + 0.25·N + 0.15·Fp + 0.20·A`

**Reference price movement:**

`R(t+1) = R(t) × (1 + k·M)`

**News decay:**

`I(t) = I₀ × e^(−λ·t)`

**Fair-value correction:**

`C = α(F − R)`

**Last traded price** is updated only by executed trades in settlement — not by news or the UI directly.

Event-style volatility knobs (optional, in `.env.example`): `MARKET_INTENSITY_MULTIPLIER`, `NEWS_PRESSURE_AMPLIFIER`, `MM_SPREAD_BPS`, `MM_QUOTE_SIZE`, etc.

---

## Features

- **Trading terminal** — minimal UI: **BUY NOW** / **SELL NOW**, chart, portfolio, news, leaderboard
- **Advanced mode** — limit orders, order book, cancel open orders
- **Admin panel** — bootstrap, session control, AI ticks, news, halt, leaderboard
- **AI traders** — same order gateway as humans
- **Leaderboard** — `GET /api/v1/leaderboard`
- **Liquidity** — market-maker quotes for immediate participant fills

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

| Page | URL |
|------|-----|
| Trading terminal | http://localhost:3000/terminal |
| Admin | http://localhost:3000/admin |
| API docs | http://localhost:8000/docs |

### Host an event (admin)

1. **Admin** → **Bootstrap market**
2. **Run AI tick** (or run the demo script below)
3. Optional: release news
4. Share `http://<your-ip>:3000/terminal` with participants

### Trade as a participant

1. **Terminal** → name → **Start**
2. Stock → quantity → **BUY NOW** or **SELL NOW** → confirm

### Multi-trader demo

```bash
cd backend
.\.venv\Scripts\python.exe scripts/run_demo_traders.py
```

## Testing

```bash
cd backend
pytest
```

Coverage includes:

- Health and settings
- Order book and matching
- Settlement and portfolio / P&L
- Circuit limits on limit orders
- News decay
- **Immediate market-order execution** (`tests/test_market_orders.py`)
- Cash, holdings, and execution summaries via API
- AI intents and exchange integration

Before changing code: inspect existing modules under `backend/app/exchange/`, `backend/app/ai/`, and `backend/app/services/`. Do not rebuild them.

## Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 0–14 | Foundation through load/simulation tests | Done |

## Key design rules

1. Matching engine does not depend on AI, news, sentiment, UI, or charts.
2. AI traders use the same order gateway as humans.
3. News does not directly set LTP (optional fair-value shift on release).
4. Admin does not manually set stock prices.
5. Configuration over hard-coding for weights, capital, circuits, ticks, and volatility.

## Contributors

Ordered list of project contributors:

1. **Raghav Singh** — [GitHub](https://github.com/ragingbul) · [LinkedIn](https://www.linkedin.com/in/raghav-singh-b24064279)
2. **Soumil Tiwary** — [GitHub](https://github.com/S0UMIL) · [LinkedIn](https://www.linkedin.com/in/soumiltiwary)
3. **Ishan Dhawan** — [GitHub](https://github.com/ishan1818) · [LinkedIn](https://www.linkedin.com/in/ishan-dhawan-130a17351)

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for the full text.

Copyright (c) 2026 Mock Stock Exchange Contributors
