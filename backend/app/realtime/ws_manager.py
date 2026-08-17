"""Simple WebSocket fan-out for market events."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

PRIVATE_EVENTS = frozenset({"WALLET_UPDATED", "PORTFOLIO_UPDATED", "IPO_APPLICATION_UPDATED"})


@dataclass
class _Client:
    websocket: WebSocket
    trader_id: int | None = None


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[_Client] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, *, trader_id: int | None = None) -> None:
        await websocket.accept()
        client = _Client(websocket=websocket, trader_id=trader_id)
        async with self._lock:
            self.active.append(client)
        auth_note = f"trader={trader_id}" if trader_id is not None else "public"
        logger.info("WebSocket connected (%s, clients=%s)", auth_note, len(self.active))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active = [c for c in self.active if c.websocket is not websocket]
        logger.info("WebSocket disconnected (clients=%s)", len(self.active))

    async def _send(self, clients: list[_Client], event: str, payload: dict[str, Any]) -> None:
        message = json.dumps({"event": event, "payload": payload}, default=str)
        dead: list[WebSocket] = []
        for client in clients:
            try:
                await client.websocket.send_text(message)
            except Exception:
                dead.append(client.websocket)
        for ws in dead:
            await self.disconnect(ws)

    async def broadcast_public(self, event: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            peers = list(self.active)
        await self._send(peers, event, payload)

    async def broadcast_private(
        self, trader_id: int, event: str, payload: dict[str, Any]
    ) -> None:
        async with self._lock:
            peers = [c for c in self.active if c.trader_id == trader_id]
        await self._send(peers, event, payload)

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        """Route public events to all clients; private events to authenticated owner only."""
        trader_id = payload.get("trader_id")
        if event in PRIVATE_EVENTS or (event == "CONDITIONAL_UPDATED" and trader_id is not None):
            if trader_id is not None:
                await self.broadcast_private(int(trader_id), event, payload)
            return
        await self.broadcast_public(event, payload)


manager = ConnectionManager()
