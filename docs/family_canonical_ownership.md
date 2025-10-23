# Family Canonical Ownership — Design and Implementation Guide

This document describes the changes implemented to make family virtual SBD accounts the canonical owner for shop purchases and avatar ownership ("Approach A"). It explains the rationale, the exact code changes, API usage, database effects, verification steps, migration considerations, testing, and follow-ups.

## TL;DR
- Purchases paid with a family account are recorded on the family's virtual user document (the virtual SBD account) instead of the purchaser's personal user document.
- The shape of owned-item entries remains the same as user-owned arrays (e.g., `avatars_owned`, `themes_owned`) with a few audit fields added for family-paid entries:
  - `purchased_by_user_id`
  - `purchased_by_username`
  - `family_transaction_id`
- Frontend: keep calling the same endpoints. To use family funds, include `payment_method: {"type": "family", "family_id": "<family_id>"}`. Use `GET /shop/payment-options` to list family accounts and permissions.

## Rationale
Previously, the app stored ownership on the purchaser's user document. To support canonical family ownership (so a family's purchases are owned by the family and available to all members), we introduced the following changes:
- Centralized family-owned retrieval helper in `family_manager`.
- Persisted purchased assets to the family virtual user document when family funds are used.
- Updated avatar listing and avatar selection endpoints to accept family-owned assets.

This keeps frontend logic simple, preserves backwards compatibility for personal purchases, and centralizes family-owned asset state.

## Files Changed (high level)
- `src/second_brain_database/managers/family_manager.py`
  - Added: `get_family_owned_items(family_id: str, item_type: str) -> List[Dict[str, Any]]`
  - Ensures safe retrieval of `*_owned` arrays from the family virtual user document.

- `src/second_brain_database/routes/shop/routes.py`
  - Modified `process_payment()` behavior so that when `payment_type == 'family'` the server will write purchased entries into the family virtual user document (e.g., `avatars_owned`, `themes_owned`, `banners_owned`, `bundles_owned`).
  - Added audit fields to the entries when stored on family account: `purchased_by_user_id`, `purchased_by_username`, `family_transaction_id`.
  - Ensured cart checkout flow writes bundle contents to the family virtual user when appropriate.

- `src/second_brain_database/routes/avatars/routes.py`
  - `GET /avatars/owned` now merges personal-owned plus family-owned avatars for families the current user belongs to (deduped by `avatar_id`).
  - `POST /avatars/current` ownership check now accepts family-owned avatars when validating access.

- `docs/family_canonical_ownership.md` (this file) — created to describe the system and usage.

## API usage and examples
All endpoints use the same routes — only the request body needs the `payment_method` object to select a family payment.

1) Buy an avatar using family funds

Request (POST /shop/avatars/buy):

```json
{
  "avatar_id": "emotion_tracker-static-avatar-cat-1",
  "payment_method": { "type": "family", "family_id": "fam_abc123" }
}
```

Response (successful, new-format):

```json
{
  "status": "success",
  "avatar": {
    "avatar_id": "emotion_tracker-static-avatar-cat-1",
    "unlocked_at": "2025-10-23T12:34:56Z",
    "permanent": true,
    "source": "purchase",
    "transaction_id": "txn_...",
    "note": "Bought from shop",
    "price": 100
  },
  "payment": {
    "payment_type": "family",
    "from_account": "family_smiths",
    "family_id": "fam_abc123",
    "family_name": "Smith Family",
    "amount": 100,
    "transaction_id": "txn_...",
    "family_member": "alice"
  }
}
```

DB effect (family virtual user document `username: family_smiths`):

```json
{
  "avatars_owned": [
    {
      "avatar_id": "emotion_tracker-static-avatar-cat-1",
      "unlocked_at": "2025-10-23T12:34:56Z",
      "permanent": true,
      "source": "purchase",
      "transaction_id": "txn_...",
      "price": 100,
      "purchased_by_user_id": "<alice_id>",
      "purchased_by_username": "alice",
      "family_transaction_id": "txn_..."
    }
  ],
  "sbd_tokens": 1234,
  "sbd_tokens_transactions": [ ... ]
}
```

2) List owned avatars (profile route)

- Endpoint: `GET /avatars/owned`
- This returns the personal owned avatars and appends family-owned avatars from any family the current user belongs to. Use this endpoint for UI presentation when family-owned assets should be visible.

