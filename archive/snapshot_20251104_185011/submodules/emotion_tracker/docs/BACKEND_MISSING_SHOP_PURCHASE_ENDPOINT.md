# Backend Issue: Missing POST /shop/purchase Endpoint

**Date:** October 25, 2025
**Reporter:** Mobile App Team
**Priority:** 🔴 CRITICAL
**Status:** Backend Endpoint Missing
**Affected Feature:** Family Shop Purchase Requests

---

## Executive Summary

The mobile app's family shop feature is **fully implemented** but purchase requests are failing because the backend is missing the `POST /shop/purchase` endpoint. Users cannot submit purchase requests for any shop items (avatars, banners, themes, bundles) in the family shop.

### Current Behavior
- Frontend makes `POST /shop/purchase` request
- Backend returns **404 Not Found** or **500 Internal Server Error**
- Error message: "Purchase failed: API Error (404): Not Found" or similar
- Affects both admin and non-admin users
- Purchase dialog shows error but no detailed server response

---

## Required Solution

Implement a new `POST /shop/purchase` endpoint that handles family shop purchase requests with approval workflow for non-admin users.

### Endpoint Specification

**Method:** `POST`  
**Path:** `/shop/purchase`  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 10 requests/minute per user

### Request Body Schema

```json
{
  "item_id": "string (required)",
  "item_type": "string (required)", // "avatar", "banner", "theme", "bundle"
  "quantity": "integer (required, min: 1)",
  "use_family_wallet": "boolean (required)",
  "family_id": "string (required)",
  "payment_source_id": "string (optional)", // Only when not using family wallet
  "reason": "string (optional, max: 500 chars)"
}
```

### Business Logic

1. **Validate User Permissions:**
   - User must be a member of the specified `family_id`
   - If `use_family_wallet = true`: Check user's spending permissions in family wallet

2. **Validate Item:**
   - Item must exist in shop catalog
   - Item must be available for purchase
   - Price must be > 0

3. **Payment Logic:**
   - If `use_family_wallet = true`:
     - Check family wallet balance
     - Check user's spending limit (if not admin)
     - If user is NOT admin: Create purchase request for approval
     - If user IS admin: Process purchase immediately
   - If `use_family_wallet = false`:
     - Validate `payment_source_id` exists and belongs to user
     - Process purchase immediately (personal payment)

4. **Approval Workflow:**
   - Non-admin purchases with family wallet → Create pending purchase request
   - Admin purchases with family wallet → Process immediately
   - Personal payments → Process immediately

### Response Schema

**Success Response (200 OK):**

For immediate purchases:
```json
{
  "status": "success",
  "message": "Purchase completed successfully",
  "purchase_id": "string",
  "item_id": "string",
  "item_type": "string",
  "quantity": 1,
  "total_cost": 100,
  "payment_method": "family_wallet|personal"
}
```

For pending requests:
```json
{
  "status": "pending",
  "message": "Purchase request submitted for admin approval",
  "request_id": "string",
  "item_id": "string",
  "item_type": "string",
  "quantity": 1,
  "total_cost": 100
}
```

**Error Responses:**

| Status | Error Code | Description |
|--------|------------|-------------|
| 400 | INVALID_REQUEST | Missing required fields or invalid data |
| 400 | INSUFFICIENT_BALANCE | Family wallet doesn't have enough funds |
| 400 | SPENDING_LIMIT_EXCEEDED | User exceeded their spending limit |
| 403 | NOT_FAMILY_MEMBER | User is not a member of the family |
| 403 | CANNOT_SPEND | User doesn't have spending permissions |
| 403 | ITEM_NOT_AVAILABLE | Item is not available for purchase |
| 404 | ITEM_NOT_FOUND | Item doesn't exist |
| 404 | FAMILY_NOT_FOUND | Family doesn't exist |
| 429 | RATE_LIMIT_EXCEEDED | Too many purchase requests |
| 500 | INTERNAL_ERROR | Server error |

Error response format:
```json
{
  "error": "ERROR_CODE",
  "message": "Human readable error message",
  "details": {
    "field": "specific_field_name",
    "value": "provided_value"
  }
}
```

---

## Database Schema Requirements

### Purchase Requests Table

