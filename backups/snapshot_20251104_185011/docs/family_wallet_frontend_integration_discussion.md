# Family SBD Wallet Backend - Frontend Integration Discussion

**Date:** October 22, 2025  
**Status:** Discussion Document - Frontend Team Review Required  
**Purpose:** Clarify implementation gaps and requirements before final API contract

---

## 🎯 **Current Status Summary**

### ✅ **Implemented (8/12 endpoints)**
- `GET /families/{familyId}/sbd-account` ✅
- `GET /families/{familyId}/sbd-account/transactions` ✅  
- `POST /families/{familyId}/token-requests` ✅
- `GET /families/{familyId}/token-requests/pending` ✅
- `POST /families/{familyId}/token-requests/{requestId}/review` ✅
- `PUT /families/{familyId}/members/{memberId}/permissions` ✅
- `POST /families/{familyId}/sbd-account/freeze` ✅
- `POST /families/{familyId}/sbd-account/emergency-unfreeze` ✅

### ❌ **Missing (4/12 endpoints)**
- `POST /families/{familyId}/sbd-account/transfer` ❌
- `POST /families/{familyId}/sbd-account/topup` ❌
- `GET /families/{familyId}/members/{memberId}/available` ❌
- **Webhook management & delivery endpoints** ❌

### ⚠️ **Implementation Gaps**
- **Idempotency keys** - No X-Idempotency-Key header support
- **Webhook system** - No event emission or delivery
- **Daily/weekly limits** - Only per-transaction limits exist
- **Multi-admin approvals** - Not implemented

---

## 🔑 **Critical Questions for Frontend Team**

### 1. **Idempotency Key Implementation**
**Current Status:** Not implemented  
**Frontend Requirement:** X-Idempotency-Key header for transfer/topup/approve endpoints  
**Questions:**
- Should we implement full idempotency with database storage?
- What should be the key format (UUID, hash, etc.)?
- How long should idempotency keys be stored?
- What constitutes a duplicate request (same key + same payload)?

### 2. **Webhook System Architecture**
**Current Status:** No webhook system exists  
**Frontend Expectation:** Events for transaction.created, balance.updated, request.created/reviewed, account.frozen/unfrozen  
**Questions:**
- What webhook events are absolutely required vs nice-to-have?
- Should webhooks be configurable per family?
- What retry policy should we implement (exponential backoff, max retries)?
- How should webhook failures be handled (alerts, logging)?
- Should we implement webhook signing (HMAC) as specified?

### 3. **Transfer Endpoint Design**
**Current Status:** Transfers use general `/sbd_tokens/send` endpoint  
**Frontend Spec:** `POST /families/{familyId}/sbd-account/transfer`  
**Questions:**
- Should we create family-specific transfer endpoints, or can frontend use existing SBD send?
- If family-specific, what additional validation is needed?
- How should transfer responses differ from general SBD transfers?
- Should family transfers include additional metadata?

### 4. **Topup Endpoint Implementation**
**Current Status:** Not implemented  
**Frontend Spec:** `POST /families/{familyId}/sbd-account/topup`  
**Questions:**
- How should topups work? External payment integration?
- Who can initiate topups (any family member, admins only)?
- Should topups bypass freeze restrictions (as mentioned in spec)?
- What payment methods should be supported?

### 5. **Available Balance Endpoint**
**Current Status:** Not implemented  
**Frontend Spec:** `GET /families/{familyId}/members/{memberId}/available`  
**Questions:**
- Is this endpoint required, or can frontend calculate available balance from permissions + account balance?
- What should "available" include (remaining daily limit, account balance, etc.)?
- Should this consider pending token requests?

### 6. **Time-Based Spending Limits**
**Current Status:** Only per-transaction limits (-1 for unlimited, or fixed amount)  
**Questions:**
- Do we need daily/weekly spending limits in addition to per-transaction?
- How should time-based limits reset (calendar day, rolling 24h)?
- Should limits be configurable per member?

### 7. **Multi-Admin Approval Workflow**
**Current Status:** Not implemented  
**Questions:**
- Should large transactions require multiple admin approvals?
- What threshold triggers multi-admin approval?
- How should the approval workflow work (sequential, parallel)?

