# Feature Specification: Family SBD Top-up (Flutter Client)

**Feature Branch**: `001-family-sbd-topup`
**Created**: 2025-10-22
**Status**: Ready for Implementation
**Input**: User description: "Enable users to top up a family's SBD account via the family's virtual account username (client-side flow)."

## Clarifications

### Session 2025-10-22

- Q: Top-up permission model → A: Open — any authenticated user may send to a family's virtual username. (Answered 2025-10-22)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Simple Top-up (Priority: P1)

As an authenticated user who has an SBD wallet balance, I want to top up a family's
SBD account by sending tokens to the family's virtual account username so that the
family's balance is increased and a transaction record is created.

Why this priority: This is the core value of the feature (enables store of funds for families).

Independent Test: Use widget + integration tests to simulate opening the family SBD
screen, entering an amount and optional note, submitting, and verifying balance and
transaction updates for both sender and family.

Acceptance Scenarios:

1. **Given** the user is authenticated and has sufficient SBD balance, **When** the user
   opens the family SBD screen, **Then** they see the family's account username and an enabled
   "Top up" CTA.
2. **Given** the user enters a positive integer amount and confirms, **When** the send completes
   successfully, **Then** the user's and family's balances and transaction lists are refreshed
   and a success message/analytics event is emitted.
3. **Given** the user tries to enter zero/negative amount or greater than their available balance,
   **When** they submit, **Then** show a clear validation error and prevent send.

---

### User Story 2 - Failure Cases & Recovery (Priority: P2)

As an authenticated user, I want clear, actionable error messages and retry options if the
top-up fails so I can understand and recover (e.g., insufficient funds, frozen family account,
network error).

Independent Test: Integration tests that force server responses (insufficient balance, frozen
account, network error) and assert displayed messages and retry behavior.

Acceptance Scenarios:

1. **Given** insufficient balance, **When** user submits, **Then** show "Insufficient funds" and
   keep dialog open with option to edit amount.
2. **Given** family account is frozen, **When** user submits, **Then** show the server-provided
   friendly message and suggest next steps (contact owner/support).

---

### User Story 3 - Observability & Analytics (Priority: P3)

As an operator, I want an analytics event and monitoring for top-up operations so we can track
success/failure rates and detect anomalies.

Independent Test: Unit test that ensures analytics call is invoked on success; integration test
verifies metric emitted in staging pipeline (mock).

Acceptance Scenarios:

1. **Given** a successful top-up, **When** the operation completes, **Then** emit `family_topup_success`
  with properties { family_id, amount, sender_id } — do NOT emit plaintext usernames or tokens. `sender_id` SHOULD be a non-PII identifier (user id or one-way hashed value) per privacy rules.

---

### Edge Cases

- Missing `account_username` in family data: show clear fallback (cannot top up; provide steps).
- Concurrent top-ups: server-side atomicity assumed; client must refresh balances after success.
- Session expiry mid-flow: redirect to login and preserve attempted amount in dialog where safe.
- Device offline: disable Top up CTA and surface offline guidance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The client MUST display the family's `account_username` on the Family SBD screen when present.
- **FR-002**: The client MUST provide a Top up dialog capturing an integer amount > 0 and an optional note.
- **FR-003**: The client MUST validate amount locally (positive integer, <= sender available balance) before calling the provider.
- **FR-004**: The client MUST call existing provider `sendTokens(toUser: accountUsername, amount: amount, note: optional)` and handle success/failure responses.
- **FR-005**: On success, the client MUST refresh both the sender's and family's balances and transaction lists from the server and show confirmation.
- **FR-006**: The client MUST map server error codes/messages to user-friendly strings (error mapping table to be added).
- **FR-007**: The top-up CTA MUST be disabled when the family account is marked frozen or when the client is offline.
- **FR-008**: The client MUST not log plaintext PII (family identifiers or user tokens) in telemetry or logs.

### Key Entities *(include if feature involves data)*

