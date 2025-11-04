# Backend Request: Implement GET /family/my-invitations Endpoint

## Issue Report

**Date:** October 21, 2025  
**Reporter:** Mobile App Team  
**Priority:** High  
**Status:** Missing Endpoint

---

## Problem

The mobile app is attempting to call `GET /family/my-invitations` to retrieve invitations received by the current user, but the backend is returning **404 Not Found**.

### Current Backend Behavior

```
GET /family/my-invitations HTTP/1.1
→ 404 Not Found
→ Error: "Family not found: my-invitations"
```

The backend is treating `my-invitations` as a `family_id` parameter and trying to look up a family with that ID, which doesn't exist.

### Backend Logs

```
[2025-10-21 20:28:40,470] WARNING in Second_Brain_Database: [DATABASE] Family not found: my-invitations
INFO: 223.184.191.86:0 - "GET /family/my-invitations HTTP/1.1" 404 Not Found
```

---

## Required Solution

Implement a new endpoint that returns invitations **received by the authenticated user**, not invitations sent by a family.

### Endpoint Specification

**Method:** `GET`  
**Path:** `/family/my-invitations`  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 20 requests/hour per user

### Optional Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `status` | string | No | Filter by invitation status | `?status=pending` |

**Valid status values:**
- `pending` - Invitations awaiting response
- `accepted` - Invitations already accepted
- `declined` - Invitations that were declined
- `expired` - Invitations that expired before response

### Request Example

```bash
curl -X GET "https://dev-app-sbd.rohanbatra.in/family/my-invitations" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Accept: application/json"
```

### Response Schema

**Success (200 OK):**

```json
[
  {
    "invitation_id": "inv_584fd025c907445d",
    "family_id": "fam_32978f981bc246e5",
    "family_name": "Johnson Family",
    "inviter_user_id": "68f3c68604839468a2f226f0",
    "inviter_username": "rohan",
    "relationship_type": "child",
    "status": "pending",
    "expires_at": "2025-10-28T15:00:36Z",
    "created_at": "2025-10-21T15:00:36Z",
    "invitation_token": "VizHqsaUUx8uvpz2q5YRzi6r2yNK-7U8G_ApNa3jr6U"
  }
]
```

**Empty (200 OK):**
```json
[]
```

**Errors:**

| Status | Description | Response |
|--------|-------------|----------|
| 401 | Unauthorized | `{"detail": "Could not validate credentials"}` |
| 429 | Rate limit exceeded | `{"detail": "Rate limit exceeded"}` |
| 500 | Server error | `{"error": "FAILED_TO_FETCH_INVITATIONS", "message": "..."}` |

---

## Database Query Requirements

The endpoint should query the `family_invitations` table where:

1. **Invitee matches current user:**
   - `invitee_user_id = current_user.user_id` OR
   - `invitee_email = current_user.email` OR
   - `invitee_username = current_user.username`

2. **Optional status filter:**
   - If `?status=pending` → only return `status = 'pending'`
   - If no status provided → return all statuses

3. **Join with families table:**
   - To get `family_name` from `families.name`

4. **Join with users table:**
   - To get `inviter_username` from `users.username`

5. **Sort by:**
   - `created_at DESC` (newest first)

### Example SQL Query

```sql
SELECT 
  fi.invitation_id,
  fi.family_id,
  f.name as family_name,
  fi.invited_by as inviter_user_id,
  u.username as inviter_username,
  fi.relationship_type,
  fi.status,
  fi.expires_at,
  fi.created_at,
  fi.invitation_token
FROM family_invitations fi
LEFT JOIN families f ON fi.family_id = f.family_id
LEFT JOIN users u ON fi.invited_by = u.user_id
WHERE (
  fi.invitee_user_id = %s OR
  fi.invitee_email = %s OR
  fi.invitee_username = %s
)
AND (%s IS NULL OR fi.status = %s)  -- status filter
ORDER BY fi.created_at DESC
```

---

## Differences from Existing Endpoint

### Existing: `GET /family/{familyId}/invitations`
- Returns invitations **sent by a family** (admin view)
- Shows who the family has invited
- Requires family membership/admin access

### New: `GET /family/my-invitations`
- Returns invitations **received by the user** (invitee view)
- Shows who has invited the current user
- Only requires user authentication

---

## Security Considerations

1. **Authentication Required:**
   - Verify Bearer token
   - Extract `user_id` from token

