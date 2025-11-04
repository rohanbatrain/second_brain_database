# Backend Required Fixes - Family Invitations

**Date:** October 21, 2025  
**Priority:** 🔴 HIGH  
**Status:** Mobile Complete ✅ | Backend Incomplete ❌

---

## Executive Summary

The mobile app's family invitations feature is **fully implemented** but is showing "Unknown Family" and missing data because the backend API endpoints are not returning complete data. The backend needs to add **JOIN queries** to populate missing fields.

---

## 🔴 Critical Fixes Required

### Fix #1: GET /family/{familyId}/invitations - Add JOINs

**Current Issue:**
- Returns empty `family_name` ("")
- Returns null `invitee_username`
- Returns null `invited_by_username`
- Returns null `family_id`

**Required SQL Query:**
```sql
SELECT 
  fi.invitation_id,
  fi.family_id,
  COALESCE(f.name, 'Unknown Family') as family_name,
  fi.invited_by,
  COALESCE(u_inviter.username, 'Unknown') as invited_by_username,
  fi.invitee_user_id,
  fi.invitee_email,
  COALESCE(u_invitee.username, '') as invitee_username,
  fi.relationship_type,
  fi.status,
  fi.expires_at,
  fi.created_at,
  fi.invitation_token
FROM family_invitations fi
LEFT JOIN families f ON fi.family_id = f.family_id
LEFT JOIN users u_inviter ON fi.invited_by = u_inviter.user_id
LEFT JOIN users u_invitee ON fi.invitee_user_id = u_invitee.user_id
WHERE fi.family_id = $1
ORDER BY fi.created_at DESC
```

**Expected Response:**
```json
{
  "invitations": [
    {
      "invitation_id": "inv_abc123",
      "family_id": "fam_32978f981bc246e5",
      "family_name": "Smith Family",
      "invited_by": "68f3c68604839468a2f226f0",
      "invited_by_username": "rohan",
      "invitee_email": "john@example.com",
      "invitee_username": "john",
      "relationship_type": "child",
      "status": "pending",
      "expires_at": "2025-10-28T15:00:36Z",
      "created_at": "2025-10-21T15:00:36Z",
      "invitation_token": "VizHqsaUUx..."
    }
  ]
}
```

---

### Fix #2: GET /family/my-invitations - Add JOINs

**Current Issue:**
- Returns empty `family_name` ("")
- Returns null `family_id`
- ✅ `inviter_username` is working correctly!

**Required SQL Query:**
```sql
SELECT 
  fi.invitation_id,
  fi.family_id,
  COALESCE(f.name, 'Unknown Family') as family_name,
  fi.invited_by as inviter_user_id,
  COALESCE(u.username, 'Unknown') as inviter_username,
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
AND ($4 IS NULL OR fi.status = $4)
ORDER BY fi.created_at DESC
```

**Expected Response:**
```json
{
  "items": [
    {
      "invitation_id": "inv_4d4bd60648df440c",
      "family_id": "fam_32978f981bc246e5",
      "family_name": "Johnson Family",
      "inviter_user_id": "68f3c68604839468a2f226f0",
      "inviter_username": "rohan",
      "relationship_type": "child",
      "status": "pending",
      "expires_at": "2025-10-28T15:11:51Z",
      "created_at": "2025-10-21T15:11:51Z",
      "invitation_token": "VizHqsaUUx..."
    }
  ]
}
```

---

## 🟡 Medium Priority Enhancements

### Enhancement #1: Implement Edge Case Validations

**Add to POST /family/{familyId}/invite:**

1. **Prevent Duplicate Invitations**
```sql
-- Check if user already has pending invitation
SELECT COUNT(*) 
FROM family_invitations 
WHERE family_id = $1 
  AND (invitee_user_id = $2 OR invitee_email = $3 OR invitee_username = $4)
  AND status = 'pending'
  AND expires_at > NOW()
```
**Error Response:** 
```json
{
  "error": "DUPLICATE_INVITATION",
  "message": "User already has a pending invitation to this family"
}
```

