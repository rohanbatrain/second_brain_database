# Family SBD API — Frontend Spec

Copy/paste-ready spec for the Flutter team. Use this when implementing the "Can Spend" toggle and "Spending Limit" UI.

---

## Authentication
- All endpoints require a Bearer token in the `Authorization` header.

## Endpoints (summary)
1. GET /family/{familyId}/sbd-account
2. PUT /family/{familyId}/sbd-account/permissions
3. GET /family/limits

---

## 1) GET /family/{familyId}/sbd-account
- Auth: Bearer
- Purpose: Return the family SBD virtual account and per-member permissions used by the UI.
- Who can call: any family member.

Important response fields (the UI should use `member_permissions`):
- account_id: string | null
- account_username: string
- account_name: string | null
- balance: integer (smallest unit)
- currency: string (e.g. `SBD`)
- is_frozen: boolean
- freeze_reason: string | null
- frozen_at: ISO-8601 datetime | null
- member_permissions: object keyed by `user_id` -> { can_spend: bool, spending_limit: int }
  - This is the simple map the frontend should read for the toggle and limit display.
- spending_permissions: richer map retained for audit (contains updated_by, updated_at, role)
- notification_settings: object (optional)
- recent_transactions: array (optional)

Example (HTTP 200):

```json
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
    "user_abc": {"role":"member","spending_limit":200,"can_spend":true,"updated_by":"admin_1","updated_at":"2025-10-22T12:00:00Z"}
  },
  "notification_settings": {},
  "recent_transactions": []
}
```

Notes for frontend:
- Treat `spending_limit == -1` as "Unlimited".
- `balance` and `amount` fields are integers (smallest unit). Convert/format in UI as per currency rules.

Errors: 401, 403 (not a family member), 404

---

## 2) PUT /family/{familyId}/sbd-account/permissions
- Auth: Bearer
- Purpose: Admin-only update of one member's spending permissions.
- Who can call: family administrators only (server enforces).

Request body (JSON) — matches frontend `UpdateSpendingPermissionsRequest`:

```json
{
  "user_id": "user_abc",
  "spending_limit": 100,
  "can_spend": true
}
```

Validation rules (server-side):
- `spending_limit` must be integer >= -1 (where -1 == Unlimited)
- `user_id` must belong to the family
- caller must be a family admin

Response: HTTP 200 with the full, updated SBD account JSON (same shape as GET /sbd-account). The frontend should replace its local SBD account state with the returned payload after a successful update.

Errors:
- 400 validation (e.g., invalid spending_limit)
- 401 unauthorized
- 403 forbidden (caller not admin)
- 404 family or target user not found

Example request/response flow:
- Admin changes user `user_abc` limit to `200` and enables spending.
- Client sends the PUT body above.
- Server responds with the updated full account JSON (see GET example) containing updated `member_permissions` and `spending_permissions` entries.

UI behavior:
- After PUT succeeds, update UI using the returned account object (do not assume the update succeeded locally).
- When `can_spend` === false, visually disable spending controls for that user.
- When `spending_limit` === -1 show "Unlimited" instead of `-1 SBD`.

---

## 3) GET /family/limits
- Auth: Bearer
- Purpose: Return family/global limits and flags used by the UI.

Example response:
```json
{
  "default_spending_limit": 100,
  "maximum_spending_limit": 100000,
  "require_admin_approval_for_spending": true
}
```

Note: `GET /family/{id}` may already contain `settings` — it is acceptable to read limits there.

---

## Authorization & transfer rules (backend enforcement)
- Only family admins may call PUT to change others' permissions.
- Transfer/transaction flows are subject to these checks (server enforced):
  - If `can_spend == false` => reject transfer with 403 and clear message.
  - If `spending_limit != -1` and `amount > spending_limit` => reject with 400/403 (or route to approval flow).
  - If no `member_permissions` entry exists for the user => fallback to family default or deny.

## Notifications & audit
- When permissions change, a permission-audit row is created server-side and a family notification of type `family_permission_change` is emitted with metadata `{ changed_by, target_user_id }` so the UI can show an in-app notification.

## Error & user messages (recommended)
- 400 { "detail": "spending_limit must be >= -1" }
- 403 { "detail": "Only family administrators can update spending permissions" }
- 403 { "detail": "User is not permitted to spend from family account" }

---

## Frontend acceptance tests
- Admin can toggle `Can Spend` for a member; PUT is sent and UI updates from the returned account payload.
- Admin can set `spending_limit = -1` and UI renders "Unlimited".
- Non-admin receives 403 when attempting to update permissions (UI surfaces error).
- When `can_spend` is false the UI prevents spend flows and shows a clear message.
- After successful PUT, member list and account card reflect the new permissions.

---

## Sample cURL (replace IDs and TOKEN):

GET:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  -X GET "https://api.example.com/family/{familyId}/sbd-account"
```

PUT:
```bash
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -X PUT "https://api.example.com/family/{familyId}/sbd-account/permissions" \
     -d '{"user_id":"user_abc","spending_limit":200,"can_spend":true}'
```

GET limits:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  -X GET "https://api.example.com/family/limits"
```

---

## Backend files changed (for traceability)
- `src/second_brain_database/managers/family_manager.py` — manager returns a simplified `member_permissions` map (user_id -> {can_spend, spending_limit}) and enriches account with `account_id`, `account_name`, `currency`, `freeze_reason`.
- `src/second_brain_database/routes/family/sbd_routes.py` — PUT `/family/{familyId}/sbd-account/permissions` now returns the full SBDAccount JSON after applying updates.
- Spec document: `docs/family_sbd_api_for_frontend.md` (this file).

---

If you'd like, I can also produce:
- An OpenAPI (YAML) snippet for these three endpoints,
- A minimal `SBDAccount` TypeScript/JSON schema the Flutter team can paste into their models,
- Or a ready-to-send email body containing these instructions.

Tell me which extra artifact you want and I will add it.
