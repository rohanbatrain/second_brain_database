# Family Shop Data Models

## PurchaseRequest
```json
{
  "request_id": "string",
  "family_id": "string",
  "requester": { "user_id": "string", "username": "string" },
  "item": { "item_id": "string", "name": "string", "item_type": "string", "image_url": "string?" },
  "cost": 100.0,
  "status": "pending|approved|denied",
  "created_at": "ISO8601 timestamp",
  "reviewed_by": { "user_id": "string", "username": "string" }?,
  "reviewed_at": "ISO8601 timestamp"?,
  "denial_reason": "string?",
  "transaction_id": "string?"
}
```

## PaymentOption
```json
{
  "source_id": "string",
  "type": "personal|family",
  "can_spend": true,
  "spending_limit": 1000.0,
  "family_id": "string?",
  "label": "Family Wallet"
}
```

## WebSocket Event Payloads
- `purchase_request_created`, `purchase_request_approved`, `purchase_request_denied` all include a `PurchaseRequest` object.
