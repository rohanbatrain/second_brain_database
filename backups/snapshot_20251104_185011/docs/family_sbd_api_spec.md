Family SBD Backend API Spec (frontend copy-paste)

Purpose
- Concise spec for frontend team to integrate "Can Spend" toggle and "Spending Limit" UI.

Summary
- Endpoints:
  1) GET /family/{familyId}/sbd-account
  2) PUT /family/{familyId}/sbd-account/permissions
  3) GET /family/limits

Authentication
- All endpoints require Bearer token in Authorization header. Use existing auth middleware.

1) GET /family/{familyId}/sbd-account
- Auth: Bearer
- Returns: full SBD account JSON mapping to frontend SBDAccount model
- Important fields:
  - account_id: string | nullable
  - account_username: string
  - account_name: string | nullable
  - balance: int (integer smallest-unit SBD)
  - currency: string (e.g., "SBD")
  - is_frozen: bool
  - freeze_reason: string | nullable
  - frozen_at: ISO datetime | nullable
  - member_permissions: object keyed by user_id -> { can_spend: bool, spending_limit: int }
  - spending_permissions: original richer map retained (may include updated_by/updated_at/role)
  - notification_settings: object
  - recent_transactions: array

- Errors: 401, 403 (not family member), 404

Example response (200):
{
  "account_id": "va_abcd1234",
  "account_username": "family_smith",
  "account_name": "Smith Family SBD",
  "balance": 5000,
  "currency": "SBD",
  "is_frozen": false,
  "freeze_reason": null,
  "frozen_at": null,
  "member_permissions": {
    "user_abc": { "can_spend": true, "spending_limit": 200 },
    "user_def": { "can_spend": false, "spending_limit": 0 }
  },
  "spending_permissions": {
    "user_abc": {"role": "member", "spending_limit": 200, "can_spend": true, "updated_by": "admin_1", "updated_at": "2025-10-22T12:00:00Z"}
  },
  "notification_settings": { ... },
  "recent_transactions": [ ... ]
}

Notes:
- Frontend expects `spending_limit` to use -1 for Unlimited.
- `member_permissions` is the simple map keyed by user_id used for UI rendering. `spending_permissions` is richer and kept for audit.

2) PUT /family/{familyId}/sbd-account/permissions
- Auth: Bearer
- Purpose: Update a single member's spending permissions (admin only)
- Request body JSON (matches frontend UpdateSpendingPermissionsRequest):
{
  "user_id": "user_abc",
  "spending_limit": 100,
  "can_spend": true
}
- Validation:
  - spending_limit must be integer >= -1 (where -1 = unlimited)
  - user_id must belong to family
  - caller must be family admin

- Response: 200 with full updated SBDAccount JSON (same shape as GET /sbd-account). Frontend expects this to refresh UI immediately.
- Errors: 400 validation, 401, 403 (caller not admin), 404

Example request:
{
  "user_id": "user_abc",
  "spending_limit": 200,
  "can_spend": true
}

Example response (200): same as GET /family/{familyId}/sbd-account (updated values present)

3) GET /family/limits
- Auth: Bearer
- Purpose: return family/global limits and flags used by UI
- Example response:
{
  "default_spending_limit": 100,
  "maximum_spending_limit": 100000,
  "require_admin_approval_for_spending": true
}

Notes for backend implementers
- Only admins may call PUT to update other users' permissions. Enforce server-side.
- GET /sbd-account allowed for family members. It returns `member_permissions` map for frontend usage.
- Use -1 as the canonical unlimited sentinel for `spending_limit`.
- `balance` and amounts are integers (smallest unit). Document precision if changed.
- When permissions change, insert an audit row and emit a `family_permission_change` notification with metadata { changed_by, target_user_id }.
- Enforce spending rules in transfer flows:
  - if can_spend == false -> reject transfer (403 with clear message)
  - if spending_limit != -1 and amount > spending_limit -> reject (400/403)
  - if no member_permissions row exists, fallback to family default or deny

Suggested DB (Postgres-like) tables: sbd_accounts, sbd_member_permissions, sbd_permission_audit

Errors & messages (recommended):
- 400 { "detail": "spending_limit must be >= -1" }
- 403 { "detail": "Only family administrators can update spending permissions" }
- 403 { "detail": "User is not permitted to spend from family account" }

Testing expectations
- Unit tests for GET/PUT endpoints (happy path + validation + auth)
- Integration tests that enforce transfer rules

Contact
- Frontend expects API shapes in `lib/providers/family/family_models.dart` and calls in `lib/providers/family/family_api_service.dart`.


