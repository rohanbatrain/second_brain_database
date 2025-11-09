# Production-Ready WebRTC Signaling Server Design

This document outlines the architecture and design for integrating a scalable, production-ready WebRTC signaling server into the Second Brain Database backend.

## 1. Overview

The goal is to add real-time communication capabilities to the application using WebRTC. Since WebRTC is peer-to-peer, it requires a central server for "signaling"—the process of establishing a connection between clients.

This implementation will create a robust signaling server using **FastAPI WebSockets**. To ensure scalability across multiple server instances in a production environment, we will use a **Redis Pub/Sub** model for broadcasting messages.

## 2. Core Concepts

-   **Signaling**: The process of coordinating WebRTC communication. Our server will manage this by passing messages like offers, answers, and ICE candidates between clients.
-   **Rooms**: Isolated communication channels. A user connects to a specific `room_id`, and signaling messages are broadcast only to other users in the same room.
-   **Scalability via Redis Pub/Sub**: To support horizontal scaling (running multiple instances of the application), we cannot rely on in-memory connection management. When one server instance receives a message, it will publish it to a Redis channel for that room. All other instances will subscribe to these channels and forward messages to their connected clients as needed. The project already uses Redis, making this a natural extension.
-   **STUN/TURN Configuration**: For WebRTC to work reliably across diverse network environments (especially NATs and firewalls), clients need STUN and TURN servers. The backend will provide a secure endpoint for clients to fetch this configuration.

## 3. Proposed Directory Structure

To keep the WebRTC feature modular and self-contained, all new logic will be placed within a dedicated `webrtc` directory.

```
src/second_brain_database/
├── webrtc/
│   ├── __init__.py
│   ├── connection_manager.py   # Core logic for managing connections and Redis Pub/Sub.
│   ├── dependencies.py         # WebSocket-specific authentication dependencies.
│   ├── router.py               # FastAPI router with WebSocket and API endpoints.
│   └── schemas.py              # Pydantic models for all signaling messages.
│
├── routes/
│   └── (existing routes...)
│
└── main.py                     # Main application file to include the new router.
```

## 4. Component Breakdown

#### `webrtc/schemas.py`

This file will define the data contracts for all signaling messages using Pydantic, ensuring that communication is strongly-typed and validated.

-   **`WebRtcMessage`**: A base model with fields like `type` (e.g., `offer`, `answer`, `ice-candidate`) and `payload`.
-   **`SdpPayload`**: Carries the SDP data for offers and answers.
-   **`IceCandidatePayload`**: Carries data for an ICE candidate.
-   Enums for message types to avoid string literals.

#### `webrtc/dependencies.py`

This file will contain dependency-injection functions for handling authentication on WebSocket connections, separate from standard HTTP requests.

-   **`get_current_user_ws(...)`**: A function that extracts a JWT from the WebSocket's query parameters (`/ws/webrtc/{room_id}?token=...`), validates it using the existing authentication logic, and returns the user object. If the token is invalid or missing, it will raise an exception to close the connection.

#### `webrtc/connection_manager.py`

This is the core of the signaling logic, designed to be completely stateless regarding connections, which are managed by the router instances.

-   **`WebRtcManager` class**:
    -   Does not hold a list of active WebSocket connections.
    -   Provides methods for publishing messages to Redis: `publish_to_room(room_id, message)`.
    -   Provides a method for creating a subscriber: `subscribe_to_room(room_id)` which yields messages from the Redis channel.
    -   Manages room state (e.g., lists of participants) in Redis Sets for a globally consistent view.

#### `webrtc/router.py`

This file defines the public-facing endpoints for the WebRTC feature.

-   **WebSocket Endpoint**: `router.websocket("/ws/webrtc/{room_id}")`
    -   Authenticates the connection using the `get_current_user_ws` dependency.
    -   Instantiates a Redis subscriber that listens for messages on the `room_id` channel.
    -   Listens for incoming messages from the client's WebSocket.
    -   When a message is received from the client, it's validated with the Pydantic schemas and published to Redis using the `WebRtcManager`.
    -   When a message is received from the Redis subscriber, it's sent down to the client's WebSocket.
-   **Configuration Endpoint**: `router.get("/api/v1/webrtc/config")`
    -   A standard, authenticated REST endpoint.
    -   Returns a JSON object containing the configured STUN and TURN server URLs.

#### `main.py`

The main application file will be updated to include the new router.

```python
# src/second_brain_database/main.py
from .webrtc import router as webrtc_router

# ... other imports

app = FastAPI(...)

# ... include other routers

app.include_router(webrtc_router.router)
```

## 5. Authentication Flow for WebSockets

1.  A client first authenticates via a standard REST endpoint to obtain a JWT access token.
2.  The client then initiates the WebSocket connection and includes the token as a query parameter:
    `wss://your.domain/ws/webrtc/some-room-id?token=eyJhbGciOi...`
3.  On the server, the `get_current_user_ws` dependency function extracts and validates this token.
4.  If the token is valid, the WebSocket connection is accepted. Otherwise, the server sends a close frame `4003` (or similar) and terminates the connection.

## 6. Example Signaling Flow

1.  **User A connects**: `Client A` connects to `/ws/webrtc/room123?token=...`.
2.  **User B connects**: `Client B` connects to the same room. The `WebRtcManager` can publish a `user-joined` event to the room's Redis channel, notifying `Client A`.
3.  **Offer**: `Client A` creates a WebRTC `offer` and sends it to the server. The server instance receiving this message publishes it to the `room123` Redis channel. The message includes who it's from and who it's for (or is broadcast to all other participants).
4.  **Answer**: The server instance managing `Client B` gets the message from Redis and forwards it. `Client B` receives the `offer`, creates an `answer`, and sends it back to the server. This is then published to Redis and forwarded back to `Client A`.
5.  **ICE Candidates**: The same process is repeated for exchanging ICE candidates.
6.  **P2P Connection**: Once signaling is complete, Client A and Client B have a direct peer-to-peer connection. The signaling server is no longer involved in their communication, only in managing room membership or further signaling needs.
