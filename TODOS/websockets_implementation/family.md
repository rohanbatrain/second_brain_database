# WebSocket Integration for Family Management (`family`)

This document outlines the WebSocket integration for the family management module. This module has many features that can be enhanced with real-time updates.

## Use Cases

### 1. Family Invitations

-   **Event:** A user is invited to a family.
-   **Action:** Send a WebSocket message to the invitee.
-   **Payload:**

    ```json
    {
        "type": "family_invitation_received",
        "data": {
            "invitation_id": "...",
            "family_name": "...",
            "inviter_username": "..."
        }
    }
    ```

-   **Event:** An invitation is accepted or declined.
-   **Action:** Send a message to the inviter (and other family admins).
-   **Payload:**

    ```json
    {
        "type": "family_invitation_responded",
        "data": {
            "invitation_id": "...",
            "invitee_username": "...",
            "action": "accepted" // or "declined"
        }
    }
    ```

### 2. Member & Role Changes

-   **Event:** A new member joins the family.
-   **Action:** Broadcast a message to all family members.
-   **Payload:**

    ```json
    {
        "type": "family_member_joined",
        "data": {
            "family_id": "...",
            "new_member_username": "..."
        }
    }
    ```

-   **Event:** A member is promoted to admin or demoted.
-   **Action:** Send a message to the affected user and broadcast a notification to other family members.
-   **Payload to affected user:**

    ```json
    {
        "type": "role_changed",
        "data": {
            "family_id": "...",
            "new_role": "admin" // or "member"
        }
    }
    ```

### 3. SBD Token Requests

-   **Event:** A family member requests SBD tokens.
-   **Action:** Send a message to all family admins.
-   **Payload:**

    ```json
    {
        "type": "token_request_created",
        "data": {
            "request_id": "...",
            "requester_username": "...",
            "amount": 100
        }
    }
    ```

-   **Event:** A token request is approved or denied.
-   **Action:** Send a message to the requesting user.
-   **Payload:**

    ```json
    {
        "type": "token_request_reviewed",
        "data": {
            "request_id": "...",
            "status": "approved" // or "denied",
            "reviewer_username": "..."
        }
    }
    ```

### 4. Account Freezing

-   **Event:** The family SBD account is frozen or unfrozen.
-   **Action:** Broadcast a message to all family members.
-   **Payload:**

    ```json
    {
        "type": "family_account_status_changed",
        "data": {
            "family_id": "...",
            "is_frozen": true // or false
        }
    }
    ```

## Implementation

### Backend

In `src/second_brain_database/managers/family_manager.py`, within the relevant functions (e.g., `invite_member`, `respond_to_invitation`, `promote_to_admin`, etc.), call the `ConnectionManager` to broadcast messages.

Example in `invite_member`:

```python
# After creating the invitation
from second_brain_database.websocket_manager import manager
import json

# Get all family members to notify
family_members = await self.get_family_members(family_id, inviter_id)
family_member_ids = [member["user_id"] for member in family_members]

# Notify the invitee
await manager.send_personal_message(
    json.dumps({
        "type": "family_invitation_received",
        "data": {
            "invitation_id": invitation_data["invitation_id"],
            "family_name": family["name"],
            "inviter_username": inviter["username"]
        }
    }),
    invitee_id
)

# Notify existing family members
await manager.broadcast_to_users(
    json.dumps({
        "type": "new_family_invitation_sent",
        "data": {
            "family_id": family_id,
            "invitee_identifier": identifier
        }
    }),
    family_member_ids
)
```

### Client-Side

```javascript
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    switch (message.type) {
        case "family_invitation_received":
            // Display a notification about the new invitation
            showNotification(`You have a new family invitation from ${message.data.inviter_username}!`);
            break;
        case "family_member_joined":
            // Update the family member list in the UI
            addFamilyMember(message.data.new_member_username);
            break;
        // ... handle other family-related message types
    }
};
```
