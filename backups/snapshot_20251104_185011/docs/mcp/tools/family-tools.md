# Family Management MCP Tools

## Overview

Family management tools provide comprehensive functionality for managing family accounts, members, relationships, invitations, and SBD token operations. All tools include security validation, audit logging, and proper authorization checks.

## Core Family Management Tools

### get_family_info

Get detailed information about a specific family.

**Parameters:**
- `family_id` (string, required): Family identifier

**Permissions Required:** `family:read`

**Example:**
```python
family_info = await mcp_client.call_tool("get_family_info", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0"
})

# Response
{
    "id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "name": "Smith Family",
    "description": "Our family account",
    "created_at": "2024-01-15T10:30:00Z",
    "member_count": 4,
    "owner_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "settings": {
        "notifications_enabled": true,
        "auto_approve_purchases": false
    }
}
```

### get_family_members

List all members of a family with their roles and status.

**Parameters:**
- `family_id` (string, required): Family identifier

**Permissions Required:** `family:read`

**Example:**
```python
members = await mcp_client.call_tool("get_family_members", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0"
})

# Response
[
    {
        "user_id": "64f8a1b2c3d4e5f6a7b8c9d1",
        "username": "john_smith",
        "email": "john@example.com",
        "role": "owner",
        "joined_at": "2024-01-15T10:30:00Z",
        "status": "active"
    },
    {
        "user_id": "64f8a1b2c3d4e5f6a7b8c9d2",
        "username": "jane_smith",
        "email": "jane@example.com",
        "role": "admin",
        "joined_at": "2024-01-16T14:20:00Z",
        "status": "active"
    }
]
```

### get_user_families

Get all families that the current user belongs to.

**Parameters:** None

**Permissions Required:** `family:read`

**Example:**
```python
families = await mcp_client.call_tool("get_user_families")

# Response
[
    {
        "id": "64f8a1b2c3d4e5f6a7b8c9d0",
        "name": "Smith Family",
        "role": "owner",
        "member_count": 4
    },
    {
        "id": "64f8a1b2c3d4e5f6a7b8c9d3",
        "name": "Extended Family",
        "role": "member",
        "member_count": 12
    }
]
```

### create_family

Create a new family account.

**Parameters:**
- `name` (string, required): Family name
- `description` (string, optional): Family description

**Permissions Required:** `family:create`

**Example:**
```python
new_family = await mcp_client.call_tool("create_family", {
    "name": "Johnson Family",
    "description": "Our new family account for shared resources"
})

# Response
{
    "id": "64f8a1b2c3d4e5f6a7b8c9d4",
    "name": "Johnson Family",
    "description": "Our new family account for shared resources",
    "created_at": "2024-01-20T09:15:00Z",
    "owner_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "member_count": 1
}
```

### update_family_settings

Update family configuration and settings.

**Parameters:**
- `family_id` (string, required): Family identifier
- `settings` (object, required): Settings to update

**Permissions Required:** `family:admin`

**Example:**
```python
result = await mcp_client.call_tool("update_family_settings", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "settings": {
        "notifications_enabled": true,
        "auto_approve_purchases": false,
        "spending_limit": 500
    }
})

# Response
{
    "success": true,
    "updated_settings": {
        "notifications_enabled": true,
        "auto_approve_purchases": false,
        "spending_limit": 500
    }
}
```

### delete_family

Delete a family account (owner only).

**Parameters:**
- `family_id` (string, required): Family identifier
- `confirmation` (string, required): Must be "DELETE" to confirm

**Permissions Required:** `family:delete`

**Example:**
```python
result = await mcp_client.call_tool("delete_family", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "confirmation": "DELETE"
})

# Response
{
    "success": true,
    "message": "Family deleted successfully"
}
```

## Member Management Tools

### add_family_member

Add a new member to the family via invitation.

**Parameters:**
- `family_id` (string, required): Family identifier
- `email` (string, required): Email address to invite
- `role` (string, optional): Member role (default: "member")

**Permissions Required:** `family:admin`

**Example:**
```python
result = await mcp_client.call_tool("add_family_member", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "email": "newmember@example.com",
    "role": "member"
})

# Response
{
    "success": true,
    "invitation_id": "64f8a1b2c3d4e5f6a7b8c9d5",
    "message": "Invitation sent successfully"
}
```

### remove_family_member

Remove a member from the family.

**Parameters:**
- `family_id` (string, required): Family identifier
- `user_id` (string, required): User ID to remove

