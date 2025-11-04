# Family Shop WebSocket & Real-Time Updates

## WebSocket Endpoint
- `wss://api.example.com/ws/{familyId}`

## Events
- `purchase_request_created`: New request submitted (for admins)
- `purchase_request_approved`: Request approved (for requester)
- `purchase_request_denied`: Request denied (for requester)

## Event Payloads
- All events include a `PurchaseRequest` object (see data models)

## Fallback
- If WebSocket unavailable, poll `/family/wallet/purchase-requests` every N seconds

## Event Handling
- WebSocketManager provider dispatches events to PurchaseRequestNotifier
- UI updates in real time
