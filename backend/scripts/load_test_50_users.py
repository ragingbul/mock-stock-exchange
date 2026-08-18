#!/usr/bin/env python3
"""50-user concurrent load test for TRADEVERSE live events.

Modes:
  LOCAL:  python load_test_50_users.py --base-url http://localhost:8000
  CLOUD:  python load_test_50_users.py --base-url https://YOUR-API.up.railway.app
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from dataclasses import dataclass, field

import httpx

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore[assignment]


@dataclass
class UserStats:
    errors: int = 0
    orders: int = 0
    wallet_reads: int = 0
    bootstrap_reads: int = 0
    ws_connected: int = 0
    latencies_ms: list[float] = field(default_factory=list)


async def _join(client: httpx.AsyncClient, idx: int) -> tuple[int, str]:
    res = await client.post("/api/v1/auth/join", json={"display_name": f"load-{idx}"})
    res.raise_for_status()
    body = res.json()
    return body["trader_id"], body["access_token"]


async def _ws_loop(base_url: str, token: str, stats: UserStats, duration_sec: float) -> None:
    if websockets is None:
        return
    ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
    uri = f"{ws_base}/api/v1/ws?token={token}"
    end = time.time() + duration_sec
    try:
        async with websockets.connect(uri, open_timeout=10) as ws:
            stats.ws_connected += 1
            await ws.recv()
            while time.time() < end:
                try:
                    await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
    except Exception:
        stats.errors += 1


async def _user_loop(
    client: httpx.AsyncClient,
    *,
    trader_id: int,
    token: str,
    stock_id: int,
    stats: UserStats,
    duration_sec: float,
    do_reconnect: bool,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    end = time.time() + duration_sec
    side = "buy"
    while time.time() < end:
        payload = {
            "trader_id": trader_id,
            "stock_id": stock_id,
            "side": side,
            "order_type": "market",
            "quantity": 1,
        }
        started = time.perf_counter()
        try:
            if do_reconnect and random.random() < 0.05:
                boot = await client.get("/api/v1/session/bootstrap", headers=headers)
                if boot.status_code == 200:
                    stats.bootstrap_reads += 1
                else:
                    stats.errors += 1
            wallet = await client.get(f"/api/v1/traders/{trader_id}/wallet", headers=headers)
            if wallet.status_code == 200:
                stats.wallet_reads += 1
            else:
                stats.errors += 1
            res = await client.post("/api/v1/orders", json=payload, headers=headers)
            if res.status_code >= 400:
                stats.errors += 1
            else:
                stats.orders += 1
                stats.latencies_ms.append((time.perf_counter() - started) * 1000)
        except Exception:
            stats.errors += 1
        side = "sell" if side == "buy" else "buy"
        await asyncio.sleep(0.5)


async def run_load_test(base_url: str, users: int, duration_sec: float) -> None:
    stats = UserStats()
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        health = await client.get("/api/v1/health")
        health.raise_for_status()

        stocks = (await client.get("/api/v1/stocks")).json()
        if not stocks:
            raise SystemExit("no stocks — run admin RESET first")
        stock_id = stocks[0]["id"]

        traders: list[tuple[int, str]] = []
        for idx in range(users):
            traders.append(await _join(client, idx))

        await client.get("/api/v1/leaderboard")

        tasks = []
        for trader_id, token in traders:
            tasks.append(
                asyncio.create_task(
                    _user_loop(
                        client,
                        trader_id=trader_id,
                        token=token,
                        stock_id=stock_id,
                        stats=stats,
                        duration_sec=duration_sec,
                        do_reconnect=True,
                    )
                )
            )
            if websockets is not None:
                tasks.append(
                    asyncio.create_task(
                        _ws_loop(base_url, token, stats, duration_sec)
                    )
                )
        await asyncio.gather(*tasks)

    total_requests = stats.orders + stats.errors
    p95 = statistics.quantiles(stats.latencies_ms, n=20)[-1] if len(stats.latencies_ms) >= 20 else (
        max(stats.latencies_ms) if stats.latencies_ms else 0
    )
    print(f"base_url={base_url}")
    print(f"users={users} duration={duration_sec}s")
    print(f"orders_ok={stats.orders} errors={stats.errors} error_rate={stats.errors / max(total_requests, 1):.2%}")
    print(f"wallet_reads={stats.wallet_reads} bootstrap_reads={stats.bootstrap_reads} ws_connected={stats.ws_connected}")
    print(f"trades_per_sec={stats.orders / duration_sec:.2f}")
    print(f"p95_latency_ms={p95:.1f}")
    if websockets is None:
        print("note: install websockets package for WS phase")


def main() -> None:
    parser = argparse.ArgumentParser(description="TRADEVERSE 50-user load test")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="LOCAL: http://localhost:8000 | CLOUD: https://your-api.up.railway.app",
    )
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--duration", type=float, default=60.0)
    args = parser.parse_args()
    asyncio.run(run_load_test(args.base_url.rstrip("/"), args.users, args.duration))


if __name__ == "__main__":
    main()