**Permissions Required:** `family:admin`

**Example:**
```python
result = await mcp_client.call_tool("remove_family_member", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "user_id": "64f8a1b2c3d4e5f6a7b8c9d2"
})

# Response
{
    "success": true,
    "message": "Member removed successfully"
}
```

### update_family_member_role

Update a member's role within the family.

**Parameters:**
- `family_id` (string, required): Family identifier
- `user_id` (string, required): User ID to update
- `new_role` (string, required): New role ("member", "admin")

**Permissions Required:** `family:admin`

**Example:**
```python
result = await mcp_client.call_tool("update_family_member_role", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "user_id": "64f8a1b2c3d4e5f6a7b8c9d2",
    "new_role": "admin"
})

# Response
{
    "success": true,
    "message": "Member role updated successfully"
}
```

## Relationship Management Tools

### update_relationship

Update bidirectional relationship between family members.

**Parameters:**
- `family_id` (string, required): Family identifier
- `user_id` (string, required): First user ID
- `related_user_id` (string, required): Second user ID
- `relationship_type` (string, required): Relationship type

**Permissions Required:** `family:admin`

**Example:**
```python
result = await mcp_client.call_tool("update_relationship", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "user_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "related_user_id": "64f8a1b2c3d4e5f6a7b8c9d2",
    "relationship_type": "parent-child"
})

# Response
{
    "success": true,
    "message": "Relationship updated successfully"
}
```

### get_family_relationships

Get all relationships within a family.

**Parameters:**
- `family_id` (string, required): Family identifier

**Permissions Required:** `family:read`

**Example:**
```python
relationships = await mcp_client.call_tool("get_family_relationships", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0"
})

# Response
[
    {
        "user_id": "64f8a1b2c3d4e5f6a7b8c9d1",
        "related_user_id": "64f8a1b2c3d4e5f6a7b8c9d2",
        "relationship_type": "parent-child",
        "created_at": "2024-01-16T10:00:00Z"
    }
]
```

## Invitation Management Tools

### send_family_invitation

Send an invitation to join the family.

**Parameters:**
- `family_id` (string, required): Family identifier
- `email` (string, required): Email address to invite
- `role` (string, optional): Invited role (default: "member")
- `message` (string, optional): Personal message

**Permissions Required:** `family:admin`

**Example:**
```python
result = await mcp_client.call_tool("send_family_invitation", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "email": "cousin@example.com",
    "role": "member",
    "message": "Join our family account!"
})

# Response
{
    "success": true,
    "invitation_id": "64f8a1b2c3d4e5f6a7b8c9d6",
    "expires_at": "2024-02-01T10:00:00Z"
}
```

### accept_family_invitation

Accept a family invitation.

**Parameters:**
- `invitation_id` (string, required): Invitation identifier

**Permissions Required:** `family:join`

**Example:**
```python
result = await mcp_client.call_tool("accept_family_invitation", {
    "invitation_id": "64f8a1b2c3d4e5f6a7b8c9d6"
})

# Response
{
    "success": true,
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "role": "member",
    "message": "Successfully joined the family"
}
```

### decline_family_invitation

Decline a family invitation.

**Parameters:**
- `invitation_id` (string, required): Invitation identifier

**Permissions Required:** `family:join`

**Example:**
```python
result = await mcp_client.call_tool("decline_family_invitation", {
    "invitation_id": "64f8a1b2c3d4e5f6a7b8c9d6"
})

# Response
{
    "success": true,
    "message": "Invitation declined"
}
```

### list_pending_invitations

List all pending invitations for the current user.

**Parameters:** None

**Permissions Required:** `family:read`

**Example:**
```python
invitations = await mcp_client.call_tool("list_pending_invitations")

# Response
[
    {
        "invitation_id": "64f8a1b2c3d4e5f6a7b8c9d6",
        "family_name": "Johnson Family",
        "invited_by": "john@example.com",
        "role": "member",
        "expires_at": "2024-02-01T10:00:00Z"
    }
]
```

## SBD Token Management Tools

### get_family_sbd_account

Get family SBD token account information.

**Parameters:**
- `family_id` (string, required): Family identifier

**Permissions Required:** `family:read`

**Example:**
```python
account = await mcp_client.call_tool("get_family_sbd_account", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0"
})

# Response
{
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "balance": 1500,
    "pending_requests": 2,
    "total_earned": 5000,
    "total_spent": 3500,
    "account_status": "active"
}
```

