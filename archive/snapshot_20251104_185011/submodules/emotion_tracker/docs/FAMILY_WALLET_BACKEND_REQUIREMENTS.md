# Family Wallet Backend Requirements

TL;DR

- Implement family-scoped SBD account APIs that mirror the single-user SBD wallet patterns (balance, transactions, send/topup) plus family-specific flows (member allowances, token-requests, approvals, freeze/unfreeze, audit logs, webhooks).
- Key endpoints: GET family account, GET transactions, POST transfer, POST topup, POST token-request, POST review-request, PUT member permissions, POST freeze/unfreeze, webhooks for events.
- Important: atomic DB transactions for debits/credits, idempotency keys, DB row-level locking (or optimistic locking), audit logs, and webhook HMAC signature with retries.


## Goals

1. Provide a family-level shared SBD account that behaves like the single-user SBD wallet but supports multi-member rules and admin workflows.
2. Support member allowances, request-and-approval flows, freeze/unfreeze and emergency operations with strong auditability.
3. Keep frontend work minimal by matching the existing `family_api_service.dart` expectations where possible.


## Required endpoints (summary)

1. GET /families/{familyId}/sbd-account
2. GET /families/{familyId}/sbd-account/transactions
3. POST /families/{familyId}/sbd-account/transfer
4. POST /families/{familyId}/sbd-account/topup
5. POST /families/{familyId}/token-requests
6. GET /families/{familyId}/token-requests/pending
7. POST /families/{familyId}/token-requests/{requestId}/review
8. PUT /families/{familyId}/members/{memberId}/permissions
9. POST /families/{familyId}/sbd-account/freeze
10. POST /families/{familyId}/sbd-account/emergency-unfreeze
11. GET /families/{familyId}/members/{memberId}/available
12. PUT /families/{familyId}/sbd-account/name (update account display name)
13. Webhook management & delivery endpoint(s)


## Data models (minimal)

- FamilySBDAccount
  - account_id, family_id, balance (int), currency, is_frozen, freeze_reason, frozen_at
  - account_username (string): Technical username for API operations and QR codes
  - account_name (string, optional): User-friendly display name for the account
- FamilyTransaction
  - transaction_id, account_id, type, amount, currency, from_user, to_user, status, reference, metadata, created_at
- MemberPermissions
  - id, family_id, user_id, daily_limit, weekly_limit, can_send, can_request
- TokenRequest
  - id, family_id, amount, requested_by, status, reason, reviewed_by, reviewed_at
- AdminAction (audit)
  - id, family_id, action, performed_by, payload, created_at
- IdempotencyKey
  - user_id, key, fingerprint, response_ref, created_at


## Account Naming Feature

### **Requirements**
- Add `account_username` field: Auto-generated technical identifier (e.g., "family_vacation_fund_123") for API operations and QR codes
- Add `account_name` field: Optional user-friendly display name (e.g., "Vacation Fund") set by family admin
- Fallback logic: If `account_name` is null/empty, frontend falls back to `account_username`

### **Database Changes**
- Add `account_username` column to family_sbd_accounts table (required, unique)
- Add `account_name` column to family_sbd_accounts table (optional, nullable)
- Generate `account_username` on account creation using pattern: `family_{sanitized_name}_{family_id}`

### **API Changes**
- Include `account_username` and `account_name` in all account-related responses
- Account creation endpoint should accept optional `account_name` parameter
- Add endpoint to update account name (admin only): `PUT /families/{familyId}/sbd-account/name`

### **Business Logic**
- `account_username` is immutable once created
- `account_name` can be updated by family admins
- QR codes should encode `account_username` for technical operations
- Display names should use `account_name` with fallback to `account_username`

Atomic transfers/topups
- Use DB transactions to update account balance and create transaction rows atomically. Use `SELECT FOR UPDATE` or optimistic locking with retries.
- Implement idempotency support for transfer/topup/approve endpoints (X-Idempotency-Key).

Permission checks
- Enforce per-member can_send and limit checks (daily/weekly). Return 403 when permission violated, 409 for insufficient funds.

Freeze flows
- When frozen: disallow outgoing transfers and approvals; allow incoming topups.
- Keep freeze metadata and add admin_action audit entry.

Token request flow
- POST creates request with status=pending; admins receive notification.
- POST review approves/denies; approval triggers an atomic transfer (or fail cleanly if insufficient funds).

Webhooks
- Emit events for transaction.created, balance.updated, request.created, request.reviewed, account.frozen/unfrozen.
- Secure with HMAC signature header; retry with exponential backoff.


## Example contracts (selected)

GET /families/{familyId}/sbd-account (200)
{
  "account_id":"fam-acct_123",
  "account_username":"family_vacation_fund_123",
  "account_name":"Vacation Fund",
  "family_id":"family_123",
  "balance":1000,
  "currency":"SBD",
  "is_frozen":false,
  "freeze_reason":null,
  "member_permissions":{
    "user_1":{"daily_limit":100, "weekly_limit":500, "can_send":true, "can_request":true}
  },
  "updated_at":"2025-10-22T10:00:00Z"
}

