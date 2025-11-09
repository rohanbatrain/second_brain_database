from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from second_brain_database.routes.auth.services.auth.login import get_current_user
from second_brain_database.websocket_manager import manager

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
    """
    Establish a WebSocket connection for real-time communication.

    This endpoint allows a client to establish a WebSocket connection with the server.
    Authentication is handled via a JWT token passed as a query parameter.
    Once connected, the server can push real-time updates to the client.

    Args:
        websocket (WebSocket): The WebSocket connection object.
        current_user (dict): The authenticated user, injected by Depends.
    """
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
