# Family Invitations: Complete Flow & Backend Requirements

**Date:** October 21, 2025  
**Version:** 1.0  
**Status:** ✅ Mobile Complete | 🔴 Backend Incomplete

---

## Table of Contents

1. [Overview](#overview)
2. [Two Separate Features](#two-separate-features)
3. [Flow 1: Sending Invitations](#flow-1-sending-invitations-you-invite-others)
4. [Flow 2: Receiving Invitations](#flow-2-receiving-invitations-others-invite-you)
5. [All Backend Endpoints Required](#all-backend-endpoints-required)
6. [Data Models](#data-models)
7. [Mobile App Screens](#mobile-app-screens)
8. [Current Issues](#current-issues)

---

## Overview

There are **TWO COMPLETELY SEPARATE** invitation features:

1. **Sending Invitations** - You invite others to join YOUR family
2. **Receiving Invitations** - Others invite you to join THEIR family

Each has its own:
- Backend endpoints
- Data models
- UI screens
- User flows

---

## Two Separate Features

### Feature 1: Sending Invitations (You Invite Others)

**Use Case:** You are a family administrator and want to invite someone to join your family.

**User Journey:**
1. You navigate to **Family Details Screen**
2. Click "View Invitations" button
3. See **Invitations Screen** (shows invitations YOU sent)
4. Click "Invite Member" button
5. Enter email/username, select relationship type
6. Backend creates invitation and sends notification
7. Invited person receives the invitation

**Backend Endpoints Involved:**
- `POST /family/{familyId}/invite` - Send invitation
- `GET /family/{familyId}/invitations` - View invitations YOU sent
- `DELETE /family/{familyId}/invitations/{invitationId}` - Cancel invitation

### Feature 2: Receiving Invitations (Others Invite You)

**Use Case:** Someone invited you to join their family, and you need to accept or decline.

**User Journey:**
1. You navigate to **Received Invitations Screen** (from Family Management)
2. See list of invitations sent TO you
3. Review invitation details (family name, who invited you, relationship)
4. Accept or decline the invitation
5. If accepted, you join that family
6. If declined, there's a 24-hour cooldown

**Backend Endpoints Involved:**
- `GET /family/my-invitations` - View invitations sent TO you
- `POST /family/invitation/{invitationToken}/respond` - Accept/decline invitation

---

## Flow 1: Sending Invitations (You Invite Others)

### Step 1: Admin Invites a Member

**Endpoint:** `POST /family/{familyId}/invite`

**Mobile Code:** `lib/providers/family/family_api_service.dart` line 255-323

**Request:**
```json
POST /family/fam_32978f981bc246e5/invite
Authorization: Bearer YOUR_TOKEN

{
  "identifier": "john@example.com",
  "identifier_type": "email",
  "relationship_type": "child"
}
```

**Backend Actions:**
1. Validate user is family admin
2. Check if identifier exists (user lookup)
3. Create invitation record in `family_invitations` table
4. Generate `invitation_token`
5. Set `expires_at` (7 days from now)
6. Send notification to invitee (email/push)
7. Return invitation details

**Expected Response:**
```json
{
  "invitation_id": "inv_584fd025c907445d",
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
  "invitation_token": "VizHqsaUUx8uvpz2q5YRzi6r2yNK-7U8G_ApNa3jr6U"
}
```

**Mobile UI:** `lib/screens/settings/account/family/invitations_screen.dart`

### Step 2: Admin Views Sent Invitations

**Endpoint:** `GET /family/{familyId}/invitations`

**Mobile Code:** `lib/providers/family/family_api_service.dart` line 332-361

**Request:**
```json
GET /family/fam_32978f981bc246e5/invitations
Authorization: Bearer YOUR_TOKEN
```

**Backend Actions:**
1. Validate user has access to family
2. Query `family_invitations` where `family_id = fam_32978f981bc246e5`
3. JOIN with `families` table to get `family_name`
4. JOIN with `users` table (inviter) to get `invited_by_username`
5. Optionally JOIN with `users` table (invitee) to get `invitee_username`
6. Return all invitations (pending, accepted, declined, expired)

**Required SQL:**
```sql
SELECT 
  fi.invitation_id,
  fi.family_id,
  f.name as family_name,
  fi.invited_by,
  u_inviter.username as invited_by_username,
  fi.invitee_user_id,
  fi.invitee_email,
  u_invitee.username as invitee_username,
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
      "invitation_id": "inv_584fd025c907445d",
      "family_id": "fam_32978f981bc246e5",
      "family_name": "Smith Family",
      "invited_by": "68f3c68604839468a2f226f0",
      "invited_by_username": "rohan",
      "invitee_email": "john@example.com",
      "invitee_username": "john",
      "relationship_type": "child",
      "status": "pending",
      "expires_at": "2025-10-28T15:00:36Z",
      "created_at": "2025-10-21T15:00:36Z"
    }
  ]
}
```

**Current Issue:** ❌ Backend returning empty `family_name`, missing `invitee_username`, missing `invited_by_username`

### Step 3: Admin Cancels Invitation

**Endpoint:** `DELETE /family/{familyId}/invitations/{invitationId}`

**Mobile Code:** `lib/providers/family/family_api_service.dart` line 374

**Request:**
```json
DELETE /family/fam_32978f981bc246e5/invitations/inv_584fd025c907445d
Authorization: Bearer YOUR_TOKEN
```

**Backend Actions:**
1. Validate user is family admin
2. Update invitation status to 'cancelled'
3. Send notification to invitee (invitation cancelled)

---

## Flow 2: Receiving Invitations (Others Invite You)

### Step 1: View Invitations Received

**Endpoint:** `GET /family/my-invitations`

**Mobile Code:** `lib/providers/family/family_api_service.dart` line 378-407

**Request:**
```json
GET /family/my-invitations
Authorization: Bearer YOUR_TOKEN

Optional query params:
  ?status=pending
  ?status=accepted
  ?status=declined
  ?status=expired
```

**Backend Actions:**
1. Extract `user_id`, `email`, `username` from Bearer token
2. Query `family_invitations` where:
   - `invitee_user_id = current_user.user_id` OR
   - `invitee_email = current_user.email` OR
   - `invitee_username = current_user.username`
3. JOIN with `families` table to get `family_name`
4. JOIN with `users` table (inviter) to get `inviter_username`
5. Apply optional status filter
6. Return invitations

**Required SQL:**
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
      "invitation_token": "VizHqsaUUx8uvpz2q5YRzi6r2yNK-7U8G_ApNa3jr6U"
    }
  ]
}
```

**Current Issue:** 
- ✅ Endpoint responding (no longer 404)
- ❌ `family_name` is empty string `""`
- ❌ `family_id` is null
- ✅ `inviter_username` is "rohan" (correct!)

**Mobile UI:** `lib/screens/settings/account/family/received_invitations_screen.dart`

### Step 2: Accept or Decline Invitation

**Endpoint:** `POST /family/invitation/{invitationToken}/respond`

**Mobile Code:** `lib/providers/family/family_api_service.dart` line 325-330

**Request (Accept):**
```json
POST /family/invitation/VizHqsaUUx8uvpz2q5YRzi6r2yNK-7U8G_ApNa3jr6U/respond
Authorization: Bearer YOUR_TOKEN

{
  "action": "accept"
}
```

**Request (Decline):**
```json
POST /family/invitation/VizHqsaUUx8uvpz2q5YRzi6r2yNK-7U8G_ApNa3jr6U/respond
Authorization: Bearer YOUR_TOKEN

{
  "action": "decline"
}
```

**Backend Actions (Accept):**
1. Validate invitation exists and is pending
2. Check invitation not expired
3. Add user to family members table
4. Update invitation status to 'accepted'
5. Send notification to family admin
6. Return success

**Backend Actions (Decline):**
1. Validate invitation exists and is pending
2. Update invitation status to 'declined'
3. Record `declined_at` timestamp (for 24h cooldown)
4. Send notification to family admin
5. Return success

**24-Hour Cooldown Rule:**
- If user declines, admin cannot send another invitation for 24 hours
- Backend should enforce: Check `declined_at` timestamp when creating new invitation
- Mobile shows warning before declining

---

## All Backend Endpoints Required

### Invitation Management

| Method | Endpoint | Purpose | Mobile Location | Status |
|--------|----------|---------|----------------|--------|
| `POST` | `/family/{familyId}/invite` | Send invitation | `family_api_service.dart:255` | ✅ Working |
| `GET` | `/family/{familyId}/invitations` | View sent invitations | `family_api_service.dart:332` | ⚠️ Missing fields |
| `DELETE` | `/family/{familyId}/invitations/{invitationId}` | Cancel invitation | `family_api_service.dart:374` | ✅ Working |
| `GET` | `/family/my-invitations` | View received invitations | `family_api_service.dart:378` | ⚠️ Missing fields |
| `POST` | `/family/invitation/{token}/respond` | Accept/decline | `family_api_service.dart:325-330` | ✅ Working |

### Supporting Endpoints

| Method | Endpoint | Purpose | Mobile Location | Status |
|--------|----------|---------|----------------|--------|
| `GET` | `/family/my-families` | List user's families | `family_api_service.dart:66` | ✅ Working |
| `GET` | `/family/{familyId}` | Get family details | `family_api_service.dart:87` | ✅ Working |
| `GET` | `/family/{familyId}/members` | List family members | `family_api_service.dart:109` | ✅ Working |

---

## Data Models

### 1. FamilyInvitation (Sent Invitations)

**Mobile:** `lib/providers/family/family_models.dart` line 235-304

**Fields:**
```dart
class FamilyInvitation {
  final String invitationId;
  final String familyId;
  final String familyName;           // From JOIN with families table
  final String invitedBy;            // Inviter user_id
  final String invitedByUsername;    // From JOIN with users table
  final String? inviteeEmail;        // Email of person invited
  final String? inviteeUsername;     // Username of person invited
  final String relationshipType;
  final String status;
  final DateTime createdAt;
  final DateTime expiresAt;
  final String? invitationToken;
}
```

**Backend Schema:**
```sql
CREATE TABLE family_invitations (
  invitation_id VARCHAR PRIMARY KEY,
  family_id VARCHAR NOT NULL,
  invited_by VARCHAR NOT NULL,         -- user_id of inviter
  invitee_user_id VARCHAR,
  invitee_email VARCHAR,
  invitee_username VARCHAR,
  relationship_type VARCHAR NOT NULL,
  status VARCHAR NOT NULL,             -- pending, accepted, declined, expired, cancelled
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL,
  declined_at TIMESTAMP,               -- For 24h cooldown
  invitation_token VARCHAR UNIQUE,
  
  FOREIGN KEY (family_id) REFERENCES families(family_id),
  FOREIGN KEY (invited_by) REFERENCES users(user_id)
);
```

### 2. ReceivedInvitation (Invitations You Received)

**Mobile:** `lib/providers/family/family_models.dart` line 309-383

**Fields:**
```dart
class ReceivedInvitation {
  final String invitationId;
  final String familyId;
  final String familyName;           // From JOIN with families table
  final String inviterUserId;
  final String inviterUsername;      // From JOIN with users table
  final String relationshipType;
  final String status;
  final DateTime expiresAt;
  final DateTime createdAt;
  final String? invitationToken;
}
```

**Same backend table, different query perspective!**

---

## Mobile App Screens

### 1. Invitations Screen (Sent Invitations)

**File:** `lib/screens/settings/account/family/invitations_screen.dart`

**Purpose:** View and manage invitations YOU sent to others

**Features:**
- List of invitations sent (pending, accepted, declined, expired)
- "Invite Member" button to send new invitation
- Cancel pending invitations
- Shows invitee email/username
- Shows family name
- Shows who sent the invitation (you)

**Navigation:**
```
Family Details Screen 
  → "View Invitations" button 
    → Invitations Screen
```

### 2. Received Invitations Screen

**File:** `lib/screens/settings/account/family/received_invitations_screen.dart`

**Purpose:** View and respond to invitations sent TO you

**Features:**
- Tabbed interface (Pending / Accepted / Declined / Expired)
- Shows family name of inviter
- Shows who invited you
- Accept/Decline buttons
- 24-hour cooldown warning before declining
- Expiry warnings for invitations expiring soon
- Pull-to-refresh

**Navigation:**
```
Family Management Screen 
  → "Received Invitations" button 
    → Received Invitations Screen
```

---

## Current Issues

### Issue 1: GET /family/{familyId}/invitations Missing Fields

**Endpoint:** `GET /family/{familyId}/invitations`

**What's Wrong:**
- `family_name` is empty string `""`
- `invitee_username` is missing
- `invited_by_username` is missing

**Current Backend Response:**
```json
{
  "invitations": [{
    "invitation_id": "inv_...",
    "family_id": null,
    "family_name": "",              ❌
    "invited_by": null,
    "invited_by_username": null,    ❌
    "invitee_email": null,
    "invitee_username": null,       ❌
    "relationship_type": "child",
    "status": "pending"
  }]
}
```

**Fix Required:**
- Add LEFT JOIN with `families` table
- Add LEFT JOIN with `users` table for inviter
- Add LEFT JOIN with `users` table for invitee
- Return `family_id` from database

### Issue 2: GET /family/my-invitations Missing Fields

**Endpoint:** `GET /family/my-invitations`

**What's Wrong:**
- `family_name` is empty string `""`
- `family_id` is null

**Current Backend Response:**
```json
{
  "items": [{
    "invitation_id": "inv_4d4bd60648df440c",
    "family_id": null,              ❌
    "family_name": "",              ❌
    "inviter_username": "rohan",    ✅
    "relationship_type": "child",
    "status": "pending"
  }]
}
```

**Fix Required:**
- Add LEFT JOIN with `families` table to populate `family_name`
- Return `family_id` from `family_invitations` table

---

## Edge Cases to Handle

### Backend Must Handle:

1. **Duplicate Invitations**
   - Don't allow sending invitation if one already pending
   - Error: `"User already has a pending invitation to this family"`

2. **Self-Invite**
   - Don't allow inviting yourself
   - Error: `"You cannot invite yourself to the family"`

3. **Already a Member**
   - Don't allow inviting existing members
   - Error: `"User is already a member of this family"`

4. **24-Hour Cooldown After Decline**
   - Check `declined_at` timestamp
   - Error: `"This user recently declined an invitation. You can send another invitation in X hours."`

5. **Rate Limiting**
   - Limit invitation sends (20/hour)
   - Error: `"You've sent too many invitations. Please wait an hour."`

6. **User Not Found**
   - Validate identifier exists
   - Error: `"No user found with that email/username"`

7. **Family Member Limit**
   - Check max members (e.g., 10)
   - Error: `"Maximum family members limit (10) reached"`

8. **Expired Invitations**
   - Auto-expire after 7 days
   - Cron job or check on query

9. **Deleted Family**
   - Handle family deletion gracefully
   - Return `"Unknown Family"` in JOIN

10. **Deleted Inviter**
    - Handle user deletion
    - Return `"Unknown"` in JOIN

---

## Summary

### What Mobile Has Implemented ✅

1. ✅ Complete UI for both features
2. ✅ Data models with helper properties
3. ✅ Exception handling for all edge cases
4. ✅ User-friendly error messages
5. ✅ 24-hour cooldown warnings
6. ✅ Expiry warnings
7. ✅ Pull-to-refresh
8. ✅ Empty state handling
9. ✅ Loading states
10. ✅ Comprehensive error states

### What Backend Needs to Fix 🔴

1. ❌ Add JOIN queries to populate `family_name`
2. ❌ Add JOIN queries to populate `inviter_username` / `invited_by_username`
3. ❌ Add JOIN queries to populate `invitee_username`
4. ❌ Return `family_id` in responses
5. ❌ Implement all edge case checks (duplicates, self-invite, cooldown, etc.)
6. ❌ Add rate limiting (20 invites/hour)
7. ❌ Add notification system (email/push when invited)
8. ❌ Add cron job for auto-expiring invitations

---

## Quick Reference

**Sending Invitations (Admin View):**
```
POST /family/{familyId}/invite        → Send invitation
GET  /family/{familyId}/invitations   → View sent invitations
DELETE /family/{familyId}/invitations/{id} → Cancel invitation
```

**Receiving Invitations (Invitee View):**
```
GET  /family/my-invitations           → View received invitations
POST /family/invitation/{token}/respond → Accept/decline
```

---

**Last Updated:** October 21, 2025  
**Mobile App Version:** Complete  
**Backend API Version:** Incomplete (missing fields, missing JOINs)
