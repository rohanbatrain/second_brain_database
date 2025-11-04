# Complete Family Wallet & Shop Integration Guide (Flutter)

**Date:** 2025-10-23
**Status:** Production Implementation Guide

---

## 1. Overview

This document provides a comprehensive, end-to-end guide for the Flutter team to implement a family shop with shared wallet support, including purchasing items and transferring tokens between family and personal wallets. It covers all user and admin flows, API contracts, error handling, real-time updates, and integration patterns. Use this as the single source of truth for production.

---

## 2. User Stories

- **As a family member:**
  - I want to purchase items from the shop using our shared family wallet.
  - If my purchase requires approval, I want to be notified when it is approved or denied.
  - I want to request tokens from the family wallet to my personal wallet.
- **As a family admin:**
  - I want to be notified when a family member requests a purchase or token transfer.
  - I want to approve or deny purchase requests and token transfer requests to control family spending.
  - I want to manage spending permissions and freeze/unfreeze the family account.

---

## 3. API Endpoints

### 3.1. Shop & Purchase Endpoints

- **GET /shop/payment-options:** Returns all available payment sources (personal, family wallets) with `can_spend` and `spending_limit`.
- **POST /shop/purchase:** Initiate a purchase (general shop items).
- **POST /shop/avatars/buy:** Buy an avatar.
- **POST /shop/themes/buy:** Buy a theme.
- **POST /shop/banners/buy:** Buy a banner.
- **POST /shop/bundles/buy:** Buy a bundle.
- **GET /avatars/owned:** Get owned avatars/items (merged personal + family).

### 3.2. Family Wallet Endpoints

- **GET /family/{family_id}/sbd-account:** Get family account info, balance, permissions.
- **PUT /family/{family_id}/sbd-account/permissions:** Update member spending permissions (admin only).
- **POST /family/{family_id}/sbd-account/freeze:** Freeze/unfreeze account (admin only).
- **GET /family/{family_id}/sbd-account/transactions:** Get transaction history.
- **POST /family/{family_id}/sbd-account/validate-spending:** Validate if a spending amount is allowed.

### 3.3. Purchase Requests (Shop)

- **GET /family/wallet/purchase-requests:** List purchase requests (query params: family_id, status, requester_id, limit, offset).
- **POST /family/wallet/purchase-requests/{request_id}/approve:** Approve a purchase request (admin only).
- **POST /family/wallet/purchase-requests/{request_id}/deny:** Deny a purchase request (admin only, body: `{ "reason": "..." }`).

### 3.4. Token Transfer Requests (Family to Personal)

- **POST /family/{family_id}/token-requests:** Create a token transfer request (member requests tokens from family to personal).
- **GET /family/{family_id}/token-requests/my-requests:** Get my token requests (member).
- **POST /family/{family_id}/token-requests/{request_id}/review:** Review a token request (admin: approve/deny).

---

## 4. Data Models

### 4.1. PurchaseRequest (Shop)
```json
{
  "request_id": "string",
  "family_id": "string",
  "requester": { "user_id": "string", "username": "string" },
  "item": { "item_id": "string", "name": "string", "item_type": "string", "image_url": "string?" },
  "cost": number,
  "status": "pending|approved|denied",
  "created_at": "ISO8601 timestamp",
  "reviewed_by": { "user_id": "string", "username": "string" }?,
  "reviewed_at": "ISO8601 timestamp"?,
  "denial_reason": "string?",
  "transaction_id": "string?"
}
```

### 4.2. Family SBD Account
```json
{
  "account_username": "string",
  "balance": number,
  "is_frozen": boolean,
  "spending_permissions": {
    "[user_id]": {
      "role": "string",
      "spending_limit": number,
      "can_spend": boolean,
      "updated_at": "string"
    }
  },
  "recent_transactions": [Transaction]
}
```

### 4.3. Token Request
```json
{
  "request_id": "string",
  "requester": { "user_id": "string", "username": "string" },
  "amount": number,
  "status": "pending|approved|denied",
  "created_at": "ISO8601 timestamp",
  "reviewed_by": { "user_id": "string", "username": "string" }?,
  "reviewed_at": "ISO8601 timestamp"?,
  "denial_reason": "string?"
}
```

---

## 5. User Flows

### 5.1. Shop Purchase (Normal User)

1. **Shop Item Screen:** Show "Pay with Family Wallet" button if `can_spend` is true.
2. **Initiate Purchase:** Call `/shop/purchase` (or specific buy endpoint) with `payment_method: { "type": "family", "family_id": "..." }`.
3. **Handle Response:**
   - `200 OK`: Purchase completed immediately.
   - `202 Accepted`: Purchase request created (pending admin approval). Show info dialog: "Request sent for approval".
