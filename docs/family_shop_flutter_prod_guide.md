# Production-Ready Guide: Family Shop & Wallet Integration (Flutter)

**Date:** 2025-10-23
**Status:** Production Implementation Guide

---

## 1. Overview

This document provides a comprehensive, end-to-end guide for the Flutter team to implement a family shop with shared wallet support. It covers all user and admin flows, API contracts, error handling, real-time updates, and integration patterns. Use this as the single source of truth for production.

---

## 2. User Stories

- **As a family member:**
  - I want to purchase items from the shop using our shared family wallet.
  - If my purchase requires approval, I want to be notified when it is approved or denied.
- **As a family admin:**
  - I want to be notified when a family member requests a purchase.
  - I want to approve or deny purchase requests and control family spending.

---

## 3. API Endpoints

### 3.1. Get Payment Options
- **GET /shop/payment-options**
- Returns all available payment sources (personal, family wallets) with `can_spend` and `spending_limit`.

### 3.2. Initiate a Purchase
- **POST /shop/purchase**
- Body:
  ```json
  {
    "item_id": "<item_id>",
    "quantity": 1,
    "use_family_wallet": true,
    "family_id": "<family_id>" // required for family payments
  }
  ```
- Responses:
  - `200 OK`: Purchase completed immediately.
  - `202 Accepted`: Purchase request created (pending admin approval).
  - `400/403`: Error with detail string and error code.

### 3.3. List Purchase Requests
- **GET /family/wallet/purchase-requests**
- Query params: `family_id`, `status`, `requester_id`, `limit`, `offset`
- Returns array of PurchaseRequest objects.

### 3.4. Approve/Deny Purchase Request (Admin Only)
- **POST /family/wallet/purchase-requests/{request_id}/approve**
- **POST /family/wallet/purchase-requests/{request_id}/deny** (body: `{ "reason": "..." }`)
- Returns updated PurchaseRequest with status, transaction_id, reviewed_by, reviewed_at, denial_reason.

### 3.5. Get Owned Avatars/Items
- **GET /avatars/owned**
- Returns all avatars/items available to the user (personal + family).

---

## 4. Data Models

### 4.1. PurchaseRequest
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

---

## 5. User Flow (Non-Admin)

1. **Shop Item Screen**
   - Show "Pay with Family Wallet" button if `can_spend` is true.
   - On tap, call `/shop/purchase` with `use_family_wallet: true` and `family_id`.
   - If `200 OK`, show success dialog.
   - If `202 Accepted`, show info dialog: "Request sent for approval".
2. **Notifications**
   - Listen for WebSocket events (`purchase_request_approved`, `purchase_request_denied`).
   - On approval, show "Your purchase was approved!".
   - On denial, show reason.
3. **Owned Items**
   - Refresh `/avatars/owned` after purchase or approval.

---

## 6. Admin Flow

1. **Admin Dashboard**
   - Show badge/notification for new purchase requests.
   - List pending requests (`GET /family/wallet/purchase-requests?status=pending`).
2. **Approve/Deny**
   - Approve: Call approve endpoint, UI updates on success.
   - Deny: Call deny endpoint, optionally provide a reason.
3. **Notifications**
   - Receive real-time updates via WebSocket (`purchase_request_created`, `purchase_request_updated`).

---

## 7. Real-Time Updates

- **WebSocket Endpoint:** `wss://api.example.com/ws/{familyId}`
- **Events:**
  - `purchase_request_created`: New request submitted (for admins)
  - `purchase_request_approved`: Request approved (for requester)
  - `purchase_request_denied`: Request denied (for requester)
- **Fallback:** If WebSocket not available, poll `/family/wallet/purchase-requests`.

---

## 8. Error Handling

- **400:** Invalid input, insufficient funds, etc. (`detail` string, error code)
- **403:** Permission denied (e.g., `FAMILY_SPENDING_DENIED`)
- **404:** Not found
- **500:** Server error
- Map all error codes to user-friendly messages in the UI.

---

## 9. Integration Tips

- Always require explicit family selection for family payments.
- Use `user_permissions.can_spend` and `spending_limit` to enable/disable wallet options.
- After a successful purchase or approval, always refresh `/avatars/owned`.
- For all family management (members, permissions, invitations), use `/family` endpoints.
- See `docs/shop_family_wallet_integration.md` and `docs/flutter_family_api.md` for more details and Dart code examples.

---

## 10. Example Sequence Diagrams

### 10.1. Direct Purchase (No Approval Needed)
```
User (Member/Admin) → POST /shop/purchase (use_family_wallet: true)
→ [Server checks permissions, balance]
→ 200 OK (purchase complete)
```

### 10.2. Approval Workflow (Non-Admin)
```
Member → POST /shop/purchase (use_family_wallet: true)
→ 202 Accepted (pending approval)
→ Admin notified (WebSocket)
Admin → POST /family/wallet/purchase-requests/{id}/approve
→ 200 OK (approved)
→ Member notified (WebSocket)
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
- Dart code examples in the integration guide

---

**For questions or to request endpoint changes, see the API docs or contact the backend team.**