- **SBDAccount**: { family_id, account_username, balance, frozen } — note: `account_username` is required for top-up.
- **TopUpTransaction**: { id, from_user, to_username, amount, note, timestamp, status }

## Constitution Alignment

- Tests: Add unit tests for client validation, widget tests for dialog UI and validation messages, and an integration test that verifies end-to-end balance updates (mock backend or staging).
- Privacy & Observability: Emit analytics events `family_topup_attempt` and `family_topup_success` with minimal non-PII props; do not log raw account usernames or tokens.
- Versioning impact: No server API changes expected for minimal client-only implementation if `account_username` already exists; if server changes are required, document migration path.
- Simplicity: Reuse existing `sbdTokensProvider.sendTokens()`; avoid introducing new dependencies.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of successful top-ups should complete within 3 seconds from user confirmation (measured in staging).
- **SC-002**: 100% of top-up attempts with insufficient funds must show a clear error message and prevent token send (verifiable via integration tests).
- **SC-003**: 90% of users complete top-up flow on first attempt in usability testing (qualitative acceptance).
- **SC-004**: No PII leaks in logs as verified by a CI privacy linting step.

## Assumptions

- The repository's `sbdTokensProvider` supports sending to arbitrary usernames using `sendTokens(toUser, amount, note)`.
- Server responds with a canonical `account_username` and canonical balance values.
- The product team will decide the permission model (open vs member-only) during spec clarification.

## Deliverables

- UI: `sbd_account_screen.dart` Top up CTA and dialog.
- Provider integration: use `sbdTokensProvider.sendTokens(...)` and refresh balances.
- Tests: unit, widget, and an integration test.
- Docs: sample request/response and error mapping table added to PRD and `API_UI_COMPARISON.md`.

## Ready for planning

This spec is ready for `/speckit.plan` once Q1 is answered and a sample server request/response is confirmed or added to the spec.

---

## Backend API Contract (Reference Only)

The Flutter implementation should integrate with these existing backend endpoints:

### Get Family SBD Account
```http
GET /family/{family_id}/sbd-account
Authorization: Bearer {token}
```

**Response:**
```json
{
  "account_username": "family_johnson_family_abc123",
  "balance": 150,
  "is_frozen": false,
  "spending_permissions": {...}
}
```

### Send SBD Tokens
```http
POST /sbd_tokens/send
Authorization: Bearer {token}
Content-Type: application/json

{
  "to_user": "family_johnson_family_abc123",
  "amount": 50,
  "note": "Monthly allowance top-up"
}
```

**Success Response:**
```json
{
  "status": "success",
  "from_user": "user123",
  "to_user": "family_johnson_family_abc123",
  "amount": 50,
  "transaction_id": "txn_123456"
}
```

**Error Responses:**
```json
// Insufficient funds
{"status": "error", "detail": "Insufficient sbd_tokens"}

// Frozen account
{"status": "error", "detail": "Family account is currently frozen and cannot be used for spending"}

// Invalid amount
{"status": "error", "detail": "Amount must be a positive integer"}
```

### Error Mapping Table

| Server Error | User-Friendly Message | Action |
|-------------|----------------------|--------|
| "Insufficient sbd_tokens" | "You don't have enough tokens for this transaction" | Keep dialog open, allow amount edit |
| "Family account is currently frozen..." | "This family account is temporarily frozen. Please contact family administrators." | Close dialog, suggest contacting support |
| "Amount must be a positive integer" | "Please enter a valid amount" | Keep dialog open, highlight amount field |
| Network errors | "Connection failed. Please check your internet and try again." | Show retry button |

## Implementation Notes

- Use existing `sbdTokensProvider.sendTokens()` method
- Refresh balances using existing balance fetch methods
- Handle offline state by disabling CTA when `connectivity.isConnected == false`
- Analytics: emit `family_topup_attempt` on submit, `family_topup_success` on completion
- Privacy: Never log `account_username` or token values in analytics</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/family-sbd-topup-flutter-spec.md