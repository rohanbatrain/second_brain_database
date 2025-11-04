# Family SBD Permissions API Documentation

## Overview

This document describes the family SBD (Second Brain Database) permissions endpoints that have been implemented to support frontend integration. These endpoints allow family administrators to manage spending permissions for family members and provide the frontend with the necessary data to display permission controls.

## Authentication

All endpoints require a Bearer token in the `Authorization` header:
```
Authorization: Bearer <your_jwt_token>
```

## Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/family/{familyId}/members` | Get family members with spending permissions |
| GET | `/family/{familyId}/sbd-account` | Get family SBD account with member permissions |
| PUT | `/family/{familyId}/spending-permissions/{targetUserId}` | Update spending permissions for a member |

---

## 1. GET /family/{familyId}/members

**Purpose:** Retrieve all family members with their relationship information and spending permissions.

**Authentication:** Required (family member)

**Rate Limiting:** 3600 requests per hour per user

**Response Format:**
```json
[
  {
    "user_id": "user_123",
    "username": "john_doe",
    "email": "john@example.com",
    "relationship_type": "child",
    "role": "member",
    "joined_at": "2024-01-01T12:00:00Z",
    "spending_permissions": {
      "can_spend": true,
      "spending_limit": 1000,
      "last_updated": "2024-01-01T12:00:00Z",
      "updated_by": "admin_user"
    }
  }
]
```

**Key Fields:**
- `spending_permissions.can_spend`: Boolean indicating if member can spend
- `spending_permissions.spending_limit`: Integer limit (-1 = unlimited, 0 = no spending)
- `role`: "admin" or "member"

**Error Responses:**
- `401`: Unauthorized
- `403`: Not a family member
- `404`: Family not found

---

## 2. GET /family/{familyId}/sbd-account

**Purpose:** Retrieve family SBD account information including member permissions map.

**Authentication:** Required (family member)

**Rate Limiting:** 30 requests per hour per user

**Response Format:**
```json
{
  "account_username": "family_smith",
  "balance": 5000,
  "is_frozen": false,
  "frozen_by": null,
  "member_permissions": {
    "user_123": {
      "can_spend": true,
      "spending_limit": 1000,
      "updated_by": "admin_user",
      "updated_at": "2024-01-01T12:00:00Z"
    },
    "user_456": {
      "can_spend": false,
      "spending_limit": 0,
      "updated_by": "admin_user",
      "updated_at": "2024-01-01T12:00:00Z"
    }
  },
  "recent_transactions": [
    {
      "type": "spend",
      "amount": 100,
      "from_user": "john_doe",
      "to_user": "shop_system",
      "timestamp": "2024-01-01T15:00:00Z",
      "transaction_id": "txn_123456"
    }
  ]
}
```

**Key Changes from Previous Version:**
- Field renamed from `spending_permissions` to `member_permissions`
- Structure remains the same: `user_id -> permission_object`

**Frontend Usage:**
```javascript
// Access member permissions
const permissions = response.member_permissions;
const userPermission = permissions[currentUserId];

// Check if user can spend
if (userPermission.can_spend && (userPermission.spending_limit === -1 || amount <= userPermission.spending_limit)) {
  // Allow spending
}
```

**Error Responses:**
- `401`: Unauthorized
- `403`: Not a family member
- `404`: Family not found

---

## 3. PUT /family/{familyId}/spending-permissions/{targetUserId}

**Purpose:** Update spending permissions for a specific family member (admin only).

**Authentication:** Required (family administrator only)

**Rate Limiting:** 15 requests per hour per user

**Request Body:**
```json
{
  "spending_limit": 1000,
  "can_spend": true
}
```

**Request Parameters:**
- `spending_limit`: Integer (-1 = unlimited, 0 = no spending, positive = limit amount)
- `can_spend`: Boolean

