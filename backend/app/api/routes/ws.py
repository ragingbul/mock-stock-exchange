"""WebSocket endpoint."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime.ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_json({"event": "CONNECTED", "payload": {"ok": True}})
        while True:
            # Keepalive / ignore client pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        logger.exception("websocket connection error")
        await manager.disconnect(websocket)
