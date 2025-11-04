# Family Shop API Contracts

## 1. Get Payment Options
- **Endpoint:** `GET /shop/payment-options`
- **Response:**
```json
[
  {
    "source_id": "string",
    "type": "personal|family",
    "can_spend": true,
    "spending_limit": 1000.0,
    "family_id": "string?",
    "label": "Family Wallet"
  }
]
```

## 2. Initiate a Purchase
- **Endpoint:** `POST /shop/purchase`
- **Body:**
```json
{
  "item_id": "string",
  "quantity": 1,
  "use_family_wallet": true,
  "family_id": "string"
}
```
- **Responses:**
  - `200 OK`: `{ "status": "success", ... }`
  - `202 Accepted`: `{ "status": "pending", "request_id": "..." }`
  - `400/403/404/500`: `{ "detail": "...", "error_code": "..." }`

## 3. List Purchase Requests
- **Endpoint:** `GET /family/wallet/purchase-requests`
- **Query:** `family_id`, `status`, `requester_id`, `limit`, `offset`
- **Response:** Array of PurchaseRequest objects (see models).

## 4. Approve/Deny Purchase Request
- **Endpoint:**
  - `POST /family/wallet/purchase-requests/{request_id}/approve`
  - `POST /family/wallet/purchase-requests/{request_id}/deny`
- **Body (deny):** `{ "reason": "..." }`
- **Response:** Updated PurchaseRequest object.

## 5. Get Owned Avatars/Items
- **Endpoint:** `GET /avatars/owned`
- **Response:** Array of item objects.

## 6. WebSocket Events
- **Endpoint:** `wss://api.example.com/ws/{familyId}`
- **Events:**
  - `purchase_request_created`
  - `purchase_request_approved`
  - `purchase_request_denied`
- **Payload:** See models.
