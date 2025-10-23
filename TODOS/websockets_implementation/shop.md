# WebSocket Integration for the Shop (`shop`)

This document describes how to integrate WebSockets into the shop module for real-time updates, particularly for purchases made using family SBD tokens.

## Use Cases

### 1. Family Purchase Notifications

-   **Event:** A user makes a purchase from the shop using a family's shared SBD token account.
-   **Action:** Broadcast a message to all members of that family.
-   **Payload:**

    ```json
    {
        "type": "family_shop_purchase",
        "data": {
            "family_id": "...",
            "purchaser_username": "...",
            "item_id": "...",
            "item_type": "theme" // or "avatar", "banner", "bundle"
            "price": 250
        }
    }
    ```

-   **Benefit:** All family members are immediately aware of how the shared funds are being used.

### 2. Real-time Shop Updates (Future Enhancement)

-   **Event:** A new item is added to the shop, or an existing item's price changes.
-   **Action:** Broadcast a message to all connected users.
-   **Payload:**

    ```json
    {
        "type": "shop_updated",
        "data": {
            "new_items": [...],
            "updated_items": [...]
        }
    }
    ```

-   **Benefit:** The shop UI can be updated in real-time for all users without requiring a page refresh.

## Implementation

### Backend

In `src/second_brain_database/routes/shop/routes.py`, within the `process_payment` function, when a family payment is processed:

```python
# Inside process_payment, after a successful family payment
if payment_details["payment_type"] == "family":
    from second_brain_database.websocket_manager import manager
    import json

    family_id = payment_details["family_id"]
    family_members = await family_manager.get_family_members(family_id, user_id) # Assuming you have user_id
    family_member_ids = [member["user_id"] for member in family_members]

    await manager.broadcast_to_users(
        json.dumps({
            "type": "family_shop_purchase",
            "data": {
                "family_id": family_id,
                "purchaser_username": current_user["username"],
                "item_id": item_details.get(f"{item_details.get('type')}_id"),
                "item_type": item_details.get("type"),
                "price": amount
            }
        }),
        family_member_ids
    )
```

### Client-Side

```javascript
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "family_shop_purchase") {
        // Display a notification about the purchase
        showNotification(`${message.data.purchaser_username} bought a ${message.data.item_type} for ${message.data.price} SBD tokens from your family account.`);
    }
    // ... other message types
};
```
