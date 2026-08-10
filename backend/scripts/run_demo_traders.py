"""Run a multi-trader demo against a live API (bootstrap + bots + trades).

Usage (backend running on port 8000):
    cd backend
    .\\.venv\\Scripts\\python.exe scripts/run_demo_traders.py
"""

from __future__ import annotations

import random
import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
TRADER_COUNT = 24
AI_TICKS = 10
ORDER_ROUNDS = 250


def main() -> int:
    rng = random.Random(42)
    fills = 0
    rejects = 0

    with httpx.Client(timeout=120.0) as client:
        health = client.get(f"{BASE}/health")
        if health.status_code != 200:
            print("Backend not reachable at", BASE)
            return 1

        boot = client.post(f"{BASE}/admin/bootstrap").json()
        print("Bootstrap:", boot)

        traders: list[int] = []
        for i in range(TRADER_COUNT):
            r = client.post(f"{BASE}/traders", json={"name": f"Demo-{i:02d}"})
            traders.append(r.json()["id"])

        stocks = client.get(f"{BASE}/stocks").json()
        print(f"Created {len(traders)} traders, {len(stocks)} stocks")

        for _ in range(AI_TICKS):
            tick = client.post(f"{BASE}/admin/ai/tick").json()
            print(f"AI tick: {tick.get('actions', 0)} actions")

        # Seed holdings: early traders buy so later sells can execute
        lead_stock = stocks[0]
        for tid in traders[:12]:
            body = {
                "trader_id": tid,
                "stock_id": lead_stock["id"],
                "side": "buy",
                "order_type": "market",
                "quantity": rng.randint(20, 60),
            }
            res = client.post(f"{BASE}/orders", json=body).json()
            if res.get("executed"):
                fills += 1

        for i in range(ORDER_ROUNDS):
            stock = rng.choice(stocks)
            trader = rng.choice(traders)
            side = rng.choice(["buy", "sell"])
            order_type = "market" if rng.random() < 0.65 else "limit"
            qty = rng.randint(5, 35)
            ltp = float(stock["last_traded_price"])
            body: dict = {
                "trader_id": trader,
                "stock_id": stock["id"],
                "side": side,
                "order_type": order_type,
                "quantity": qty,
            }
            if order_type == "limit":
                jitter = rng.uniform(-0.03, 0.03)
                body["price"] = round(ltp * (1 + jitter), 2)
            else:
                body["price"] = None

            res = client.post(f"{BASE}/orders", json=body).json()
            if res.get("executed"):
                fills += 1
            elif res.get("rejected"):
                rejects += 1

            # Refresh stock prices occasionally
            if i % 40 == 0:
                stocks = client.get(f"{BASE}/stocks").json()

        news = client.post(
            f"{BASE}/admin/news",
            json={
                "title": "Sector rally on strong earnings",
                "description": "Multiple large caps guide higher for the quarter.",
                "affected_tickers": lead_stock["ticker"],
                "direction": 1,
                "impact": "0.8",
                "confidence": "0.9",
                "duration_minutes": 30,
                "decay_rate": "0.04",
                "fundamental_impact_pct": "5",
            },
        ).json()
        client.post(f"{BASE}/admin/news/{news['id']}/release")

        for _ in range(4):
            client.post(f"{BASE}/admin/ai/tick")

        trades = client.get(f"{BASE}/trades", params={"stock_id": lead_stock["id"], "limit": 500}).json()
        overview = client.get(f"{BASE}/admin/overview").json()

    print(f"Done: fills={fills} rejects={rejects} trades_on_{lead_stock['ticker']}={len(trades)}")
    print(f"Overview: trades={overview.get('trades')} open_orders={overview.get('open_orders')}")
    print("Open terminal, select", lead_stock["ticker"], "to see the live chart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