**Response Format:**
```json
{
  "new_permissions": {
    "can_spend": true,
    "spending_limit": 1000,
    "updated_by": "admin_user",
    "updated_at": "2024-01-01T12:00:00Z"
  }
}
```

**Key Notes:**
- Response is wrapped in `new_permissions` object
- Only family administrators can call this endpoint
- Target user must be a family member

**Frontend Integration:**
```javascript
// Update permissions
const response = await fetch(`/family/${familyId}/spending-permissions/${targetUserId}`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    spending_limit: 1000,
    can_spend: true
  })
});

const result = await response.json();
// Update local state with result.new_permissions
updatePermissions(targetUserId, result.new_permissions);
```

**Error Responses:**
- `400`: Validation error (invalid spending_limit)
- `401`: Unauthorized
- `403`: Not a family administrator
- `404`: Family or target user not found

---

## Frontend Implementation Guidelines

### Permission Display Logic

```javascript
function getPermissionDisplayText(permission) {
  if (!permission.can_spend) {
    return "No spending allowed";
  }
  
  if (permission.spending_limit === -1) {
    return "Unlimited spending";
  }
  
  return `Up to ${permission.spending_limit} SBD`;
}

function canUserSpend(userId, amount, memberPermissions) {
  const permission = memberPermissions[userId];
  
  if (!permission || !permission.can_spend) {
    return false;
  }
  
  if (permission.spending_limit === -1) {
    return true; // Unlimited
  }
  
  return amount <= permission.spending_limit;
}
```

### UI State Management

```javascript
// Initial load
const familyMembers = await fetchFamilyMembers(familyId);
const sbdAccount = await fetchSBDAccount(familyId);

// Update permissions
async function updateMemberPermissions(targetUserId, newPermissions) {
  try {
    const response = await updatePermissionsAPI(familyId, targetUserId, newPermissions);
    
    // Update local state with server response
    setMemberPermissions(prev => ({
      ...prev,
      [targetUserId]: response.new_permissions
    }));
    
    // Refresh SBD account data
    const updatedAccount = await fetchSBDAccount(familyId);
    setSBDAccount(updatedAccount);
    
  } catch (error) {
    // Handle error - show user message
    showError("Failed to update permissions: " + error.message);
  }
}
```

### Error Handling

```javascript
function handleAPIError(error) {
  switch (error.status) {
    case 401:
      // Redirect to login
      redirectToLogin();
      break;
    case 403:
      if (error.detail?.error === "INSUFFICIENT_PERMISSIONS") {
        showError("Only family administrators can update permissions");
      } else {
        showError("You don't have permission to perform this action");
      }
      break;
    case 404:
      showError("Family or member not found");
      break;
    case 400:
      showError("Invalid request: " + error.detail?.message);
      break;
    default:
      showError("An unexpected error occurred");
  }
}
```

---

## Testing Examples

### cURL Commands

**Get Family Members:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  -X GET "https://api.example.com/family/fam_123/members"
```

**Get SBD Account:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  -X GET "https://api.example.com/family/fam_123/sbd-account"
```

**Update Permissions:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X PUT "https://api.example.com/family/fam_123/spending-permissions/user_456" \
     -d '{"spending_limit": 500, "can_spend": true}'
```

---

## Migration Notes

### Field Name Changes
- `spending_permissions` → `member_permissions` in GET /family/{familyId}/sbd-account response
- This change provides clearer semantics for the frontend

### Response Format Changes
- PUT endpoint now returns `{"new_permissions": {...}}` wrapper instead of full account object
- This provides more focused response data for permission updates

### Backward Compatibility
- GET /family/{familyId}/members still returns `spending_permissions` field
- No breaking changes to existing integrations

---

## Contact Information

For questions about this API or integration issues, please contact:
- Backend Team: [backend-team@example.com]
- API Documentation: [api-docs@example.com]

---

*Last Updated: October 22, 2025*
*API Version: v1.0*</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/docs/family_sbd_permissions_api_frontend.md