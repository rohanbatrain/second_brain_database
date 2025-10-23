# Backend Implementation Status for Family Purchase Requests (Flutter Integration)

## 1. What is Missing in Backend (To Be Implemented)

- **/shop/purchase**
  - Ensure full support for family wallet purchases.
  - Must return 202 Accepted with a full PurchaseRequest object if approval is required (non-admin or over limit).
  - Must return 200 OK for direct purchases (admin or within limit).
  - Response payloads must match frontend contract.

- **/family/wallet/purchase-requests**
  - Support all required query params: family_id, status, requester_id, limit, offset.
  - Return array of PurchaseRequest objects as per frontend model.

- **/family/wallet/purchase-requests/{request_id}/approve**
  - POST endpoint for admin approval.
  - Returns updated PurchaseRequest with status, transaction_id, reviewed_by, reviewed_at.

- **/family/wallet/purchase-requests/{request_id}/deny**
  - POST endpoint for admin denial.
  - Accepts optional reason.
  - Returns updated PurchaseRequest with status, denial_reason, reviewed_by, reviewed_at.

- **WebSocket Events**
  - Emit `purchase_request_created` and `purchase_request_updated` events to relevant clients (admin, requester) on create/approve/deny.
  - If not possible, document polling fallback for frontend.

- **Error Codes and Payloads**
  - Ensure all error responses (400, 403, 404, 500) use clear `detail` strings and error codes as expected by frontend.
  - Map backend errors to frontend contract (e.g., FAMILY_SPENDING_DENIED).

## 2. What is Already Implemented (Ready for Flutter Team)

- **/shop/purchase**
  - Supports both personal and family wallet purchases.
  - Returns 200 OK for direct purchases.
  - Returns 202 Accepted and creates a purchase request if approval is required (in most flows).
  - Error handling for insufficient funds and permission errors is present.

- **/family/wallet/purchase-requests**
  - GET endpoint exists and returns purchase requests for a family.
  - Admins see all requests; members see their own.
  - Status filtering is supported (status param).

- **/family/wallet/purchase-requests/{request_id}/approve**
  - POST endpoint exists for admin approval.
  - Updates status, transaction_id, reviewed_by, reviewed_at.

- **/family/wallet/purchase-requests/{request_id}/deny**
  - POST endpoint exists for admin denial.
  - Accepts optional reason and updates status, denial_reason, reviewed_by, reviewed_at.

- **PurchaseRequest Model**
  - Model matches frontend requirements (request_id, family_id, requester, item, cost, status, created_at, reviewed_by, reviewed_at, denial_reason, transaction_id).

- **Error Handling**
  - Most endpoints return structured error codes and messages (e.g., FAMILY_SPENDING_DENIED).
  - 400/403/404/500 codes are mapped to user-friendly messages.

- **Docs and Integration Guides**
  - See `docs/shop_family_wallet_integration.md` and `docs/flutter_family_api.md` for API contracts, payloads, and Dart code examples.

## 3. Caveats and Next Steps

- **WebSocket Events:**
  - If not yet live, implement or document polling fallback for real-time updates.
- **Query Params:**
  - Ensure all required query params (family_id, requester_id, limit, offset) are supported on GET /family/wallet/purchase-requests.
- **Testing:**
  - Provide staging credentials, sample family_id/user_id, and test data for QA.
- **Error Codes:**
  - Double-check all error payloads match frontend mapping.

---

**For questions or to request endpoint changes, see the API docs or contact the backend team.**
