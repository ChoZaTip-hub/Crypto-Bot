"""Root API router."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.router import api_router
from app.realtime.manager import ConnectionManager

router = APIRouter()
router.include_router(api_router)

ws_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"echo": data, "status": "connected"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
