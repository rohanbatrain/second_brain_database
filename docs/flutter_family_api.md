# Family SBD API (Flutter) — Quick Reference

This doc is for the Flutter frontend team. It describes the API endpoints, request bodies, and JSON responses relevant to family payments and family-owned assets. No Python knowledge required — only JSON and endpoints.

Authentication
- All endpoints require the standard Authorization header with a valid JWT.
  - Header: `Authorization: Bearer <JWT>`

Common response patterns
- Success envelope (when returned by an endpoint):
  {
    "status": "success",
    "...": ...
  }
- Error envelope (generic):
  {
    "status": "error",
    "detail": <string or object>
  }
- HTTP status codes used:
  - 200 OK: success
  - 400 Bad Request: validation, insufficient funds, malformed request
  - 401 Unauthorized: missing or invalid JWT
  - 403 Forbidden: permission/authorization errors (family spend denied uses a specific error payload)
  - 404 Not Found: resource not found (user/item)
  - 500 Server Error: unexpected errors

Special family error (403):
- When a family payment is denied due to permission or freeze, API returns 403 with a detail object like:
  {
    "error": "FAMILY_SPENDING_DENIED",
    "message": "You don't have permission to spend from this family account"
  }

Endpoints

1) Get payment options (personal + families)
- GET /shop/payment-options
- Response (200):
  {
    "status": "success",
    "data": {
      "user_id": "<user_id>",
      "username": "alice",
      "payment_options": [
        {"payment_type": "personal", "balance": 500, "account_username": "alice"},
        {
          "payment_type": "family",
          "account_username": "family_smiths",
          "family_id": "fam_abc123",
          "family_name": "Smith Family",
          "balance": 2000,
          "user_permissions": {"can_spend": true, "spending_limit": 1000}
        }
      ]
    }
  }
- Usage: use this to show family accounts with `can_spend` true and balance information.

2) Buy an avatar (family or personal)
- POST /shop/avatars/buy
- Request (family):
  {
    "avatar_id": "emotion_tracker-static-avatar-cat-1",
    "payment_method": { "type": "family", "family_id": "fam_abc123" }
  }
- Request (personal, legacy supported):
  { "avatar_id": "emotion_tracker-static-avatar-cat-1" }
- Success (200) example (family):
  {
    "status": "success",
    "avatar": { "avatar_id": "...", "unlocked_at": "...", "transaction_id": "txn_...", "price": 100 },
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
- DB note: For family payments the purchased avatar is stored in the family's virtual user under `avatars_owned` (not in the purchaser's user doc). The Flutter app does not need to care where it is stored — use the API below to list owned assets.

3) Buy theme/banner/bundle
- POST /shop/themes/buy, /shop/banners/buy, /shop/bundles/buy
- Request format is same pattern as avatar. Use `payment_method` object for family payments.
- For bundles: the server expands bundle contents (avatars, themes) and stores each unlocked item on the target owner (user or family) with `transaction_id`.

4) Cart checkout
- POST /shop/cart/checkout
- Request: include `payment_method` (new format) to use family funds; legacy behavior without it uses personal tokens.
- Successful response includes `transaction_id` and `checked_out` list.

5) Get owned avatars (family-aware)
- GET /avatars/owned
- Response (200):
  { "avatars_owned": [ { "avatar_id": "...", "unlocked_at": "...", "transaction_id": "..." }, ... ] }
- Note: This endpoint merges personal-owned and family-owned avatars for all families the current user belongs to. Use this for UI to display all avatars the user can use.

6) Set current avatar
- POST /avatars/current
- Request:
  { "avatar_id": "emotion_tracker-static-avatar-cat-1" }
- Success: { "success": true, "avatar_id": "..." }
- Access rules: The avatar must be either personally owned, currently rented (and not expired), or family-owned by a family the user belongs to.

7) Get current avatar
- GET /avatars/current
- Returns the currently-set avatar for the calling app (determined by User-Agent mapping); unchanged behavior.

Audit fields available to client (read-only)
- For family-owned entries the server attaches audit fields inside the owned-item entries when written to the family account. These can be shown in admin or family activity UI if desired:
  - `purchased_by_user_id`
  - `purchased_by_username`
  - `family_transaction_id`

Frontend integration checklist (Flutter)
- To present family options:
  1. Call `GET /shop/payment-options` and show only family accounts where `user_permissions.can_spend` is true (or display read-only if false).
  2. When user picks a family, include `payment_method: { "type": "family", "family_id": "..." }` in the buy/checkout request.

- After a successful purchase:
  - Re-fetch `GET /avatars/owned` (or appropriate `/shop/*/owned` if we change parity later) to pick up family-owned items.
  - Show the `payment.transaction_id` to the user in receipts if needed.

- Handling errors:
  - If server returns 403 with `FAMILY_SPENDING_DENIED`, show a clear UI message indicating the family account is frozen or the user lacks spending permissions, and suggest opening family settings or contacting an admin.
  - For 400 errors (insufficient funds), show a balance and the amount required.