GET /families/{familyId}/sbd-account/transactions (200)
{
  "account_username":"family_vacation_fund_123",
  "account_name":"Vacation Fund",
  "current_balance":1000,
  "transactions":[
    {
      "transaction_id":"tx_678",
      "type":"transfer",
      "amount":50,
      "currency":"SBD",
      "from_user":"user_2",
      "to_user":"user_x",
      "status":"succeeded",
      "created_at":"2025-10-22T10:05:00Z"
    }
  ],
  "total_transactions":25,
  "has_more":false
}

POST /families/{familyId}/sbd-account/transfer (request)
{
  "to_user":"user_x",
  "amount":50,
  "note":"snacks",
  "idempotency_key":"uuid-1234"
}

Response (200 success)
{
  "transaction_id":"tx_678",
  "account_id":"fam-acct_123",
  "type":"transfer",
  "amount":50,
  "currency":"SBD",
  "from_user":"user_2",
  "to_user":"user_x",
  "status":"succeeded",
  "created_at":"2025-10-22T10:05:00Z"
}

PUT /families/{familyId}/sbd-account/name (200)
Request:
{ "account_name": "Summer Vacation Fund" }
Response:
{
  "account_id":"fam-acct_123",
  "account_username":"family_vacation_fund_123",
  "account_name":"Summer Vacation Fund",
  "updated_at":"2025-10-22T10:10:00Z"
}

POST /families/{familyId}/token-requests (201)
Request:
{ "amount": 120, "reason":"groceries", "requested_by":"user_3", "idempotency_key":"..." }
Response:
{
  "request_id":"req_99",
  "family_id":"family_123",
  "amount":120,
  "requested_by":"user_3",
  "status":"pending",
  "created_at":"..."
}


## Edge cases & tests

- Concurrency: two transfers racing for the same funds — test SELECT FOR UPDATE and optimistic retries.
- Idempotency: repeated requests with same key should not duplicate transactions.
- Permission enforcement: exceeding daily/weekly limits.
- Freeze behaviour: outgoing blocked, incoming allowed.
- Reconciliation: ledger vs account balance mismatches must be detectable.


## Monitoring & metrics

- Track failed_transactions, pending_token_requests, webhook_delivery_success_rate, reconciliation_mismatches.
- Alert on rapid balance decreases and long-lived pending requests.


## Frontend mapping & notes

- `family_api_service.dart` already expects many of these endpoints: `getSBDAccount`, `getTransactions`, `createTokenRequest`, `reviewTokenRequest`, `freezeAccount`, `unfreezeAccount`, `emergencyUnfreezeAccount`, `updateSpendingPermissions`.
- Keep API paths identical to the frontend calls or update frontend to match the final API. Prefer `/family/{id}/...` as used in repo.
- Provide `available_balance` or per-member available endpoint to avoid frontend computing complex limits.


## Next steps & recommendations

1. **Database Migration**: Add `account_username` and `account_name` columns to family_sbd_accounts table
2. **Account Creation Logic**: Generate unique `account_username` on family account creation
3. **API Updates**: Include new fields in all account-related endpoints
4. **Name Update Endpoint**: Implement PUT /families/{familyId}/sbd-account/name for admin account renaming
5. Implement DB tables and run migrations for accounts, transactions, token_requests, member_permissions, and idempotency.
6. Build REST endpoints with strong validation and transactional semantics.
7. Add webhook emitter and management and secure it with HMAC.
8. Provide an OpenAPI spec so frontend and backend can agree on contract.
9. Add unit+integration tests for concurrency, idempotency and token-request flows.


## Appendix: Webhook sample event

POST /webhooks/target
Headers:
- X-Signature: sha256=hex_hmac
Body:
{
  "event_id":"evt_123",
  "type":"family.sbd.transaction.created",
  "timestamp":"2025-10-22T10:10:00Z",
  "payload": { /* transaction object */ }
}

## Database Migration Example

```sql
-- Add account naming fields to family_sbd_accounts table
ALTER TABLE family_sbd_accounts 
ADD COLUMN account_username VARCHAR(255) UNIQUE NOT NULL,
ADD COLUMN account_name VARCHAR(255);

-- Create index for account_username lookups
CREATE INDEX idx_family_sbd_accounts_username ON family_sbd_accounts(account_username);

-- Generate account_username for existing accounts (run this after adding the column)
UPDATE family_sbd_accounts 
SET account_username = CONCAT('family_', REPLACE(LOWER(family_id), '-', '_'), '_', id)
WHERE account_username IS NULL;

-- Add NOT NULL constraint after populating existing data
ALTER TABLE family_sbd_accounts 
ALTER COLUMN account_username SET NOT NULL;
```

If you want I can now:
- generate an OpenAPI (Swagger) spec for these endpoints, or
- add server skeleton code (choose language: Node/Express, Python/FastAPI, Go, or Java/Spring), or
- create DB migration SQL for Postgres to add required tables.

Which one should I do next?