3) Set current avatar

- Endpoint: `POST /avatars/current` with `{ "avatar_id": "..." }`.
- The endpoint now accepts family-owned avatar selections (provided the caller is a family member and the family owns the asset). Rental expiry checks still apply.

## Implementation details and notes
- Owned item shape: We intentionally preserved the existing owned-item structure to avoid breaking frontend assumptions. For family purchases we add the three audit fields; additional metadata can be added later if needed.

- Where writes occur: When a purchase is paid with `payment_type == 'family'`, the code writes purchased items to the family virtual user document (found by `account_username` stored in the family doc). The `users` collection stores the family virtual account as a user document with `is_virtual_account: True`.

- Atomicity: Current implementation performs sequential updates:
  1. Deduct tokens from family virtual account (`$inc` and `$push` sbd_tokens_transactions).
  2. Push purchased item(s) into the family virtual user's `*_owned` arrays.

  This is done with `upsert=True` on the owned-list updates to be resilient. If you require strict all-or-nothing behavior, enable MongoDB replica set support in your environment and we can switch to transactions (sessions) so token deduction and owned-list writes occur in a single transaction.

- Notifications: The system sends family notifications about spending (this was already implemented). Transactions include family attribution fields for audit.

- Backward compatibility: If the client omits the `payment_method` object the API defaults to personal tokens (legacy format). Personal purchases continue to write to the purchaser's user doc as before.

## Migrations & data hygiene
- Ensure every family virtual user document has the expected owned arrays present:
  - `avatars_owned`, `themes_owned`, `banners_owned`, `bundles_owned`

  You can add a simple migration that runs:

  ```py
  users = db.users
  users.update_many({"is_virtual_account": True}, {"$set": {
    "avatars_owned": [], "themes_owned": [], "banners_owned": [], "bundles_owned": []
  }})
  ```

- If you have previous family purchases recorded elsewhere, consider a one-time backfill to consolidate ownership into family virtual accounts.

## Testing and verification
- Recommended tests (unit/integration):
  1. Family purchase succeeds: authenticated family member with `can_spend` purchases an avatar; verify family virtual user's `avatars_owned` contains the entry and `sbd_tokens` decreased.
  2. Permission denied: user without `can_spend` or over limit receives `403 FAMILY_SPENDING_DENIED`.
  3. Account frozen: family account frozen leads to error and no deduction.
  4. Avatar selection: a family member can set a family-owned avatar as current.
  5. Cart checkout: cart checkout using family funds results in items being written to the family virtual account.

- Operational verification (smoke test):
  1. Use staging environment.
  2. Authenticate as a family member with spending permission.
  3. Call `POST /shop/avatars/buy` with the family payment_method.
  4. Check response for `payment` and `transaction_id`.
  5. Query DB for the family virtual user `avatars_owned` and verify the presence of the purchased entry and that `sbd_tokens` decreased.

## Frontend developer notes
- To offer family payment options, call `GET /shop/payment-options` and present only family accounts where the user has `can_spend` and sufficient `balance` (or show a helpful error instead of allowing selection).
- After a successful purchase, refresh the owned lists (prefer `GET /avatars/owned` for avatar UI since it is family-aware).
- If your UI calls `/shop/owned` and expects to see family-owned items, we can update those endpoints for parity (let me know and I'll add it).

## Operational considerations
- Auditing: Transaction logs include family attribution; add monitoring to detect frequent `FAMILY_SPENDING_DENIED` errors after rollout.
- Rollback: To revert this change, restore previous behavior where purchases always wrote to the purchaser's user doc. That is a code change and not a data rollback — family-owned entries would remain in the database until cleaned.

## Next steps and optional improvements
- Make family token deduction + owned-list writes transactional using MongoDB sessions (requires replica set). I can add this change and tests.
- Update shop-owned endpoints (`/shop/*/owned` and `/shop/owned`) to be family-aware for parity.
- Add automated tests for the family purchase flows and avatar selection.
- Add a migration/backfill script if you need historical family purchases consolidated.

---

If you want, I can now:
- Add the transactional/session-based implementation for family payments (requires checking replica set availability).
- Implement the test cases and run the test suite in your environment and report failures.
- Update `shop/owned` endpoints to include family-owned items.

Tell me which of the above you'd like next and I'll implement it and run tests.