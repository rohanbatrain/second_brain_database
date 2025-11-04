# Backend Issue: Missing/Empty Fields in Invitation Responses

**Date:** October 21, 2025  
**Reporter:** Mobile App Team  
**Priority:** HIGH  
**Status:** 🔴 Data Integrity Issue  
**Affected Endpoint:** `GET /family/my-invitations`

---

## Executive Summary

The `GET /family/my-invitations` endpoint is now responding (✅ no longer 404), but the data returned is **incomplete**. Critical fields like `family_name`, `invitee_email`, `invitee_username`, and `invited_by_username` are either **null** or **empty strings**, making invitations impossible to understand or manage.

---

## Current Backend Response (Actual)

```json
{
  "invitation_id": "inv_4d4bd60648df440c",
  "family_name": "",
  "inviter_username": "rohan",
  "relationship_type": "child",
  "status": "pending",
  "expires_at": "2025-10-28T15:11:51.812000",
  "created_at": "2025-10-21T15:11:51.812000"
}
```

### ❌ Missing/Empty Fields:
- `family_id`: **null** (should be family UUID)
- `family_name`: **empty string ""** (should be family name from JOIN)
- `invited_by`: **null** (should be inviter user_id)
- `invited_by_username`: **null** (field doesn't exist, but `inviter_username` does exist)
- `invitee_email`: **null** (should be recipient's email)
- `invitee_username`: **null** (should be recipient's username)

### ✅ Working Fields:
- `invitation_id`: Correct
- `inviter_username`: Correct (though field name inconsistent)
- `relationship_type`: Correct
- `status`: Correct
- `expires_at`: Correct
- `created_at`: Correct

---

## Expected Backend Response (Required)

```json
{
  "invitation_id": "inv_4d4bd60648df440c",
  "family_id": "fam_32978f981bc246e5",
  "family_name": "Johnson Family",
  "inviter_user_id": "68f3c68604839468a2f226f0",
  "inviter_username": "rohan",
  "relationship_type": "child",
  "status": "pending",
  "expires_at": "2025-10-28T15:11:51.812000",
  "created_at": "2025-10-21T15:11:51.812000",
  "invitation_token": "VizHqsaUUx8uvpz2q5YRzi6r2yNK-7U8G_ApNa3jr6U"
}
```

---

## Root Cause Analysis

### 1. Missing JOIN with `families` Table

The query is not joining with the `families` table to populate `family_name`.

**Current (broken):**
```sql
SELECT * FROM family_invitations 
WHERE invitee_user_id = ?
```

**Required:**
```sql
SELECT 
  fi.*,
  f.name as family_name,
  f.family_id
FROM family_invitations fi
LEFT JOIN families f ON fi.family_id = f.family_id
WHERE fi.invitee_user_id = ?
```

### 2. Missing `family_id` in Response

The `family_id` field is null, suggesting the `family_invitations` table either:
- Doesn't have a `family_id` column (wrong schema)
- Has null values (data integrity issue)
- Query isn't selecting it

### 3. Field Name Inconsistency

The backend uses `inviter_username` but the API documentation specifies `invited_by_username`. We need consistency.

**Current naming:**
- `inviter_username` ← returned
- `inviter_user_id` ← missing

**Expected naming (from API docs):**
- `inviter_username` ✅
- `inviter_user_id` ❌ (should be `invited_by` per docs, but let's use `inviter_user_id` for consistency)

---

## Impact on Mobile App

### User Experience Issues

1. **"Unknown Family" Display**
   - Users see "Unknown" instead of family name
   - Cannot identify which family the invitation is from
   - Must blindly accept/decline invitations

2. **Empty "Invited by" Field**
   - Shows "Invited by: " with no name
   - User doesn't know who sent the invitation (though `inviter_username` exists)

3. **Cannot Display Invitee Info** (for sent invitations)
   - When viewing sent invitations, shows "Unknown" for recipient
   - Cannot track who was invited

### Mobile App Workarounds

The app now handles empty/null fields gracefully:

```dart
// Treats both null AND empty string as "Unknown Family"
final familyName = (json['family_name'] == null || json['family_name'].isEmpty) 
    ? 'Unknown Family' 
    : json['family_name'];

// Uses inviter_username if available
final inviterUsername = json['inviter_username'] ?? 'Unknown';
```

But this is a **workaround**, not a solution. The backend must return complete data.

---

## Required Backend Fixes

### Priority 1: Fix `family_name` (CRITICAL)

**SQL Query Update:**
```sql
SELECT 
  fi.invitation_id,
  fi.family_id,
  COALESCE(f.name, 'Unknown Family') as family_name,
  fi.invited_by as inviter_user_id,
  u.username as inviter_username,
  fi.invitee_email,
  fi.invitee_username,
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
ORDER BY fi.created_at DESC
```

### Priority 2: Return `family_id` (HIGH)

Ensure `family_id` is included in the response. This is needed for:
- Linking invitation to family
- Navigation after accepting invitation
- Data consistency

### Priority 3: Return Invitee Information (MEDIUM)

For sent invitations (`GET /family/{familyId}/invitations`), include:
- `invitee_email` (if invitation sent by email)
- `invitee_username` (if invitation sent by username)

### Priority 4: Field Name Consistency (LOW)

Standardize field naming:
- Use `inviter_username` (not `invited_by_username`)
- Use `inviter_user_id` (not `invited_by`)
- Update API documentation to match

---

## Testing Validation

### Before Fix (Current State)

```bash
curl -X GET "https://dev-app-sbd.rohanbatra.in/family/my-invitations" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Result:**
```json
{
  "invitation_id": "inv_4d4bd60648df440c",
  "family_name": "",           ❌ EMPTY
  "family_id": null,            ❌ NULL
  "invited_by": null,           ❌ NULL
  "invitee_email": null,        ❌ NULL
  "invitee_username": null,     ❌ NULL
  "inviter_username": "rohan",  ✅ OK
  ...
}
```

### After Fix (Expected State)

**Result:**
```json
{
  "invitation_id": "inv_4d4bd60648df440c",
  "family_name": "Johnson Family",  ✅ POPULATED
  "family_id": "fam_32978f981bc246e5", ✅ POPULATED
  "inviter_user_id": "68f3c68604839468a2f226f0", ✅ POPULATED
  "inviter_username": "rohan",       ✅ OK
  "invitee_email": "user@example.com", ✅ POPULATED
  "invitee_username": "testuser",    ✅ POPULATED
  ...
}
```

---

## Database Schema Verification Needed

Please verify the `family_invitations` table schema includes:

```sql
CREATE TABLE family_invitations (
  invitation_id VARCHAR PRIMARY KEY,
  family_id VARCHAR NOT NULL,          ← Must be populated
  invited_by VARCHAR NOT NULL,         ← Inviter user_id
  invitee_user_id VARCHAR,
  invitee_email VARCHAR,
  invitee_username VARCHAR,
  relationship_type VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL,
  invitation_token VARCHAR,
  
  FOREIGN KEY (family_id) REFERENCES families(family_id),
  FOREIGN KEY (invited_by) REFERENCES users(user_id)
);
```

If `family_id` column doesn't exist or has NULL values, this is a **schema/data issue** that must be fixed first.

---

## Related Endpoints (Also Need Verification)

### `GET /family/{familyId}/invitations` (Sent Invitations)

Please verify this endpoint also returns complete data:

**Required fields:**
- ✅ `invitation_id`
- ✅ `family_id`
- ✅ `family_name` (from JOIN)
- ✅ `invited_by` / `inviter_user_id`
- ✅ `invited_by_username` / `inviter_username` (from JOIN)
- ⚠️ `invitee_email` (if sent by email)
- ⚠️ `invitee_username` (if sent by username)
- ✅ `relationship_type`
- ✅ `status`
- ✅ `expires_at`
- ✅ `created_at`

---

## Debug Logs from Mobile App

```
I/flutter (15866): [FAMILY_API] ========== GET MY INVITATIONS RESPONSE ==========
I/flutter (15866): [FAMILY_API] Raw response: {items: [{invitation_id: inv_4d4bd60648df440c, ...}]}
I/flutter (15866): [FAMILY_API] Invitations count: 3
I/flutter (15866): [FAMILY_API] First invitation raw data:
I/flutter (15866): {
  invitation_id: inv_4d4bd60648df440c, 
  family_name: ,                           ← EMPTY STRING
  inviter_username: rohan,                 ← OK
  relationship_type: child, 
  status: pending, 
  expires_at: 2025-10-28T15:11:51.812000, 
  created_at: 2025-10-21T15:11:51.812000
}
I/flutter (15866): [FAMILY_API] Fields check:
I/flutter (15866):   - invitation_id: inv_4d4bd60648df440c
I/flutter (15866):   - family_id: null                    ← NULL
I/flutter (15866):   - family_name:                       ← EMPTY
I/flutter (15866):   - invited_by: null                   ← NULL
I/flutter (15866):   - invited_by_username: null          ← NULL
I/flutter (15866):   - invitee_email: null                ← NULL
I/flutter (15866):   - invitee_username: null             ← NULL
I/flutter (15866):   - relationship_type: child
I/flutter (15866):   - status: pending
```

---

## Urgency

**CRITICAL** - Feature is deployed but showing incorrect/incomplete data to users. This impacts:
- User trust (seeing "Unknown" everywhere)
- Feature usability (can't identify invitations)
- Data integrity (missing family_id)

### Estimated Fix Time

- SQL query update: **15 minutes**
- Testing: **15 minutes**
- Deployment: **5 minutes**
- **Total: ~35 minutes**

---

## Contact

**Mobile Team:** GitHub Copilot  
**Backend API:** dev-app-sbd.rohanbatra.in  
**Environment:** Development  
**Date Reported:** October 21, 2025, 8:57 AM

---

**Status:** 🔴 Awaiting Backend Fix
