# Family SBD Backend Requirements

Purpose
- Provide the backend team a concise, copyable specification the frontend expects so the "Can Spend" toggle and "Spending Limit" UI work correctly.
- Matches shapes used by the Flutter frontend in `lib/providers/family/family_models.dart` and API calls in `lib/providers/family/family_api_service.dart`.

## Summary
The frontend requires endpoints that return the family SBD account (including a per-member `member_permissions` map) and an endpoint to update a member's spending permissions. The frontend expects JSON shapes that map to `SBDAccount` and `UpdateSpendingPermissionsRequest` in `family_models.dart`.

## Required endpoints (minimal)
1) GET /family/{familyId}/sbd-account
- Auth: Bearer token
- Returns: full SBDAccount JSON
- Important fields frontend uses:
  - `account_id` (string)
  - `account_username` (optional)
  - `account_name` (optional)
  - `balance` (int)
  - `currency` (string, e.g. "SBD")
  - `is_frozen` (bool)
  - `freeze_reason`, `frozen_at` (optional)
  - `member_permissions`: object keyed by `user_id` where value = `{ "can_spend": bool, "spending_limit": int }`
- Errors: 401, 403 (not family member), 404

2) PUT /family/{familyId}/sbd-account/permissions
- Auth: Bearer token
- Purpose: update a single member's spending permissions
- Request body (JSON) — matches `UpdateSpendingPermissionsRequest`:
```
{
  "user_id": "user_abc",
  "spending_limit": 100,
  "can_spend": true
}
```
- Response: 200 with updated SBDAccount JSON (same shape as GET)
- Errors: 400 validation, 401, 403 (caller not admin), 404

3) GET /family/limits
- Auth: Bearer token
- Purpose: return family/global limits and flags used by UI
- Example response:
```
{
  "default_spending_limit": 100,
  "maximum_spending_limit": 100000,
  "require_admin_approval_for_spending": true
}
```

> Note: `GET /family/{id}` may already include `settings` (see `FamilySettings`). If so, returning limits in that payload is acceptable.

## Data model notes (frontend expectations)
- `member_permissions` must be a map keyed by `user_id`:
```
"member_permissions": {
  "user_abc": { "can_spend": true, "spending_limit": 200 },
  "user_def": { "can_spend": false, "spending_limit": 0 }
}
```
- `spending_limit` uses `-1` to represent "Unlimited" (frontend's `SpendingPermissions.limitText` treats `-1` as Unlimited).
- `balance` and `amount` are integers in the frontend; keep integer smallest-unit representation or document precision.

## Authorization & business rules (server-side)
- Only family admins should be allowed to update other members' permissions via PUT. Enforce server-side.
- GET `/sbd-account` should be allowed for family members. Decide whether to return full `member_permissions` only for admins or include the map for all members — frontend can handle nulls but expects the map for admin views.
- Permission enforcement on transfer flows:
  - If `can_spend == false`: reject transfer with 403 and a clear message.
  - If `spending_limit != -1` and `amount > spending_limit`: reject with 400/403 (or surface as a token-request flow if you require approval).
  - If no `member_permissions` row exists for a user, fallback to family default (if configured) or deny by default.
- Use `-1` as the canonical unlimited sentinel. Document in API docs.

## DB suggestions (high level)
- `sbd_accounts` table: account metadata, balance, is_frozen, etc.
- `sbd_member_permissions` table: family_id, user_id, can_spend (bool), spending_limit (bigint), timestamps; unique (family_id,user_id).
- `sbd_permission_audit` table: who changed what (previous/new), timestamp, optional reason.

Example minimal schema (Postgres-like, adapt to your migrations):
```sql
CREATE TABLE sbd_accounts (
  id uuid PRIMARY KEY,
  family_id uuid UNIQUE REFERENCES families(id),
  account_username text,
  account_name text,
  balance bigint NOT NULL DEFAULT 0,
  currency varchar(10) NOT NULL DEFAULT 'SBD',
  is_frozen boolean NOT NULL DEFAULT false,
  freeze_reason text,
  frozen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sbd_member_permissions (
  id uuid PRIMARY KEY,
  family_id uuid NOT NULL REFERENCES families(id),
  user_id uuid NOT NULL REFERENCES users(id),
  can_spend boolean NOT NULL DEFAULT false,
  spending_limit bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(family_id, user_id)
);

CREATE TABLE sbd_permission_audit (
  id uuid PRIMARY KEY,
  family_id uuid NOT NULL,
  changed_by_user_id uuid,
  target_user_id uuid,
  previous_can_spend boolean,
  previous_spending_limit bigint,
  new_can_spend boolean,
  new_spending_limit bigint,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

## Notifications & audit
- Insert an audit row whenever permissions change.
- Emit a family notification (maps to `FamilyNotification`) so the UI can display that permissions changed. Suggested `type`: `family_permission_change`. Include metadata with `changed_by` and `target_user_id`.

## Validation rules
- `spending_limit` must be an integer >= -1. Consider a `maximum_spending_limit` constraint.
- `user_id` in PUT must belong to the family; return 400/404 if not.

## Errors & messages (suggested)
- 400 {
  "detail": "spending_limit must be >= -1"
}
- 403 {
  "detail": "Only family administrators can update spending permissions"
}
- 403 {
  "detail": "User is not permitted to spend from family account"
}

## Tests backend should provide
- Unit tests for GET and PUT endpoints (happy path and validation errors).
- Authorization tests: admin vs non-admin behavior.
- Integration tests for transfer enforcement (cannot spend when can_spend=false; cannot send > spending_limit).
- Concurrency/integrity test to ensure no negative balances under concurrent sends.

## Frontend notes / UX expectations
- Frontend shows `Spending Limit: 0 SBD` when value is 0. If you want that to mean 'cannot spend', prefer setting `can_spend=false` and leaving limit = 0 to avoid ambiguous UX.
- The frontend expects the PUT to return the updated `SBDAccount` so it can refresh the UI immediately.
- If you implement approval workflows (e.g., admin approval required before change), returning `202 Accepted` with a status field is possible, but the current frontend expects synchronous success. Consider adding a `status` metadata field in the response if asynchronous.

## Example request/response (copy-paste)
- PUT /family/{familyId}/sbd-account/permissions
Request:
```json
{
  "user_id": "user_abc",
  "spending_limit": 200,
  "can_spend": true
}
```
Response (200):
```json
{
  "account_id": "sbd_123",
  "account_username": "family_sbd",
  "account_name": "Batra Family SBD",
  "balance": 5000,
  "currency": "SBD",
  "is_frozen": false,
  "member_permissions": {
    "user_abc": { "can_spend": true, "spending_limit": 200 },
    "user_def": { "can_spend": false, "spending_limit": 0 }
  }
}
```

## Quick backend checklist
- [ ] Add `sbd_accounts`, `sbd_member_permissions`, `sbd_permission_audit` (or adapt existing schema).
- [ ] Implement `GET /family/{familyId}/sbd-account` returning `member_permissions`.
- [ ] Implement `PUT /family/{familyId}/sbd-account/permissions` with auth/validation; return updated SBDAccount.
- [ ] Enforce permissions and limits in transfer endpoints; add tests.
- [ ] Create audit rows and family notifications on permission changes.
- [ ] Add `GET /family/limits` or return limits in `GET /family/{id}`.

---

If you want, I can also generate:
- SQL migration files (Postgres) ready for your migration tooling,
- Example controller code for a stack (Express/Django/Rails), or
- Example unit + integration test outlines.

Tell me which output you'd like next and I'll add it under `docs/` or `specs/` as a follow-up file.
