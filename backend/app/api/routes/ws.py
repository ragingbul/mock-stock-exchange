"""WebSocket endpoint."""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.realtime.ws_manager import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    trader_id: int | None = None
    if token:
        try:
            payload = decode_token(token)
            raw_id = payload.get("trader_id")
            if raw_id is not None:
                trader_id = int(raw_id)
        except Exception:
            # Stale/invalid token must not block the public market feed.
            trader_id = None

    await manager.connect(websocket, trader_id=trader_id)
    try:
        await websocket.send_json(
            {
                "event": "CONNECTED",
                "payload": {"ok": True, "authenticated": trader_id is not None},
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
