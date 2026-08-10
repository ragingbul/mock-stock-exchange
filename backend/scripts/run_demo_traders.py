"""Run a volatile multi-trader demo against a live API (bootstrap + news + bots).

Usage (backend running on port 8000):
    cd backend
    .\\.venv\\Scripts\\python.exe scripts/run_demo_traders.py
"""

from __future__ import annotations

import random
import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
TRADER_COUNT = 30
AI_TICKS = 18
ORDER_ROUNDS = 500
NEWS_RELEASES = 12

# Simulates a busy event day — mix of sharp rallies and selloffs
NEWS_SCENARIOS = [
    ("TECHNOVA beats earnings", "TECHNOVA", 1, "0.95", "12"),
    ("AUTOMAX supply shock", "AUTOMAX", -1, "0.9", "-10"),
    ("Pharma sector upgrade", "HEALTHPLUS", 1, "0.85", "8"),
    ("Banking credit fears", "FINWAVE", -1, "0.9", "-9"),
    ("Energy spike on crude", "ENERGYX", 1, "0.88", "11"),
    ("Retail slump warning", "RETAILKING", -1, "0.92", "-11"),
    ("Tech guidance cut", "TECHNOVA", -1, "0.93", "-14"),
    ("Auto export boom", "AUTOMAX", 1, "0.87", "9"),
    ("Market-wide risk-on", "", 1, "0.8", "6"),
    ("Market-wide risk-off", "", -1, "0.82", "-7"),
    ("HEALTHPLUS FDA approval", "HEALTHPLUS", 1, "0.96", "15"),
    ("FINWAVE dividend surprise", "FINWAVE", 1, "0.84", "7"),
]


def release_news(client: httpx.Client, title: str, tickers: str, direction: int, impact: str, pct: str) -> None:
    body = {
        "title": title,
        "description": title,
        "affected_tickers": tickers,
        "direction": direction,
        "impact": impact,
        "confidence": "0.95",
        "duration_minutes": 45,
        "decay_rate": "0.015",
        "fundamental_impact_pct": pct,
        "market_wide": tickers == "",
    }
    created = client.post(f"{BASE}/admin/news", json=body).json()
    client.post(f"{BASE}/admin/news/{created['id']}/release")


def print_leaderboard_summary(client: httpx.Client) -> None:
    lb = client.get(f"{BASE}/leaderboard").json()
    if not lb:
        print("Leaderboard: empty")
        return
    returns = [float(r["return_pct"]) for r in lb]
    best = lb[0]
    worst = lb[-1]
    print(
        f"Leaderboard: {len(lb)} traders · "
        f"best {best['name']} {best['return_pct']}% · "
        f"worst {worst['name']} {worst['return_pct']}% · "
        f"spread {max(returns):.2f}% to {min(returns):.2f}%"
    )
    for row in lb[:5]:
        print(f"  #{row['rank']} {row['name']}: {row['return_pct']}% (₹{row['portfolio_value']})")
    print("  ...")
    for row in lb[-3:]:
        print(f"  #{row['rank']} {row['name']}: {row['return_pct']}% (₹{row['portfolio_value']})")


def main() -> int:
    rng = random.Random(42)
    fills = 0
    rejects = 0

    with httpx.Client(timeout=180.0) as client:
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

        lead_stock = stocks[0]
        for tid in traders[:15]:
            body = {
                "trader_id": tid,
                "stock_id": rng.choice(stocks)["id"],
                "side": "buy",
                "order_type": "market",
                "quantity": rng.randint(40, 120),
            }
            res = client.post(f"{BASE}/orders", json=body).json()
            if res.get("executed"):
                fills += 1

        news_idx = 0
        for i in range(ORDER_ROUNDS):
            if i > 0 and i % 45 == 0 and news_idx < NEWS_RELEASES:
                title, tickers, direction, impact, pct = NEWS_SCENARIOS[news_idx % len(NEWS_SCENARIOS)]
                release_news(client, title, tickers, direction, impact, pct)
                print(f"News released: {title}")
                for _ in range(3):
                    client.post(f"{BASE}/admin/ai/tick")
                news_idx += 1
                stocks = client.get(f"{BASE}/stocks").json()

            stock = rng.choice(stocks)
            trader = rng.choice(traders)
            side = rng.choice(["buy", "sell"])
            order_type = "market" if rng.random() < 0.72 else "limit"
            qty = rng.randint(25, 140)
            ltp = float(stock["last_traded_price"])
            body: dict = {
                "trader_id": trader,
                "stock_id": stock["id"],
                "side": side,
                "order_type": order_type,
                "quantity": qty,
            }
            if order_type == "limit":
                jitter = rng.uniform(-0.06, 0.06)
                body["price"] = round(ltp * (1 + jitter), 2)
            else:
                body["price"] = None

            res = client.post(f"{BASE}/orders", json=body).json()
            if res.get("executed"):
                fills += 1
            elif res.get("rejected"):
                rejects += 1

            if i % 50 == 0:
                stocks = client.get(f"{BASE}/stocks").json()

        while news_idx < NEWS_RELEASES:
            title, tickers, direction, impact, pct = NEWS_SCENARIOS[news_idx % len(NEWS_SCENARIOS)]
            release_news(client, title, tickers, direction, impact, pct)
            news_idx += 1
            for _ in range(4):
                client.post(f"{BASE}/admin/ai/tick")

        stocks = client.get(f"{BASE}/stocks").json()
        overview = client.get(f"{BASE}/admin/overview").json()
        trades = client.get(f"{BASE}/trades", params={"stock_id": lead_stock["id"], "limit": 500}).json()

        print(f"Done: fills={fills} rejects={rejects} news={news_idx} trades_on_{lead_stock['ticker']}={len(trades)}")
        print(f"Overview: trades={overview.get('trades')} open_orders={overview.get('open_orders')}")
        print("Price moves (sample):")
        for s in stocks[:6]:
            start = float(s.get("starting_price", s["last_traded_price"]))
            ltp = float(s["last_traded_price"])
            chg = ((ltp - start) / start) * 100 if start else 0
            print(f"  {s['ticker']}: {start:.2f} → {ltp:.2f} ({chg:+.1f}%)")
        print_leaderboard_summary(client)
        print("Open terminal, pick active tickers for live charts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
