# WebSocket Integration for SBD Tokens (`sbd_tokens`)

This document outlines the WebSocket integration for the SBD tokens module, focusing on real-time notifications for token transfers.

## Use Cases

### 1. SBD Token Transfers

-   **Event:** A user sends SBD tokens to another user.
-   **Action:** Send a WebSocket message to both the sender and the receiver.
-   **Payload to Receiver:**

    ```json
    {
        "type": "sbd_tokens_received",
        "data": {
            "from_username": "...",
            "amount": 100,
            "new_balance": 1234
        }
    }
    ```

-   **Payload to Sender:**

    ```json
    {
        "type": "sbd_tokens_sent",
        "data": {
            "to_username": "...",
            "amount": 100,
            "new_balance": 5678
        }
    }
    ```

-   **Benefit:** Both parties involved in a transaction receive immediate confirmation and updated balances.

## Implementation

### Backend

In `src/second_brain_database/routes/sbd_tokens/routes.py`, within the `send_sbd_tokens` function, after the transaction is successfully processed:

```python
# After successfully processing the transaction
from second_brain_database.websocket_manager import manager
import json

# Get sender and receiver user objects
sender_user = await users_collection.find_one({"username": from_user})
receiver_user = await users_collection.find_one({"username": to_user})

# Notify the receiver
await manager.send_personal_message(
    json.dumps({
        "type": "sbd_tokens_received",
        "data": {
            "from_username": from_user,
            "amount": amount,
            "new_balance": receiver_user["sbd_tokens"]
        }
    }),
    str(receiver_user["_id"])
)

# Notify the sender
await manager.send_personal_message(
    json.dumps({
        "type": "sbd_tokens_sent",
        "data": {
            "to_username": to_user,
            "amount": amount,
            "new_balance": sender_user["sbd_tokens"]
        }
    }),
    str(sender_user["_id"])
)
```

### Client-Side

```javascript
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "sbd_tokens_received") {
        // Update the user's balance in the UI
        updateBalance(message.data.new_balance);
        showNotification(`You received ${message.data.amount} SBD tokens from ${message.data.from_username}.`);
    } else if (message.type === "sbd_tokens_sent") {
        // Update the user's balance in the UI
        updateBalance(message.data.new_balance);
        showNotification(`You sent ${message.data.amount} SBD tokens to ${message.data.to_username}.`);
    }
    // ... other message types
};
```
