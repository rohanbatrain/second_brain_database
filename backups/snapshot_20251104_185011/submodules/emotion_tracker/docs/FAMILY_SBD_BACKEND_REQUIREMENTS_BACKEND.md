# Family SBD (Spending / Can Spend) — Backend Requirements

TL;DR
- Frontend reads member permissions from GET /family/{familyId}/members (each member must include `spending_permissions`).
- Admins read a richer SBD account from GET /family/{familyId}/sbd-account (contains `member_permissions` map keyed by user id).
- Admin updates must be implemented at PUT /family/{familyId}/spending-permissions/{targetUserId} and should return a wrapper JSON with `new_permissions` and `transaction_safe`.
- Request/response shapes, validations, auth rules, and audit events are specified below. Use -1 to represent Unlimited for `spending_limit`.

Why this exists
- The frontend (Members tab in `SBDAccountScreen`) calls the family provider to load members and, when present, an SBD account. The UI relies on per-member `spending_permissions` for display and on the PUT wrapper response to update local state without forcing a full refresh.

Goals for backend implementers
- Provide consistent, documented endpoints that:
  - Always return per-member permission info in the members list (so non-admins can see permissions),
  - Return a full `sbd-account` for admin views (including `member_permissions` map), and
  - Provide an update endpoint that returns `new_permissions` and `transaction_safe` so the frontend can update local models.

---

## Auth / Common headers
- All endpoints require `Authorization: Bearer <access_token>`.
- `Content-Type: application/json` expected for POST/PUT.
- Return `401 Unauthorized` for missing/invalid token.

Use UTC ISO 8601 timestamps (e.g. `2025-10-22T12:34:56Z`).

---

## 1) GET /family/{familyId}
Purpose: family metadata and the current user's role within that family.

Response (200):
```
{
  "family_id": "fam_123",
  "name": "Smith Family",
  "is_admin": true,
  "admin_user_ids": ["user_1","user_2"],
  "user_role": "admin"
}
```

Frontend usage: `FamilyApiService.getFamilyDetails()` → `FamilyDetailsNotifier.loadFamilyDetails()`.

---

## 2) GET /family/{familyId}/members
Purpose: list all family members. **This endpoint MUST include per-member permission data** in the returned member object.

Response (200):
```
{
  "members": [
    {
      "user_id": "user_123",
      "username": "jdoe",
      "email": "jdoe@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "role": "member",
      "is_backup_admin": false,
      "joined_at": "2025-10-22T12:34:56Z",
      "spending_permissions": {
        "can_spend": true,
        "spending_limit": 500,   // integer, -1 = Unlimited
        "updated_by": "admin_1",
        "updated_at": "2025-10-22T12:00:00Z"
      }
    }
  ]
}
```

Notes:
- Field names should match the frontend model names or be trivially mappable.
- If your API uses a different top-level array key, the client accepts `members` or `items` (client code already falls back to `items`), but include `spending_permissions` inside each member.

---

## 3) GET /family/{familyId}/sbd-account
Purpose: SBD account details for the family (mainly used by admins). Must include a `member_permissions` map keyed by user id for quick lookup.

Response (200):
```
{
  "account_id": "acct_abc",
  "account_username": "family_rohan_s_family",
  "account_name": "Smith Family SBD",
  "balance": 1200,
  "currency": "SBD",
  "is_frozen": false,
  "freeze_reason": null,
  "member_permissions": {
    "user_123": {
      "can_spend": true,
      "spending_limit": 500,
      "updated_by": "admin_1",
      "updated_at": "2025-10-22T12:00:00Z"
    },
    "user_456": {
      "can_spend": false,
      "spending_limit": 0,
      "updated_by": "admin_1",
      "updated_at": "2025-10-21T09:00:00Z"
    }
  }
}
```

Notes:
- `spending_limit` semantics: integer >= 0; -1 = Unlimited.
- `member_permissions` is optional for non-admin viewers (the frontend wraps the `getSBDAccount` call in try/catch and will continue if it's inaccessible).

---

## 4) PUT /family/{familyId}/spending-permissions/{targetUserId}
Purpose: Admin updates a member's spending permissions.

Auth: Admin-only. Return 403 if the caller is not allowed.

Request body (JSON):
```
{
  "user_id": "user_123",
  "spending_limit": 500,    // integer, -1 = Unlimited
  "can_spend": true
}
```

Response (200) — **wrapper** (frontend expects and uses this):
```
{
  "message": "Updated spending permissions for user_123",
  "family_id": "fam_123",
  "target_user_id": "user_123",
  "new_permissions": {
    "role": "member",
    "can_spend": true,
    "spending_limit": 500,
    "updated_by": "admin_1",
    "updated_at": "2025-10-22T12:10:00Z"
  },
  "updated_by": "admin_1",
  "updated_at": "2025-10-22T12:10:00Z",
  "transaction_safe": true
}
```

Field notes:
- `new_permissions` will be used by the frontend to update local in-memory models (`FamilyMember.spendingPermissions` and `SBDAccount.memberPermissions`).
- `transaction_safe` indicates whether the change is safe to apply without extra coordination (frontend may surface a warning if `false`).

Error responses:
- 400 Bad Request — invalid input (e.g., `spending_limit` < -1)
- 401 Unauthorized — token missing/invalid
- 403 Forbidden — not an admin
- 404 Not Found — family or user not found
- 422 Unprocessable Entity — validation failure; prefer a JSON body describing field errors
- 429 Too Many Requests — rate limit

---

## 5) (Optional) GET /family/{familyId}/limits
Purpose: expose system-wide or family-level policies (max permitted limits, allow unlimited flag, defaults).

Response example:
```
{
  "max_spending_limit": 100000,
  "default_spending_limit": 0,
  "allow_unlimited": true
}
```

---

## Validation rules (server-side)
- `spending_limit` must be integer and either -1 (Unlimited) or >= 0.
- `can_spend` must be boolean.
- Admin-only guard for PUT endpoint; return 403 for others.

---

## Audit & notifications
- Record an audit entry for each permission change with: family_id, target_user_id, previous_permissions, new_permissions, changed_by, ip_address (if available), timestamp.
- Optionally emit a notification to the family or the target user describing the change.

---

## Tests to provide
- Unit tests: validate PUT input validation, admin auth guard, correct `new_permissions` in response.
- Integration tests: admin happy path, non-admin 403, invalid body 400/422, concurrent updates.
- End-to-end: frontend integration that toggles a permission and verifies the UI updates using the wrapper `new_permissions`.

---

## Example curl (update permissions)
```
curl -X PUT "https://api.example.com/family/fam_123/spending-permissions/user_123" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"user_123",
    "spending_limit":500,
    "can_spend":true
  }'

# Expect HTTP 200 with wrapper JSON (see above)
```

---

## Quick implement checklist for backend team
- [ ] GET `/family/{familyId}/members` returns `spending_permissions` in each member.
- [ ] GET `/family/{familyId}/sbd-account` returns `member_permissions` map for admins.
- [ ] PUT `/family/{familyId}/spending-permissions/{targetUserId}` implemented and returns wrapper with `new_permissions` and `transaction_safe`.
- [ ] Input validation, auth checks, audit logs and notification events implemented.
- [ ] Tests added and sample responses documented in API docs (OpenAPI/Swagger).

---
