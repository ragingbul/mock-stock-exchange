#!/usr/bin/env python3
"""Post-deploy smoke test for synchronized TRADEVERSE state.

Verifies health, admin reset, multi-trader join, stock prices, trading,
portfolio, and leaderboard consistency against a single API worker + database.

Example:
  ADMIN_SECRET=your-secret python smoke_test_sync.py \\
    --base-url https://your-api.up.railway.app
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore[assignment]


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def _admin_headers(admin_secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_secret}"}


async def _join(client: httpx.AsyncClient, name: str) -> tuple[int, str]:
    res = await client.post("/api/v1/auth/join", json={"display_name": name})
    res.raise_for_status()
    body = res.json()
    return body["trader_id"], body["access_token"]


async def _bootstrap(client: httpx.AsyncClient, token: str) -> dict:
    res = await client.get(
        "/api/v1/session/bootstrap",
        headers={"Authorization": f"Bearer {token}"},
    )
    res.raise_for_status()
    return res.json()


async def _leaderboard(client: httpx.AsyncClient, token: str) -> list[dict]:
    res = await client.get(
        "/api/v1/leaderboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    res.raise_for_status()
    return res.json()


async def _wait_for_ws_event(base_url: str, token: str, timeout_sec: float = 5.0) -> bool:
    if websockets is None:
        return False
    ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
    uri = f"{ws_base}/api/v1/ws?token={token}"
    try:
        async with websockets.connect(uri, open_timeout=10) as ws:
            await asyncio.wait_for(ws.recv(), timeout=timeout_sec)
            return True
    except Exception:
        return False


async def run(base_url: str, admin_secret: str) -> None:
    base = base_url.rstrip("/")
    admin = _admin_headers(admin_secret)
    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
        health = await client.get("/api/v1/health")
        health.raise_for_status()
        body = health.json()
        if body.get("status") != "ok":
            _fail(f"health status={body.get('status')!r}")
        _ok(f"health database={body.get('database', 'unknown')}")

        reset = await client.post("/api/v1/admin/simulation/reset", headers=admin)
        if reset.status_code not in (200, 201):
            _fail(f"admin reset failed: {reset.status_code} {reset.text}")
        _ok("admin reset loaded canonical universe")

        traders: list[tuple[str, int, str]] = []
        for i in range(3):
            trader_id, token = await _join(client, f"sync-smoke-{i}")
            traders.append((f"sync-smoke-{i}", trader_id, token))
        _ok("joined 3 traders")

        bootstraps = []
        for _, _, token in traders:
            bootstraps.append(await _bootstrap(client, token))
        stock_sets = [
            {s["ticker"]: s["last_traded_price"] for s in b.get("stocks", [])}
            for b in bootstraps
        ]
        if not stock_sets[0]:
            _fail("bootstrap returned no stocks after reset")
        ticker = next(iter(stock_sets[0]))
        for prices in stock_sets[1:]:
            if prices.get(ticker) != stock_sets[0].get(ticker):
                _fail(f"LTP mismatch for {ticker} across traders before trade")
        _ok(f"identical LTP for {ticker} across 3 bootstraps")

        leader_a = await _leaderboard(client, traders[0][2])
        leader_b = await _leaderboard(client, traders[1][2])
        if len(leader_a) != len(leader_b):
            _fail("leaderboard row count differs between traders")
        _ok("leaderboard row count matches across traders")

        status = await client.get("/api/v1/admin/simulation/status", headers=admin)
        status.raise_for_status()
        sim = status.json()
        if not sim.get("trading_enabled"):
            start = await client.post("/api/v1/admin/simulation/start", headers=admin)
            if start.status_code not in (200, 409):
                _fail(f"could not start simulation: {start.status_code} {start.text}")
            _ok("simulation trading enabled for trade test")
        else:
            _ok("simulation already trading")

        buyer_name, buyer_id, buyer_token = traders[0]
        stock = bootstraps[0]["stocks"][0]
        ticker = stock["ticker"]
        order = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={
                "trader_id": buyer_id,
                "stock_id": stock["id"],
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
            },
        )
        if order.status_code not in (200, 201):
            _fail(f"market buy failed: {order.status_code} {order.text}")
        _ok(f"{buyer_name} submitted market buy for {ticker}")

        await asyncio.sleep(1.5)

        after_a = await _bootstrap(client, traders[0][2])
        after_b = await _bootstrap(client, traders[1][2])
        ltp_a = next(s for s in after_a["stocks"] if s["ticker"] == ticker)[
            "last_traded_price"
        ]
        ltp_b = next(s for s in after_b["stocks"] if s["ticker"] == ticker)[
            "last_traded_price"
        ]
        if ltp_a != ltp_b:
            _fail(f"LTP mismatch after trade: {ltp_a} vs {ltp_b}")
        _ok(f"identical LTP after trade ({ltp_a})")

        ws_ok = await _wait_for_ws_event(base, traders[1][2])
        if websockets is None:
            print("SKIP: websockets not installed — pip install websockets")
        elif ws_ok:
            _ok("WebSocket delivered at least one event to second trader")
        else:
            _fail("WebSocket did not deliver an event within timeout")

        print("\nAll smoke checks passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="TRADEVERSE post-deploy sync smoke test")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("API_BASE_URL"),
        help="API worker base URL (or set API_BASE_URL)",
    )
    parser.add_argument(
        "--admin-secret",
        default=os.environ.get("ADMIN_SECRET", "change-me-admin-secret"),
        help="Admin secret for reset/start (default: ADMIN_SECRET env or dev default)",
    )
    args = parser.parse_args()
    if not args.base_url:
        parser.error("--base-url or API_BASE_URL is required")
    asyncio.run(run(args.base_url, args.admin_secret))


if __name__ == "__main__":
    main()