2. **Prevent Self-Invite**
```python
if invitee_user_id == current_user.user_id:
    raise HTTPException(400, {
        "error": "SELF_INVITE_NOT_ALLOWED",
        "message": "You cannot invite yourself to the family"
    })
```

3. **Prevent Inviting Existing Members**
```sql
SELECT COUNT(*) 
FROM family_members 
WHERE family_id = $1 AND user_id = $2
```
**Error Response:**
```json
{
  "error": "ALREADY_MEMBER",
  "message": "User is already a member of this family"
}
```

4. **Enforce 24-Hour Cooldown After Decline**
```sql
SELECT declined_at 
FROM family_invitations 
WHERE family_id = $1 
  AND (invitee_user_id = $2 OR invitee_email = $3)
  AND status = 'declined'
ORDER BY declined_at DESC
LIMIT 1
```
```python
if declined_at and (now - declined_at) < timedelta(hours=24):
    hours_remaining = 24 - (now - declined_at).total_seconds() / 3600
    raise HTTPException(429, {
        "error": "RECENTLY_DECLINED",
        "message": f"This user recently declined an invitation. You can send another invitation in {hours_remaining:.0f} hours.",
        "retry_after_hours": hours_remaining
    })
```

5. **Enforce Family Member Limit**
```sql
SELECT COUNT(*) FROM family_members WHERE family_id = $1
```
```python
if member_count >= 10:  # or your configured limit
    raise HTTPException(400, {
        "error": "FAMILY_FULL",
        "message": "Maximum family members limit (10) reached"
    })
```

6. **User Not Found Validation**
```sql
SELECT user_id FROM users 
WHERE email = $1 OR username = $2
```
**Error Response:**
```json
{
  "error": "USER_NOT_FOUND",
  "message": "No user found with that email or username"
}
```

7. **Rate Limiting**
```python
# Track invitations sent per user per hour
if invitation_count_last_hour >= 20:
    raise HTTPException(429, {
        "error": "RATE_LIMIT_EXCEEDED",
        "message": "You've sent too many invitations. Please wait an hour.",
        "retry_after_seconds": 3600
    })
```

---

### Enhancement #2: Add Notification System

**When invitation is sent:**
```python
# Send email notification
send_email(
    to=invitee_email,
    subject=f"You've been invited to join {family_name}",
    template="family_invitation",
    data={
        "family_name": family_name,
        "inviter_name": inviter_username,
        "relationship_type": relationship_type,
        "accept_url": f"https://app.example.com/family/invitation/{token}/accept"
    }
)

# Send push notification (if app installed)
send_push_notification(
    user_id=invitee_user_id,
    title=f"Family Invitation from {inviter_username}",
    body=f"You've been invited to join {family_name} as {relationship_type}",
    data={"invitation_token": token}
)
```

---

### Enhancement #3: Auto-Expire Invitations

**Add cron job or check on query:**

```python
# Cron job (runs every hour)
def expire_old_invitations():
    db.execute("""
        UPDATE family_invitations 
        SET status = 'expired'
        WHERE status = 'pending' 
          AND expires_at < NOW()
    """)

# OR check on each query
SELECT 
  *,
  CASE 
    WHEN expires_at < NOW() AND status = 'pending' THEN 'expired'
    ELSE status
  END as status
FROM family_invitations
```

---

## 🟢 Low Priority (Nice to Have)

### Optional #1: Add Invitation Analytics

Track:
- Total invitations sent per family
- Acceptance rate
- Average response time
- Most common decline reasons

### Optional #2: Add Invitation History

Keep audit trail:
- Who sent invitation
- When it was sent
- When it was responded to
- IP address of responder

---

## Database Schema Verification

**Please verify your `family_invitations` table has these columns:**

