# Family Shop Providers & State Management

## Riverpod Providers/Notifiers

### 1. FamilyShopApiServiceProvider
- Handles all API calls (payment options, purchase, requests, approval/denial, owned items)
- Uses `dio` for HTTP
- Exposes methods:
  - `getPaymentOptions()`
  - `purchaseItem(...)`
  - `listPurchaseRequests(...)`
  - `approvePurchaseRequest(...)`
  - `denyPurchaseRequest(...)`
  - `getOwnedItems()`

### 2. PurchaseRequestNotifier
- Holds list of purchase requests, status, error
- Methods:
  - `fetchRequests()`
  - `approveRequest(id)`
  - `denyRequest(id, reason)`
  - Handles real-time updates (WebSocket/polling)

### 3. FamilyWalletProvider
- Tracks wallet state, permissions, spending limit
- Exposes wallet info for UI

### 4. WebSocketManager
- Connects to family WebSocket endpoint
- Dispatches events to notifiers

## Error Handling
- Centralized error code mapping utility
- All providers surface user-friendly error messages