4. **Notifications:** Listen for WebSocket events (`purchase_request_approved`, `purchase_request_denied`).
5. **Owned Items:** Refresh `/avatars/owned` after purchase or approval.

### 5.2. Token Transfer from Family to Personal (Normal User)

1. **Request Tokens:** Call `POST /family/{family_id}/token-requests` with `amount`, `recipient_user_id` (your own), `note`.
2. **Check Status:** Call `GET /family/{family_id}/token-requests/my-requests` to see status.
3. **Notifications:** Listen for WebSocket events for approval/denial.
4. **On Approval:** Tokens are transferred to your personal wallet.

### 5.3. Shop Purchase (Admin)

- Same as normal user, but purchases may auto-approve if admin has unlimited spending.

### 5.4. Token Transfer from Family to Personal (Admin)

- Admins can directly transfer tokens without request/approval, or use the request flow for audit.
- For direct transfer: Use SBD token system endpoints if available, or create a direct transfer endpoint.

---

## 6. Admin Flows

### 6.1. Manage Purchase Requests

1. **Dashboard:** Show badge/notification for new purchase requests.
2. **List Requests:** Call `GET /family/wallet/purchase-requests?status=pending`.
3. **Approve/Deny:** Call approve/deny endpoints.
4. **Notifications:** Receive real-time updates via WebSocket (`purchase_request_created`, `purchase_request_updated`).

### 6.2. Manage Token Transfer Requests

1. **List Requests:** Call `GET /family/{family_id}/token-requests` (admin view).
2. **Review:** Call `POST /family/{family_id}/token-requests/{request_id}/review` with `action: "approve"` or `"deny"`.
3. **On Approval:** Tokens are transferred from family to personal wallet.

### 6.3. Manage Family Wallet

- **Update Permissions:** `PUT /family/{family_id}/sbd-account/permissions`.
- **Freeze Account:** `POST /family/{family_id}/sbd-account/freeze`.
- **View Transactions:** `GET /family/{family_id}/sbd-account/transactions`.

---

## 7. Real-Time Updates

- **WebSocket Endpoint:** `wss://api.example.com/ws/{familyId}`
- **Events:**
  - `purchase_request_created`, `purchase_request_approved`, `purchase_request_denied`
  - `token_request_created`, `token_request_approved`, `token_request_denied`
- **Fallback:** Poll relevant endpoints if WebSocket not available.

---

## 8. Error Handling

- **400:** Invalid input, insufficient funds (`detail` string, error code).
- **403:** Permission denied (e.g., `FAMILY_SPENDING_DENIED`).
- **404:** Not found.
- **500:** Server error.
- Map all error codes to user-friendly messages.

---

## 9. Integration Tips

- Always require explicit family selection for family payments/transfers.
- Use `user_permissions.can_spend` and `spending_limit` to enable/disable options.
- After successful actions, refresh relevant endpoints (e.g., `/avatars/owned`, `/family/{family_id}/sbd-account`).
- For family management, use `/family` endpoints.
- See `docs/shop_family_wallet_integration.md` and `docs/flutter_family_api.md` for more details.

---

## 10. Example Sequence Diagrams

### 10.1. Shop Purchase (Approval Workflow)
```
Member → POST /shop/purchase (family wallet)
→ 202 Accepted (pending approval)
→ Admin notified (WebSocket)
Admin → POST /family/wallet/purchase-requests/{id}/approve
→ 200 OK (approved)
→ Member notified (WebSocket)
```

### 10.2. Token Transfer (Normal User to Admin)
```
Member → POST /family/{family_id}/token-requests (amount, recipient)
→ Request created
→ Admin notified
Admin → POST /family/{family_id}/token-requests/{id}/review (approve)
→ Tokens transferred
→ Member notified
```

### 10.3. Token Transfer (Admin Direct)
```
Admin → [Direct transfer endpoint or SBD send]
→ Tokens transferred immediately
```

---

## 11. Dart Code Patterns

- Use `dio` for HTTP, `riverpod` for state management.
- See `familyShopApiServiceProvider` and `PurchaseRequestNotifier` for API and state management.
- UI: Show dialogs based on API response and error codes.

---

## 12. Staging & QA

- Provide staging baseURL and API token with admin/member roles.
- Provide sample `family_id`, `user_id` pairs and sample request entries.
- Optionally provide a sandbox endpoint that auto-approves for end-to-end QA.

---

## 13. References

- `docs/shop_family_wallet_integration.md`
- `docs/flutter_family_api.md`
- `docs/family_sbd_wallet_api_quick_reference.md`
- Dart code examples in the integration guide

---

**For questions or to request endpoint changes, see the API docs or contact the backend team.**