2. **Authorization:**
   - Users can only see invitations sent TO them
   - Cannot see invitations sent to other users

3. **Data Privacy:**
   - Only return invitation details relevant to the invitee
   - Don't expose internal admin data

4. **Rate Limiting:**
   - Apply 20 requests/hour limit
   - Use user_id as rate limit key

---

## Testing Checklist

### Functional Tests

- [ ] User with pending invitations receives them in response
- [ ] User with no invitations receives empty array `[]`
- [ ] Filtering by `?status=pending` returns only pending invitations
- [ ] Filtering by `?status=accepted` returns only accepted invitations
- [ ] Response includes correct `family_name` from families table
- [ ] Response includes correct `inviter_username` from users table
- [ ] Invitations sorted by `created_at DESC` (newest first)

### Security Tests

- [ ] 401 when no Authorization header
- [ ] 401 when invalid/expired token
- [ ] User A cannot see invitations sent to User B
- [ ] Rate limiting enforced (20/hour)

### Edge Cases

- [ ] Family deleted after invitation sent → `family_name = "Unknown Family"`
- [ ] Inviter account deleted → `inviter_username = "Unknown User"`
- [ ] Expired invitations included in results (not filtered out)
- [ ] Multiple invitations to same user from different families

---

## Implementation Priority

**HIGH** - Mobile app feature is already implemented and waiting for this endpoint.

### Impact

- Mobile users cannot view family invitations received
- Shows error message: "Backend Endpoint Not Ready"
- Family feature is partially non-functional

### Timeline Needed

- Backend implementation: 1-2 hours
- Testing: 30 minutes
- Deployment: Immediate (dev environment)

---

## Example Backend Implementation (Python/FastAPI)

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from auth import get_current_user

router = APIRouter()

@router.get("/family/my-invitations")
async def get_my_invitations(
    status: Optional[str] = Query(None, regex="^(pending|accepted|declined|expired)$"),
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Get invitations received by the current user.
    
    Optional status filter: pending, accepted, declined, expired
    """
    try:
        # Query invitations where current user is the invitee
        query = """
            SELECT 
                fi.invitation_id,
                fi.family_id,
                COALESCE(f.name, 'Unknown Family') as family_name,
                fi.invited_by as inviter_user_id,
                COALESCE(u.username, 'Unknown User') as inviter_username,
                fi.relationship_type,
                fi.status,
                fi.expires_at,
                fi.created_at,
                fi.invitation_token
            FROM family_invitations fi
            LEFT JOIN families f ON fi.family_id = f.family_id
            LEFT JOIN users u ON fi.invited_by = u.user_id
            WHERE (
                fi.invitee_user_id = $1 OR
                fi.invitee_email = $2 OR
                fi.invitee_username = $3
            )
        """
        
        params = [current_user.user_id, current_user.email, current_user.username]
        
        # Add status filter if provided
        if status:
            query += " AND fi.status = $4"
            params.append(status)
        
        query += " ORDER BY fi.created_at DESC"
        
        invitations = await db.fetch_all(query, params)
        
        return [dict(row) for row in invitations]
        
    except Exception as e:
        logger.error(f"Failed to fetch invitations: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "FAILED_TO_FETCH_INVITATIONS",
                "message": "Unable to retrieve family invitations. Please try again later."
            }
        )
```

---

## Current Workaround

The mobile app shows a user-friendly error message:

```
🔧 Backend Endpoint Not Ready

The received invitations endpoint is not yet available on the backend.

Required Backend Endpoint:
GET /family/my-invitations

This endpoint should return invitations received by the 
current authenticated user.
```

Users cannot access the Received Invitations feature until this endpoint is implemented.

---

## Contact

**Mobile Team:** GitHub Copilot  
**Backend API:** dev-app-sbd.rohanbatra.in  
**Environment:** Development  
**Date Reported:** October 21, 2025

---

## Related Endpoints (Already Working)

✅ `GET /family/my-families` - Get families user belongs to  
✅ `GET /family/{familyId}/invitations` - Get invitations sent by family  
✅ `POST /family/{familyId}/invite` - Send invitation  
✅ `POST /family/invitation/{invitationId}/respond` - Accept/decline invitation  
❌ `GET /family/my-invitations` - **MISSING - NEEDS IMPLEMENTATION**

---

**End of Request**
