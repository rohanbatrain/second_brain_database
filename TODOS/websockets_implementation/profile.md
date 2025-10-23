# WebSocket Integration for User Profile (`profile`)

This document describes the WebSocket integration for the user profile module. The primary use case is to notify a user's active sessions when their profile information has been updated.

## Use Cases

### 1. Profile Update Notification

-   **Event:** A user updates their profile information (e.g., name, bio).
-   **Action:** Send a WebSocket message to all active sessions for that user.
-   **Payload:**

    ```json
    {
        "type": "profile_updated",
        "data": {
            "updated_fields": ["user_first_name", "user_bio"],
            "message": "Your profile has been updated from another session."
        }
    }
    ```

-   **Benefit:** Ensures that all of the user's active sessions have the most up-to-date profile information, prompting a UI refresh if necessary.

## Implementation

### Backend

In `src/second_brain_database/routes/profile/routes.py`, within the `update_profile` function, after successfully updating the profile:

```python
# After successfully updating the profile
from second_brain_database.websocket_manager import manager
import json

await manager.send_personal_message(
    json.dumps({
        "type": "profile_updated",
        "data": {
            "updated_fields": list(updates.keys()),
            "message": "Your profile has been updated from another session."
        }
    }),
    str(current_user["_id"])
)
```

### Client-Side

```javascript
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "profile_updated") {
        // Refresh the user's profile information in the UI
        showNotification(message.data.message);
        // Example: refreshProfile();
    }
    // ... other message types
};
```
