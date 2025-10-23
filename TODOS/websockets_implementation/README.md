# WebSocket Integration Strategy

This document outlines a comprehensive strategy for integrating WebSockets into the Second Brain Database API. The goal is to enhance real-time functionality, improve user experience, and provide a more interactive and responsive application.

## Core Concepts

The WebSocket integration will be built around a centralized `ConnectionManager` that handles all WebSocket connections. This manager will be responsible for:

-   **Connection Management:** Tracking active connections for each user.
-   **Authentication:** Ensuring that only authenticated users can establish a WebSocket connection.
-   **Broadcasting:** Sending messages to specific users, groups of users (e.g., a family), or all connected users.

## Use Cases

WebSockets will be integrated into the following modules to provide real-time updates:

-   **[Authentication (`auth`)](auth.md):** Real-time notifications for security events like password changes, 2FA updates, and new device logins.
-   **[Family Management (`family`)](family.md):** Live updates for family events such as invitations, member joins/leaves, role changes, and SBD token requests.
-   **[Shop (`shop`)](shop.md):** Real-time notifications for family purchases and, in the future, live updates for new items or price changes.
-   **[SBD Tokens (`sbd_tokens`)](sbd_tokens.md):** Real-time updates on SBD token transfers and balance changes.
-   **[User Profile (`profile`)](profile.md):** Notifications when a user's profile is updated.
-   **[Avatars, Banners, and Themes](avatars_banners_themes.md):** Real-time updates when a user's avatar, banner, or theme is changed.

## Implementation Details

The implementation will follow these steps:

1.  **Create a `ConnectionManager`:** A new file, `src/second_brain_database/websocket_manager.py`, will house the `ConnectionManager` class.
2.  **Create a WebSocket Endpoint:** A new route, `/ws`, will be created in `src/second_brain_database/routes/websockets.py` to handle WebSocket connections.
3.  **Implement Authentication:** The WebSocket endpoint will use a custom dependency to authenticate users via a token passed as a query parameter.
4.  **Integrate Broadcasting:** The existing manager classes (e.g., `FamilyManager`, `ShopManager`) will be modified to call the `ConnectionManager` to broadcast messages when relevant events occur.
5.  **Client-Side Implementation:** The client-side application will establish a WebSocket connection and listen for incoming messages to update the UI in real-time.

Each of the linked markdown files provides a detailed breakdown of the WebSocket integration for that specific module, including code examples for both the backend and client-side.
