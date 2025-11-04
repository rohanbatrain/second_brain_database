
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from second_brain_database.websocket_manager import manager
from second_brain_database.routes.auth.services.auth.login import get_current_user

router = APIRouter()

async def get_current_user_ws(token: Optional[str] = Query(None)):
    """
    Dependency function to retrieve the current authenticated user for WebSocket connections.
    The token is passed as a query parameter.
    """
    if token is None:
        return None
    return await get_current_user(token)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, current_user: dict = Depends(get_current_user_ws)):
    if current_user is None:
        await websocket.close(code=1008)
        return

    user_id = str(current_user["_id"])
    await manager.connect(user_id, websocket)
    try:
        while True:
            # The server can listen for messages from the client if needed
            # For now, we just keep the connection open
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