### create_token_request

Request SBD tokens for family use.

**Parameters:**
- `family_id` (string, required): Family identifier
- `amount` (number, required): Token amount requested
- `reason` (string, required): Reason for request

**Permissions Required:** `family:token_request`

**Example:**
```python
result = await mcp_client.call_tool("create_token_request", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "amount": 100,
    "reason": "Purchase new avatars for family members"
})

# Response
{
    "success": true,
    "request_id": "64f8a1b2c3d4e5f6a7b8c9d7",
    "status": "pending",
    "expires_at": "2024-02-01T10:00:00Z"
}
```

### review_token_request

Review and approve/deny a token request (admin only).

**Parameters:**
- `request_id` (string, required): Token request identifier
- `action` (string, required): "approve" or "deny"
- `admin_notes` (string, optional): Admin notes

**Permissions Required:** `family:admin`

**Example:**
```python
result = await mcp_client.call_tool("review_token_request", {
    "request_id": "64f8a1b2c3d4e5f6a7b8c9d7",
    "action": "approve",
    "admin_notes": "Approved for avatar purchases"
})

# Response
{
    "success": true,
    "new_status": "approved",
    "tokens_granted": 100,
    "message": "Token request approved"
}
```

### get_token_requests

List token requests for a family.

**Parameters:**
- `family_id` (string, required): Family identifier
- `status` (string, optional): Filter by status

**Permissions Required:** `family:read`

**Example:**
```python
requests = await mcp_client.call_tool("get_token_requests", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "status": "pending"
})

# Response
[
    {
        "request_id": "64f8a1b2c3d4e5f6a7b8c9d7",
        "requested_by": "jane@example.com",
        "amount": 100,
        "reason": "Purchase new avatars",
        "status": "pending",
        "created_at": "2024-01-20T14:30:00Z"
    }
]
```

## Administration Tools

### promote_to_admin

Promote a family member to admin role.

**Parameters:**
- `family_id` (string, required): Family identifier
- `user_id` (string, required): User ID to promote

**Permissions Required:** `family:admin`

**Example:**
```python
result = await mcp_client.call_tool("promote_to_admin", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "user_id": "64f8a1b2c3d4e5f6a7b8c9d2"
})

# Response
{
    "success": true,
    "message": "Member promoted to admin successfully"
}
```

### get_admin_actions_log

Get audit log of admin actions within the family.

**Parameters:**
- `family_id` (string, required): Family identifier
- `limit` (number, optional): Number of entries to return (default: 50)

**Permissions Required:** `family:admin`

**Example:**
```python
log_entries = await mcp_client.call_tool("get_admin_actions_log", {
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "limit": 20
})

# Response
[
    {
        "action": "member_promoted",
        "performed_by": "john@example.com",
        "target_user": "jane@example.com",
        "timestamp": "2024-01-20T15:30:00Z",
        "details": {
            "old_role": "member",
            "new_role": "admin"
        }
    }
]
```

## Error Handling

### Common Errors

**Authentication Required:**
```json
{
    "error": {
        "code": "AUTHENTICATION_ERROR",
        "message": "Authentication required for family operations"
    }
}
```

**Insufficient Permissions:**
```json
{
    "error": {
        "code": "AUTHORIZATION_ERROR",
        "message": "Insufficient permissions for family administration",
        "details": {
            "required_permissions": ["family:admin"],
            "user_role": "member"
        }
    }
}
```

**Family Not Found:**
```json
{
    "error": {
        "code": "FAMILY_NOT_FOUND",
        "message": "Family not found or access denied",
        "details": {
            "family_id": "64f8a1b2c3d4e5f6a7b8c9d0"
        }
    }
}
```

**Rate Limit Exceeded:**
```json
{
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Too many family operations. Please wait before retrying.",
        "details": {
            "retry_after": 60,
            "limit": "10 requests per minute"
        }
    }
}
```

## Best Practices

### Security Considerations

1. **Validate family access** before any operations
2. **Use least privilege** - request minimal required permissions
3. **Audit sensitive operations** like member removal or role changes
4. **Implement proper error handling** for security failures

### Performance Optimization

1. **Cache family information** for repeated access
2. **Batch member operations** when possible
3. **Use pagination** for large member lists
4. **Monitor rate limits** and implement backoff

### User Experience

1. **Provide clear error messages** for common failures
2. **Validate inputs** before sending requests
3. **Handle async operations** properly with loading states
4. **Implement retry logic** for transient failures