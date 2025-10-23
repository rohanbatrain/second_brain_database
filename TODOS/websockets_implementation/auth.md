# WebSocket Integration for Authentication (`auth`)

This document details the WebSocket integration for the authentication module. WebSockets can be used to provide real-time notifications for security-sensitive events.

## Use Cases

### 1. Password Change Notification

-   **Event:** When a user changes their password.
-   **Action:** Send a WebSocket message to all other active sessions for that user, notifying them of the password change.
-   **Benefit:** Allows other sessions to be gracefully logged out or to prompt the user to re-authenticate.

### 2. 2FA Status Change

-   **Event:** When a user enables or disables 2FA.
-   **Action:** Send a WebSocket message to all active sessions for that user.
-   **Benefit:** The UI can be updated in real-time to reflect the new 2FA status.

### 3. New Device Login

-   **Event:** When a user logs in from a new device (unrecognized user agent).
-   **Action:** Send a WebSocket message to all other active sessions for that user.
-   **Benefit:** Provides an immediate security alert to the user about potentially suspicious activity.

## Implementation

### Backend

In `src/second_brain_database/routes/auth/services/auth/password.py`, within the `change_user_password` function, after successfully changing the password:

```python
# After successfully changing the password
from second_brain_database.websocket_manager import manager
import json

await manager.send_personal_message(
    json.dumps({
        "type": "password_changed",
        "data": {
            "message": "Your password has been changed from another session."
        }
    }),
    str(current_user["_id"])
)
```

### Client-Side

```javascript
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "password_changed") {
        // Log out the user or prompt for re-authentication
        alert(message.data.message);
        // Example: logout();
    }
    // ... other message types
};
```