```sql
CREATE TABLE family_invitations (
  invitation_id VARCHAR PRIMARY KEY,
  family_id VARCHAR NOT NULL,              ← Must not be NULL
  invited_by VARCHAR NOT NULL,             ← Inviter's user_id
  invitee_user_id VARCHAR,
  invitee_email VARCHAR,
  invitee_username VARCHAR,
  relationship_type VARCHAR NOT NULL,
  status VARCHAR NOT NULL DEFAULT 'pending',
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  declined_at TIMESTAMP,                   ← For 24h cooldown
  invitation_token VARCHAR UNIQUE NOT NULL,
  
  FOREIGN KEY (family_id) REFERENCES families(family_id) ON DELETE CASCADE,
  FOREIGN KEY (invited_by) REFERENCES users(user_id) ON DELETE SET NULL,
  FOREIGN KEY (invitee_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  
  INDEX idx_family_invitations_family (family_id),
  INDEX idx_family_invitations_invitee (invitee_user_id, invitee_email, invitee_username),
  INDEX idx_family_invitations_status (status),
  INDEX idx_family_invitations_token (invitation_token)
);
```

**Check for NULL values:**
```sql
-- This should return 0 rows
SELECT * FROM family_invitations WHERE family_id IS NULL;
SELECT * FROM family_invitations WHERE invited_by IS NULL;
```

---

## Testing Checklist

### After implementing fixes, test:

**Fix #1 (Sent Invitations):**
- [ ] `family_name` is populated from families table
- [ ] `invited_by_username` is populated from users table
- [ ] `invitee_username` is populated when user exists
- [ ] `family_id` is never null
- [ ] COALESCE returns "Unknown Family" when family deleted
- [ ] COALESCE returns "Unknown" when inviter deleted

**Fix #2 (Received Invitations):**
- [ ] `family_name` is populated from families table
- [ ] `inviter_username` continues to work correctly
- [ ] `family_id` is never null
- [ ] Status filter works (?status=pending)
- [ ] Multiple invitations from different families display correctly

**Edge Cases:**
- [ ] Duplicate invitation returns proper error
- [ ] Self-invite returns proper error
- [ ] Inviting existing member returns proper error
- [ ] 24-hour cooldown after decline is enforced
- [ ] Family member limit (10) is enforced
- [ ] Invalid email/username returns proper error
- [ ] Rate limit (20/hour) is enforced

---

## Quick Reference Commands

**Test sent invitations endpoint:**
```bash
curl -X GET "https://dev-app-sbd.rohanbatra.in/family/fam_YOUR_FAMILY_ID/invitations" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  | jq
```

**Test received invitations endpoint:**
```bash
curl -X GET "https://dev-app-sbd.rohanbatra.in/family/my-invitations" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  | jq
```

**Test with status filter:**
```bash
curl -X GET "https://dev-app-sbd.rohanbatra.in/family/my-invitations?status=pending" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  | jq
```

---

## Expected Timeline

| Task | Estimated Time |
|------|----------------|
| Fix #1: Add JOINs to sent invitations | 20 minutes |
| Fix #2: Add JOINs to received invitations | 15 minutes |
| Add edge case validations | 1-2 hours |
| Add notification system | 2-3 hours |
| Add auto-expire cron job | 30 minutes |
| Testing | 1 hour |
| **Total Critical Fixes** | **35 minutes** |
| **Total with Enhancements** | **4-7 hours** |

---

## Contact

**Mobile Team:** GitHub Copilot  
**Backend API:** dev-app-sbd.rohanbatra.in  
**Environment:** Development  

---

## Mobile App Status

✅ **Frontend is 100% Complete:**
- Models handle null/empty values gracefully
- UI shows "Unknown Family" with warning when data missing
- UI shows "Unknown Recipient" when invitee data missing
- All edge cases handled with user-friendly error messages
- Comprehensive exception handling
- Debug logging for troubleshooting
- Pull-to-refresh functionality
- Empty states
- Loading states
- Error states with retry
- 24-hour cooldown warnings
- Expiry warnings

**Mobile app is production-ready pending backend fixes!**