- Performance/UI tips:
  - Optimistically show a "purchase in progress" state, but only add the avatar to UI after the server confirms success and you re-fetch owned items.
  - Deduplicate avatars by `avatar_id` when merging lists from different sources.

Example Flutter (pseudo) flow for a family purchase
1. Fetch payment options
  final options = await api.get('/shop/payment-options');
  showFamilyChoices(options.data.payment_options);

2. User selects family and buys an avatar
  final body = {
    'avatar_id': avatarId,
    'payment_method': {'type': 'family', 'family_id': selectedFamilyId}
  };
  final resp = await api.post('/shop/avatars/buy', body);
  if (resp.status == 200) {
    // show success and refresh owned avatars
    await api.get('/avatars/owned');
  } else if (resp.status == 403 && resp.detail?.error == 'FAMILY_SPENDING_DENIED') {
    // show family permission/frozen message
  }

Notes & caveats for Flutter team
- The server stores family-owned items centrally; the Flutter client should rely on `/avatars/owned` for display, not local assumptions about where the data lives.
- If you previously used `/shop/owned` and expect family items there, switch to `/avatars/owned` for avatar UI; ping me and I can make `/shop/owned` return family-aware results as well.
- If you need real-time notifications about family purchases, hook your push/notification integration to the family notification system (server sends family notifications on purchases).

Questions or adjustments
- If you want a short Flutter-specific SDK helper (Dart code) that builds the `payment_method` and wraps error handling, I can add it.
- If you want `/shop/owned` made family-aware so existing UI code doesn't change, I can update that endpoint too.

---

File created by engineering on behalf of frontend team.

## Handling Users with Multiple Families

Users can belong to multiple families. The backend handles this by requiring explicit family selection for payments and merging owned items across all families for listings.

### Key Rules
- **Membership check**: All family actions require the user to be a member of the specified family. The server verifies this.
- **Explicit family selection**: For family payments, you must include `payment_method` with the `family_id`:
  { "payment_method": { "type": "family", "family_id": "fam_abc123" } }
  The server does not auto-select a family — the request must specify one.
- **Charge target**: Tokens are deducted and items are stored on the chosen family's virtual account only.
- **Ownership visibility**: `GET /avatars/owned` merges personal-owned + family-owned items from all families the user belongs to (deduped by `avatar_id`).
- **Avatar selection**: `POST /avatars/current` allows setting an avatar if it's owned by any family the user belongs to.
- **Permissions**: Spending permissions and limits are checked per-family.

### UI Implementation
1. **Show family options**: Call `GET /shop/payment-options` and display family accounts with `family_name`, `balance`, and `user_permissions.can_spend`.
2. **Require family pick**: For family purchases, show a chooser and require the user to select one family. Build the request with the selected `family_id`.
3. **Validate before send**: Check `can_spend` and `balance >= price` on the client to avoid errors.
4. **Handle responses**: On 403 `FAMILY_SPENDING_DENIED`, show the family name and reason. On success, re-fetch `GET /avatars/owned`.
5. **Owned items**: Use `GET /avatars/owned` — it already merges across families.

### JSON Examples

Payment options (user in 2 families):
```json
{
  "status": "success",
  "data": {
    "payment_options": [
      {"payment_type": "personal", "account_username": "alice", "balance": 120},
      {
        "payment_type": "family",
        "account_username": "family_smiths",
        "family_id": "fam_111",
        "family_name": "Smiths",
        "balance": 2000,
        "user_permissions": {"can_spend": true, "spending_limit": 1000}
      },
      {
        "payment_type": "family",
        "account_username": "family_parkers",
        "family_id": "fam_222",
        "family_name": "Parkers",
        "balance": 50,
        "user_permissions": {"can_spend": false, "spending_limit": 0}
      }
    ]
  }
}
```

Family purchase request (choosing Smiths):
```json
{
  "avatar_id": "emotion_tracker-static-avatar-cat-1",
  "payment_method": { "type": "family", "family_id": "fam_111" }
}
```

Success response:
```json
{
  "status": "success",
  "avatar": { "avatar_id": "...", "transaction_id": "txn_..." },
  "payment": {
    "payment_type": "family",
    "from_account": "family_smiths",
    "family_id": "fam_111",
    "amount": 100,
    "transaction_id": "txn_..."
  }
}
```

If choosing Parkers (no permission):
403 response:
```json
{
  "status": "error",
  "detail": {
    "error": "FAMILY_SPENDING_DENIED",
    "message": "You don't have permission to spend from this family account"
  }
}
```

### UI Patterns
- **Family chooser**: Show families with status badges (green: can spend + sufficient balance; orange: can spend but low balance; grey: no permission).
- **Default family**: No default — require explicit pick to avoid accidental charges.
- **Receipts**: Show family name and `transaction_id` for family payments.

### Edge Cases
- Same item owned by multiple families: Deduped in listings; selection works if owned by any family.
- Frozen accounts: Purchase denied for that family; user can pick another.
- No families: Falls back to personal payment only.