```sql
CREATE TABLE family_purchase_requests (
  request_id VARCHAR PRIMARY KEY,
  family_id VARCHAR NOT NULL,
  user_id VARCHAR NOT NULL,
  item_id VARCHAR NOT NULL,
  item_type VARCHAR NOT NULL,
  quantity INTEGER NOT NULL,
  total_cost INTEGER NOT NULL,
  payment_method VARCHAR NOT NULL, -- 'family_wallet', 'personal'
  payment_source_id VARCHAR,
  reason TEXT,
  status VARCHAR NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'denied', 'completed'
  approved_by VARCHAR,
  approved_at TIMESTAMP,
  denied_by VARCHAR,
  denied_at TIMESTAMP,
  denied_reason TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  FOREIGN KEY (family_id) REFERENCES families(family_id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (approved_by) REFERENCES users(user_id),
  FOREIGN KEY (denied_by) REFERENCES users(user_id)
);

-- Indexes
CREATE INDEX idx_purchase_requests_family ON family_purchase_requests(family_id);
CREATE INDEX idx_purchase_requests_user ON family_purchase_requests(user_id);
CREATE INDEX idx_purchase_requests_status ON family_purchase_requests(status);
```

### Purchase History Table

```sql
CREATE TABLE family_purchase_history (
  purchase_id VARCHAR PRIMARY KEY,
  family_id VARCHAR NOT NULL,
  user_id VARCHAR NOT NULL,
  item_id VARCHAR NOT NULL,
  item_type VARCHAR NOT NULL,
  quantity INTEGER NOT NULL,
  total_cost INTEGER NOT NULL,
  payment_method VARCHAR NOT NULL,
  payment_source_id VARCHAR,
  request_id VARCHAR, -- Links to purchase_requests if approved
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  FOREIGN KEY (family_id) REFERENCES families(family_id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (request_id) REFERENCES family_purchase_requests(request_id)
);
```

---

## Implementation Steps

### 1. Create Database Tables
- Add `family_purchase_requests` table
- Add `family_purchase_history` table
- Add necessary indexes and foreign keys

### 2. Implement POST /shop/purchase Endpoint

**Validation Logic:**
```python
def validate_purchase_request(request, user):
    # Check user is family member
    if not is_family_member(request.family_id, user.id):
        raise HTTPException(403, {"error": "NOT_FAMILY_MEMBER"})

    # Check item exists and is available
    item = get_shop_item(request.item_id, request.item_type)
    if not item or not item.available:
        raise HTTPException(404, {"error": "ITEM_NOT_FOUND"})

    # Calculate total cost
    total_cost = item.price * request.quantity

    # Payment validation
    if request.use_family_wallet:
        wallet = get_family_wallet(request.family_id)
        permissions = get_user_spending_permissions(request.family_id, user.id)

        if not permissions.can_spend:
            raise HTTPException(403, {"error": "CANNOT_SPEND"})

        if permissions.spending_limit != -1 and total_cost > permissions.spending_limit:
            raise HTTPException(400, {"error": "SPENDING_LIMIT_EXCEEDED"})

        if wallet.balance < total_cost:
            raise HTTPException(400, {"error": "INSUFFICIENT_BALANCE"})

        # Check if admin approval required
        is_admin = is_family_admin(request.family_id, user.id)
        if not is_admin:
            # Create purchase request
            return create_purchase_request(request, user, total_cost)
        else:
            # Process immediately
            return process_immediate_purchase(request, user, total_cost)
    else:
        # Personal payment - validate payment source
        if not request.payment_source_id:
            raise HTTPException(400, {"error": "INVALID_REQUEST", "message": "payment_source_id required for personal payments"})

        payment_source = get_user_payment_source(user.id, request.payment_source_id)
        if not payment_source:
            raise HTTPException(400, {"error": "INVALID_REQUEST", "message": "Invalid payment source"})

        # Process personal purchase
        return process_personal_purchase(request, user, total_cost)
```

### 3. Implement Approval Endpoints

**POST /family/wallet/purchase-requests/{requestId}/approve**
- Only family admins can approve
- Update request status to 'approved'
- Process the purchase
- Create purchase history record

**POST /family/wallet/purchase-requests/{requestId}/deny**
- Only family admins can deny
- Update request status to 'denied'
- Optional denial reason

### 4. Implement Query Endpoints

**GET /family/wallet/purchase-requests?family_id={familyId}**
- Return pending purchase requests for the family
- Only family members can view

**GET /family/{familyId}/shop/purchase-history**
- Return completed purchases for the family
- Include both approved requests and immediate purchases

---

## Testing Checklist

### Functional Tests

- [ ] Admin can purchase immediately with family wallet
- [ ] Non-admin purchase creates pending request
- [ ] Personal payment works for both admin and non-admin
- [ ] Insufficient balance returns proper error
- [ ] Spending limit exceeded returns proper error
- [ ] Invalid item returns 404
- [ ] Non-family member cannot purchase
- [ ] User without spending permissions cannot purchase

