"""WebSocket endpoint."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime.ws_manager import manager

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
        await manager.disconnect(websocket)
