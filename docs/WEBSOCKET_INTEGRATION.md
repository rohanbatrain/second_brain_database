
# WebSocket Integration for Second Brain Database

This document outlines a plan to integrate WebSockets into the Second Brain Database API to enhance real-time functionality and user experience.

## 1. Introduction to WebSockets

WebSockets provide a full-duplex communication channel over a single, long-lived TCP connection. This allows for real-time, bidirectional communication between the client and server, making them ideal for applications that require instant updates and notifications.

By integrating WebSockets, we can move from a traditional request-response model to an event-driven architecture for specific features, resulting in a more interactive and responsive application.

## 2. Proposed Use Cases

Based on the existing codebase, the following features are prime candidates for WebSocket integration:

### 2.1. Real-time Family Notifications

The family management system involves numerous events that would benefit from real-time notifications.

*   **Invitations:**
    *   When a user is invited to a family, they receive a real-time notification.
    *   When an invitation is accepted, declined, or cancelled, the inviting user (and other family admins) are notified instantly.
*   **Role Changes:**
    *   When a user is promoted to admin or demoted, they receive a real-time notification of their new role.
*   **SBD Token Management:**
    *   When a family member requests SBD tokens, admins are notified in real-time.
    *   When a token request is approved or rejected, the requesting member is notified.
*   **Account Status:**
    *   All family members are notified in real-time if the family SBD account is frozen or unfrozen.

### 2.2. Live Shop Updates

The shop can be made more dynamic with WebSockets.

*   **Family Purchases:**
    *   When a purchase is made using a family's SBD tokens, all family members (or at least the admins) receive a real-time notification of the transaction.
*   **New Items (Future Enhancement):**
    *   When new items are added to the shop, the UI can be updated in real-time for all connected users without requiring a page refresh.

## 3. Implementation Guide

We will use FastAPI's built-in support for WebSockets. The implementation will involve creating a connection manager, defining WebSocket endpoints, and broadcasting messages.

### 3.1. Connection Manager

To manage active WebSocket connections, we will create a `ConnectionManager` class. This class will handle connecting, disconnecting, and broadcasting messages to clients.

**Proposed new file:** `src/second_brain_database/websocket_manager.py`

```python
from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_text(message)

    async def broadcast_to_users(self, message: str, user_ids: List[str]):
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

manager = ConnectionManager()
```

### 3.2. WebSocket Endpoint

We will create a new WebSocket endpoint to handle client connections. This endpoint will be responsible for authenticating the user and managing the WebSocket connection.

A new file `src/second_brain_database/routes/websockets.py` could be created for this.

```python
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from second_brain_database.routes.auth import get_current_user
from second_brain_database.websocket_manager import manager

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    await manager.connect(user_id, websocket)
    try:
        while True:
            # We can receive messages from the client here if needed
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
```

This new router would then be included in `src/second_brain_database/main.py`.

### 3.3. Broadcasting Messages

To broadcast messages, we will use the `ConnectionManager`. For example, when a family invitation is sent, we can call the `send_personal_message` method to notify the invitee.

In `src/second_brain_database/managers/family_manager.py`, within the `invite_member` function:

```python
# After successfully creating the invitation
from second_brain_database.websocket_manager import manager
import json

# Notify the invitee
if invitee:
    await manager.send_personal_message(
        json.dumps({
            "type": "family_invitation",
            "data": {
                "invitation_id": invitation["_id"],
                "family_name": family["name"],
                "inviter_username": inviter["username"]
            }
        }),
        str(invitee["_id"])
    )
```

## 4. Client-Side Implementation

On the client-side, we will use JavaScript to establish a WebSocket connection and handle incoming messages.

```javascript
const token = "your_jwt_token"; // The user's JWT token
const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

ws.onopen = () => {
    console.log("WebSocket connection established");
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    console.log("Received message:", message);

    if (message.type === "family_invitation") {
        // Display a notification to the user
        alert(`You have a new family invitation from ${message.data.inviter_username} to join ${message.data.family_name}!`);
    }
    // Handle other message types...
};

ws.onclose = () => {
    console.log("WebSocket connection closed");
};

ws.onerror = (error) => {
    console.error("WebSocket error:", error);
};
```
Note that the `get_current_user` dependency will need to be updated to also read the token from a query parameter for the websocket connection.

## 5. Next Steps

1.  **Create `websocket_manager.py`:** Implement the `ConnectionManager` class as described above.
2.  **Create WebSocket Endpoint:** Create the `/ws` endpoint and include its router in `main.py`.
3.  **Modify `get_current_user`:** Update the authentication dependency to accept the token from a query parameter for WebSocket connections.
4.  **Integrate Broadcasting:** Modify the relevant manager functions (e.g., `family_manager.py`) to call the `ConnectionManager` to broadcast messages for the use cases identified.
5.  **Client-Side Implementation:** Implement the client-side logic to connect to the WebSocket and handle real-time updates.
