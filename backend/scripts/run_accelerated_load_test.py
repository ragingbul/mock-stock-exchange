#!/usr/bin/env python3
"""Stress-test TRADEVERSE at accelerated speed with synthetic traders."""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = "http://127.0.0.1:8000/api/v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Accelerated TRADEVERSE load test")
    parser.add_argument("--traders", type=int, default=10, help="Synthetic traders (max ~50)")
    parser.add_argument("--speed", type=float, default=120.0, help="sim_speed_multiplier")
    parser.add_argument("--seconds", type=int, default=30, help="Real seconds to run")
    args = parser.parse_args()

    client = httpx.Client(base_url=BASE, timeout=30.0)

    def post(path: str, body: dict | None = None):
        r = client.post(path, json=body or {})
        r.raise_for_status()
        return r.json()

    def get(path: str):
        r = client.get(path)
        r.raise_for_status()
        return r.json()

    print("Reset + configure...")
    post("/admin/simulation/reset")
    client.patch("/admin/simulation-settings", json={"sim_speed_multiplier": args.speed})

    print("Start simulation...")
    post("/admin/simulation/start")

    stocks = get("/stocks")
    if not stocks:
        print("No stocks — abort")
        return 1

    traders = []
    for i in range(args.traders):
        t = post("/traders", {"name": f"LoadBot-{i}"})
        traders.append(t["id"])

    rng = random.Random(42)
    orders = 0
    t0 = time.time()
    while time.time() - t0 < args.seconds:
        tid = rng.choice(traders)
        stock = rng.choice(stocks)
        side = rng.choice(["buy", "sell"])
        qty = rng.randint(1, 5)
        try:
            post(
                "/orders",
                {
                    "trader_id": tid,
                    "stock_id": stock["id"],
                    "side": side,
                    "order_type": "market",
                    "quantity": qty,
                    "price": None,
                },
            )
            orders += 1
        except httpx.HTTPStatusError:
            pass
        time.sleep(0.2)

    status = get("/admin/simulation/status")
    lb = get("/leaderboard")
    print(f"Done: orders={orders} elapsed={status.get('elapsed')} checkpoints={status.get('completed_checkpoint_count')}/{status.get('total_checkpoint_count')}")
    print(f"Leaderboard top: {lb[:3] if lb else []}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