### Approval Workflow Tests

- [ ] Admin can approve pending requests
- [ ] Admin can deny pending requests
- [ ] Non-admin cannot approve/deny requests
- [ ] Approved requests are processed and added to history
- [ ] Denied requests remain in denied status

### Edge Cases

- [ ] Quantity validation (min 1, reasonable max)
- [ ] Reason field length validation
- [ ] Concurrent purchases don't cause race conditions
- [ ] Purchase request expiry (if implemented)
- [ ] Rate limiting works correctly

---

## Security Considerations

1. **Authorization:**
   - Only family members can make purchases
   - Only family admins can approve/deny requests
   - Users can only use their own payment sources

2. **Data Validation:**
   - All monetary values are integers (smallest currency unit)
   - Item IDs are validated against catalog
   - Family membership is verified

3. **Audit Trail:**
   - All purchases are logged in history table
   - Approval/denial actions are tracked
   - Timestamps for all state changes

---

## Performance Considerations

1. **Database Indexes:**
   - Index on `family_id`, `user_id`, `status` for purchase requests
   - Index on `family_id`, `created_at` for purchase history

2. **Caching:**
   - Cache shop item catalog
   - Cache user permissions during purchase flow

3. **Rate Limiting:**
   - 10 purchase requests per minute per user
   - Separate limit for approval actions

---

## Integration with Existing Systems

1. **Family Wallet System:**
   - Deduct from family balance on approved purchases
   - Check spending permissions and limits

2. **Notification System:**
   - Notify admins when new purchase requests are created
   - Notify users when requests are approved/denied

3. **Shop Catalog:**
   - Use existing shop item definitions
   - Validate item availability and pricing

---

## Example Implementation (Python/FastAPI)

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class PurchaseRequest(BaseModel):
    item_id: str
    item_type: str
    quantity: int
    use_family_wallet: bool
    family_id: str
    payment_source_id: Optional[str] = None
    reason: Optional[str] = None

@router.post("/shop/purchase")
async def purchase_item(request: PurchaseRequest, current_user = Depends(get_current_user)):
    try:
        # Validate request
        validation_result = await validate_purchase_request(request, current_user)

        if validation_result["requires_approval"]:
            # Create purchase request
            purchase_request = await create_purchase_request(request, current_user)
            return {
                "status": "pending",
                "message": "Purchase request submitted for admin approval",
                "request_id": purchase_request.id
            }
        else:
            # Process immediate purchase
            purchase = await process_purchase(request, current_user)
            return {
                "status": "success",
                "message": "Purchase completed successfully",
                "purchase_id": purchase.id
            }

    except ValidationError as e:
        raise HTTPException(400, {"error": "INVALID_REQUEST", "message": str(e)})
    except InsufficientFundsError:
        raise HTTPException(400, {"error": "INSUFFICIENT_BALANCE"})
    except PermissionDeniedError:
        raise HTTPException(403, {"error": "CANNOT_SPEND"})
```

---

## Current Workaround

The mobile app shows error messages but cannot complete purchases:

```
Purchase failed: API Error (404): Not Found
```

Users see this error when trying to buy any item in the family shop.

---

## Impact

**CRITICAL** - Core family shop functionality is completely broken:
- No purchases can be completed
- Family shop appears non-functional
- Users cannot access shop items
- Feature is deployed but unusable

### Timeline Needed

- Database schema: 30 minutes
- Endpoint implementation: 2-3 hours
- Testing: 1 hour
- **Total: 4-5 hours**

---

## Contact

**Mobile Team:** GitHub Copilot  
**Backend API:** dev-app-sbd.rohanbatra.in  
**Environment:** Development  
**Date Reported:** October 25, 2025

---

**Status:** 🔴 Awaiting Backend Implementation

---

## Related Endpoints (Already Working)

✅ `GET /shop/payment-options` - Returns available payment methods  
✅ `GET /avatars/owned` - Returns user's owned items  
✅ `GET /family/{familyId}/sbd-account` - Returns family wallet info  
✅ `GET /family/wallet/purchase-requests` - Lists pending requests  
✅ `POST /family/wallet/purchase-requests/{id}/approve` - Approves requests  
✅ `POST /family/wallet/purchase-requests/{id}/deny` - Denies requests

❌ `POST /shop/purchase` - **MISSING - NEEDS IMPLEMENTATION**

---

**End of Backend Requirement**</content>
<parameter name="filePath">/Users/rohan/Documents/repos/emotion_tracker/docs/BACKEND_MISSING_SHOP_PURCHASE_ENDPOINT.md