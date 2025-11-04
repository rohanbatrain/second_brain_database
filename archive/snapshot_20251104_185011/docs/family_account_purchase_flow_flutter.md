# Family Account Purchase Flow (Admin & Non-Admin) — Flutter Frontend Guide

## 1. Overview

- **Non-admins** (regular family members) can initiate purchases using the family wallet, but some purchases may require admin approval.
- **Admins** can spend directly (if within limits) and are responsible for approving/denying pending requests from other members.

---

## 2. API Endpoints

### Initiate Purchase

- **Endpoint:** `POST /shop/purchase`
- **Request Body:**
  ```json
  {
    "item_id": "<item_id>",
    "quantity": 1,
    "use_family_wallet": true
  }
  ```
- **Possible Responses:**
  - `200 OK`: Purchase completed immediately (no approval needed).
  - `202 Accepted`: Purchase is pending admin approval (request created).

### View Purchase Requests (Admin & Member)

- **Endpoint:** `GET /family/wallet/purchase-requests`
- **Query:** `status=PENDING` (for pending requests)
- **Response:** List of requests, with requester, item, cost, status, etc.

### Approve/Deny Request (Admin only)

- **Approve:** `POST /family/wallet/purchase-requests/{request_id}/approve`
- **Deny:** `POST /family/wallet/purchase-requests/{request_id}/deny` (optional reason)

---

## 3. UI/UX Flow

### Non-Admin (Member) Flow

1. **Shop Item Screen**
   - Show "Pay with Family Wallet" button if user has `can_spend` permission.
   - On tap, call purchase API as above.
   - If `200 OK`, show "Purchase Complete!" dialog.
   - If `202 Accepted`, show "Request sent for approval" dialog.

2. **Notifications**
   - Listen for WebSocket events for approval/denial.
   - On approval, show "Your purchase was approved!".
   - On denial, show reason.

### Admin Flow

1. **Admin Dashboard**
   - Show badge/notification for new purchase requests.
   - List pending requests (`GET /family/wallet/purchase-requests?status=PENDING`).

2. **Approve/Deny**
   - Approve: Call approve endpoint, UI updates on success.
   - Deny: Call deny endpoint, optionally provide a reason.

3. **Notifications**
   - Receive real-time updates via WebSocket when new requests are created.

---

## 4. Error Handling

- Show clear dialogs for:
  - Insufficient funds
  - Spending limit exceeded
  - No permission to spend
  - Not a family admin (should not happen in correct UI)
- Use error codes from API to map to user-friendly messages.

---

## 5. Real-Time Updates

- Connect to `wss://api.example.com/ws/{familyId}`.
- Listen for:
  - `purchase_request_created` (for admins)
  - `purchase_request_approved` (for requesters)
  - `purchase_request_denied` (for requesters)
- On event, refresh relevant providers/state.

---

## 6. Example Sequence Diagrams

### Direct Purchase (No Approval Needed)
```
User (Member/Admin) → POST /shop/purchase (use_family_wallet: true)
→ [Server checks permissions, balance]
→ 200 OK (purchase complete)
```

### Approval Workflow (Non-Admin)
```
Member → POST /shop/purchase (use_family_wallet: true)
→ 202 Accepted (pending approval)
→ Admin notified (WebSocket)
Admin → POST /family/wallet/purchase-requests/{id}/approve
→ 200 OK (approved)
→ Member notified (WebSocket)
```

---

## 7. Dart Code Patterns

- Use `dio` for HTTP, `riverpod` for state.
- See `familyShopApiServiceProvider` and `PurchaseRequestNotifier` for API and state management.
- UI: Show dialogs based on API response and error codes.

---

## 8. Notes on Using Existing Routes

### Core API Endpoints

- **Get payment options (personal + families):**
  - `GET /shop/payment-options`
  - Use to display all available payment sources, including family wallets with `can_spend` and `spending_limit`.

- **Initiate a purchase (family or personal):**
  - `POST /shop/purchase` (for shop items)
  - `POST /shop/avatars/buy`, `POST /shop/themes/buy`, etc. (for specific asset types)
  - For family payments, include `{ "payment_method": { "type": "family", "family_id": "..." } }` in the request body.

- **View purchase requests (admin/member):**
  - `GET /family/wallet/purchase-requests?status=PENDING`
  - Admins see all; members see their own.

- **Approve/Deny purchase requests (admin only):**
  - `POST /family/wallet/purchase-requests/{request_id}/approve`
  - `POST /family/wallet/purchase-requests/{request_id}/deny`

- **Get owned avatars (merged personal + family):**
  - `GET /avatars/owned`
  - Use to display all avatars/items available to the user, regardless of ownership source.

### Integration Tips

- Always require explicit family selection for family payments; do not auto-select.
- Use the `user_permissions.can_spend` and `spending_limit` fields to enable/disable family wallet options in the UI.
- After a successful purchase, always refresh `/avatars/owned` or the relevant owned-items endpoint.
- Handle errors using the `error_code` and `message` fields in API responses. For example, show a clear message if `FAMILY_SPENDING_DENIED` is returned.
- For real-time updates, connect to the WebSocket endpoint (`wss://api.example.com/ws/{familyId}`) and listen for purchase request events.
- For all family management (members, permissions, invitations, etc.), see the `/family` prefixed endpoints (see API summary docs for full list).

### Example: Family Purchase Request (JSON)

```json
{
  "avatar_id": "emotion_tracker-static-avatar-cat-1",
  "payment_method": { "type": "family", "family_id": "fam_111" }
}
```

### Example: Error Response (No Permission)

```json
{
  "status": "error",
  "detail": {
    "error": "FAMILY_SPENDING_DENIED",
    "message": "You don't have permission to spend from this family account"
  }
}
```

For more endpoint details, see `docs/shop_family_wallet_integration.md` and `docs/flutter_family_api.md`.

**For more details, see:**  
- `docs/shop_family_wallet_integration.md`  
- `docs/flutter_family_api.md`  
- Dart code examples in the integration guide.
