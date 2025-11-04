# WebSocket Integration for Avatars, Banners, and Themes

This document outlines the WebSocket integration for the `avatars`, `banners`, and `themes` modules. These modules share similar functionality, so their WebSocket integration is grouped together.

## Use Cases

### 1. Active Avatar/Banner/Theme Change

-   **Event:** A user changes their active avatar, banner, or theme for a specific application.
-   **Action:** Send a WebSocket message to all other active sessions for that user.
-   **Payload:**

    ```json
    {
        "type": "appearance_updated",
        "data": {
            "app_key": "...", // e.g., "emotion_tracker"
            "updated_item": "avatar", // or "banner", "theme"
            "new_item_id": "..."
        }
    }
    ```

-   **Benefit:** Ensures that the user's appearance is consistent across all their active sessions for a given application.

## Implementation

### Backend

In `src/second_brain_database/routes/avatars/routes.py`, within the `set_current_avatar` function, after successfully setting the avatar:

```python
# After successfully setting the avatar
from second_brain_database.websocket_manager import manager
import json

await manager.send_personal_message(
    json.dumps({
        "type": "appearance_updated",
        "data": {
            "app_key": app_key,
            "updated_item": "avatar",
            "new_item_id": avatar_id
        }
    }),
    str(current_user["_id"])
)
```

Similar logic would be applied to the `set_current_banner` function in `src/second_brain_database/routes/banners/routes.py` and any similar function for setting the current theme.

### Client-Side

```javascript
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "appearance_updated") {
        // Check if the update applies to the current application
        if (message.data.app_key === currentAppKey) {
            // Update the UI with the new avatar, banner, or theme
            if (message.data.updated_item === "avatar") {
                updateAvatar(message.data.new_item_id);
            } else if (message.data.updated_item === "banner") {
                updateBanner(message.data.new_item_id);
            } else if (message.data.updated_item === "theme") {
                updateTheme(message.data.new_item_id);
            }
        }
    }
    // ... other message types
};
```