### 8. **Error Response Standardization**
**Current Implementation:** Structured error responses with codes  
**Questions:**
- Does current error format match frontend expectations?
- Should we standardize error codes across all endpoints?
- What HTTP status codes should be used for business logic errors?

### 9. **Rate Limiting Specifications**
**Current Implementation:** Basic rate limiting exists  
**Questions:**
- What are acceptable rate limits for each endpoint type?
- Should family endpoints have different limits than general endpoints?
- How should rate limit errors be communicated?

### 10. **Notification System Details**
**Current Implementation:** Basic notification system exists  
**Questions:**
- What notification types are sent for family actions?
- Should notifications be real-time (WebSocket) or polled?
- Can users configure notification preferences per family?

---

## 📋 **Proposed Implementation Plan**

### **Phase 1: Critical Missing Features (Week 1-2)**
1. **Idempotency Keys** - Implement basic idempotency for transfer/topup operations
2. **Family Transfer Endpoint** - Create `POST /families/{id}/sbd-account/transfer`
3. **Topup Endpoint** - Basic implementation with external payment integration
4. **Available Balance Endpoint** - Simple calculation endpoint

### **Phase 2: Advanced Features (Week 3-4)**
1. **Webhook System** - Basic event emission for critical events
2. **Time-Based Limits** - Daily/weekly spending caps
3. **Multi-Admin Approvals** - Approval workflow for large transactions

### **Phase 3: Polish & Integration (Week 5-6)**
1. **Webhook Enhancements** - Retry logic, HMAC signing, management endpoints
2. **Rate Limiting Optimization** - Fine-tune limits based on usage patterns
3. **Error Response Standardization** - Consistent error handling across all endpoints

---

## 🔄 **API Contract Changes**

### **New Endpoints to Add:**
```typescript
// Transfer within family context
POST /families/{familyId}/sbd-account/transfer
{
  "to_user": "string",
  "amount": number,
  "note": "string",
  "idempotency_key": "string"  // NEW
}

// Topup family account
POST /families/{familyId}/sbd-account/topup
{
  "amount": number,
  "payment_method": "string",
  "idempotency_key": "string"  // NEW
}

// Get member available balance
GET /families/{familyId}/members/{memberId}/available
// Returns: { available_balance: number, daily_remaining: number, etc. }

// Webhook management
POST /families/{familyId}/webhooks
GET /families/{familyId}/webhooks
PUT /families/{familyId}/webhooks/{webhookId}
DELETE /families/{familyId}/webhooks/{webhookId}
```

### **Enhanced Headers:**
```typescript
// All mutation endpoints
Headers: {
  "X-Idempotency-Key": "uuid-string",  // NEW
  "Authorization": "Bearer token"
}
```

### **New Webhook Events:**
```typescript
// Event types to emit
{
  "event_id": "string",
  "type": "family.sbd.transaction.created" | "family.sbd.balance.updated" | 
         "family.token_request.created" | "family.token_request.reviewed" |
         "family.account.frozen" | "family.account.unfrozen",
  "timestamp": "ISO string",
  "payload": { /* event-specific data */ }
}
```

---

## 🤔 **Frontend Team Input Needed**

**Please provide feedback on:**

1. **Priority ranking** of the missing features (what's critical vs nice-to-have)
2. **Timeline expectations** - when do you need these features?
3. **API contract flexibility** - can you adapt to current implementation, or do you need exact spec matching?
4. **Webhook requirements** - which events are essential for your integration?
5. **Idempotency needs** - do you plan to implement client-side idempotency, or need server-side?
6. **Error handling expectations** - what error formats work best for your error handling?

**Your responses will determine the final implementation plan and API contract.**

---

## 📞 **Next Steps**

1. **Frontend Team Review** - Please review this document and provide feedback
2. **Clarification Meeting** - Schedule call to discuss open questions
3. **Final API Contract** - Create definitive contract based on discussion
4. **Implementation Timeline** - Agree on delivery schedule
5. **Integration Testing** - Plan joint testing approach

---

**Contact:** Backend Team  
**Document Version:** 1.0 - Discussion Draft  
**Last Updated:** October 22, 2025</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/docs/family_wallet_frontend_integration_discussion.md