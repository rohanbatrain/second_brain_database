# Family SBD Wallet Comprehensive Guide

**Document Version:** 1.0.0  
**Last Updated:** October 22, 2025  
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Core Features](#core-features)
4. [API Endpoints](#api-endpoints)
5. [Spending & Permission Management](#spending--permission-management)
6. [Security & Compliance](#security--compliance)
7. [Edge Cases & Error Handling](#edge-cases--error-handling)
8. [Integration Guide](#integration-guide)
9. [Testing Scenarios](#testing-scenarios)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Family SBD Wallet is a shared token account system that enables families to pool resources, manage spending permissions, and track financial activities within the Second Brain Database ecosystem.

### Key Capabilities

- **Shared Balance**: Virtual account with pooled SBD tokens
- **Granular Permissions**: Per-member spending limits and controls
- **Transaction Tracking**: Complete audit trail with member attribution
- **Emergency Controls**: Account freeze/unfreeze for disputes
- **Notification System**: Real-time alerts for all stakeholders
- **Integration**: Seamless integration with existing SBD token system

### Design Philosophy

1. **Security First**: Multi-layer validation prevents unauthorized spending
2. **Transparency**: All transactions logged with detailed attribution
3. **Flexibility**: Customizable permissions per family member
4. **Reliability**: Transaction safety with proper error handling
5. **Auditability**: Complete tracking for compliance and accountability

---

## System Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Family SBD Wallet System                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐      ┌──────────────┐     ┌─────────────┐ │
│  │   API       │─────▶│   Manager    │────▶│  Database   │ │
│  │  Routes     │      │   Layer      │     │  (MongoDB)  │ │
│  └─────────────┘      └──────────────┘     └─────────────┘ │
│        │                     │                     │         │
│        │                     ▼                     │         │
│        │            ┌──────────────┐              │         │
│        │            │  Validation  │              │         │
│        │            │   Engine     │              │         │
│        │            └──────────────┘              │         │
│        │                     │                     │         │
│        ▼                     ▼                     ▼         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Integration Points                          │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ • SBD Token System    • Notification Service         │  │
│  │ • Security Manager    • Audit Manager                │  │
│  │ • Rate Limiting       • Error Monitoring              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Data Model

#### Family Document Structure
```json
{
  "family_id": "fam_xxx",
  "name": "Smith Family",
  "admin_user_ids": ["user1", "user2"],
  "member_count": 4,
  "sbd_account": {
    "account_username": "family_smiths",
    "is_frozen": false,
    "frozen_by": null,
    "frozen_at": null,
    "freeze_reason": null,
    "spending_permissions": {
      "user1": {
        "role": "admin",
        "spending_limit": -1,
        "can_spend": true,
        "updated_by": "user1",
        "updated_at": "2025-10-22T00:00:00Z"
      },
      "user2": {
        "role": "member",
        "spending_limit": 1000,
        "can_spend": true,
        "updated_by": "user1",
        "updated_at": "2025-10-22T00:00:00Z"
      }
    },
    "notification_settings": {
      "notify_on_spend": true,
      "notify_threshold": 500,
      "notify_admins_only": false
    }
  },
  "created_at": "2025-10-22T00:00:00Z",
  "updated_at": "2025-10-22T00:00:00Z"
}
```

#### Virtual Account Structure
```json
{
  "_id": "virtual_xxx",
  "username": "family_smiths",
  "is_virtual_account": true,
  "account_type": "family_virtual",
  "status": "active",
  "managed_by_family": "fam_xxx",
  "sbd_tokens": 5000,
  "sbd_tokens_transactions": [
    {
      "type": "send",
      "to": "merchant_xyz",
      "amount": 100,
      "timestamp": "2025-10-22T00:00:00Z",
      "transaction_id": "txn_xxx",
      "family_member_id": "user2",
      "family_member_username": "alice",
      "family_id": "fam_xxx",
      "note": "Groceries"
    }
  ],
  "security_settings": {
    "requires_family_auth": true,
    "max_transaction_amount": 10000,
    "daily_limit": 5000
  }
}
```

---

## Core Features

### 1. Shared Balance Management

**Purpose**: Centralized token pool accessible by authorized family members.

**Implementation**:
- Virtual account created during family initialization
- Username format: `family_<sanitized_family_name>`
- Separate from individual member accounts
- Standard SBD token operations (send/receive)

**Balance Operations**:
```python
# Get current balance
balance = await family_manager.get_family_sbd_balance(account_username)

# Balance automatically updated via SBD token system
# Deposits: Anyone can send to family account
# Withdrawals: Subject to spending permission validation
```

### 2. Spending Permissions

**Permission Levels**:

| Role | Spending Limit | Can Spend | Can Manage | Description |
|------|----------------|-----------|------------|-------------|
| Admin | -1 (unlimited) | Yes | Yes | Full control over account |
| Member (Full) | -1 (unlimited) | Yes | No | Can spend without limits |
| Member (Limited) | >0 (custom) | Yes | No | Can spend up to limit |
| Member (No Access) | 0 | No | No | Cannot spend from account |

**Permission Updates**:
- Only admins can update permissions
- Changes logged with admin attribution
- Notifications sent to affected members
- Real-time validation on each transaction

### 3. Transaction Attribution

**Enhanced Tracking**:
- Every transaction includes spender identification
- Family member username and ID embedded
- Request context (IP, user agent) logged
- Audit trail for compliance

**Transaction Enhancement**:
```python
# Automatic attribution on family spending
enhanced_txn = await family_audit_manager.enhance_transaction_with_family_attribution(
    transaction=base_txn,
    family_id=family_id,
    user_id=spender_id,
    username=spender_username,
    context={
        "transaction_type": "send",
        "recipient": merchant,
        "ip_address": request_ip,
        "user_agent": user_agent
    }
)
```

### 4. Account Freeze Controls

**Freeze Operations**:
- **Purpose**: Prevent spending during disputes/emergencies
- **Who**: Only family admins
- **Effect**: Blocks all spending, allows deposits
- **Reversible**: Can be unfrozen by any admin

**Use Cases**:
- Account compromise detection
- Family disputes requiring resolution
- Suspected unauthorized access
- Temporary spending pause

### 5. Notification System

**Event Types**:
- Spending permission updates
- Account freeze/unfreeze
- Large transaction alerts
- Daily spending summaries
- Balance threshold alerts

**Configuration**:
```python
notification_settings = {
    "notify_on_spend": True,           # Notify on every transaction
    "notify_threshold": 500,           # Notify if transaction > threshold
    "notify_admins_only": False,       # Notify all members or just admins
    "daily_summary": True,             # Send daily spending summary
    "balance_alert_threshold": 1000    # Alert when balance drops below
}
```

---

## API Endpoints

### 1. Get Family SBD Account

**Endpoint**: `GET /family/{family_id}/sbd-account`

**Description**: Retrieve comprehensive family account information including balance, permissions, and recent transactions.

**Authentication**: Required (family member)

**Rate Limit**: 30 requests/hour

**Request**:
```http
GET /family/fam_xxx/sbd-account HTTP/1.1
Authorization: Bearer <token>
```

**Response**:
```json
{
  "account_username": "family_smiths",
  "balance": 5000,
  "is_frozen": false,
  "frozen_by": null,
  "frozen_at": null,
  "spending_permissions": {
    "user1": {
      "role": "admin",
      "spending_limit": -1,
      "can_spend": true,
      "updated_by": "user1",
      "updated_at": "2025-10-22T00:00:00Z"
    }
  },
  "notification_settings": {
    "notify_on_spend": true,
    "notify_threshold": 500,
    "notify_admins_only": false
  },
  "recent_transactions": [
    {
      "type": "send",
      "to": "merchant_xyz",
      "amount": 100,
      "timestamp": "2025-10-22T00:00:00Z",
      "transaction_id": "txn_xxx",
      "family_member_id": "user2",
      "family_member_username": "alice"
    }
  ]
}
```

**Error Responses**:
- `404`: Family not found
- `403`: User not a family member
- `500`: Server error

---

### 2. Update Spending Permissions

**Endpoint**: `PUT /family/{family_id}/sbd-account/permissions`

**Description**: Update spending permissions for a family member.

**Authentication**: Required (family admin)

**Rate Limit**: 10 requests/hour

**Request**:
```http
PUT /family/fam_xxx/sbd-account/permissions HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_id": "user2",
  "spending_limit": 2000,
  "can_spend": true
}
```

**Request Body**:
```json
{
  "user_id": "string (required)",
  "spending_limit": "integer (required, -1 for unlimited)",
  "can_spend": "boolean (required)"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Spending permissions updated successfully",
  "data": {
    "user_id": "user2",
    "spending_limit": 2000,
    "can_spend": true,
    "updated_by": "user1",
    "updated_at": "2025-10-22T00:00:00Z"
  }
}
```

**Error Responses**:
- `404`: Family not found
- `403`: User not an admin
- `400`: Invalid permissions or user not a member

---

### 3. Freeze/Unfreeze Account

**Endpoint**: `POST /family/{family_id}/sbd-account/freeze`

**Description**: Freeze or unfreeze the family account to prevent/allow spending.

**Authentication**: Required (family admin)

**Rate Limit**: 5 requests/hour

**Request (Freeze)**:
```http
POST /family/fam_xxx/sbd-account/freeze HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "action": "freeze",
  "reason": "Suspected unauthorized access"
}
```

**Request (Unfreeze)**:
```http
POST /family/fam_xxx/sbd-account/freeze HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "action": "unfreeze"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Family account frozen successfully",
  "data": {
    "family_id": "fam_xxx",
    "is_frozen": true,
    "frozen_by": "user1",
    "frozen_at": "2025-10-22T00:00:00Z",
    "reason": "Suspected unauthorized access"
  }
}
```

**Error Responses**:
- `404`: Family not found
- `403`: User not an admin
- `400`: Account already in requested state

---

### 4. Get Transaction History

**Endpoint**: `GET /family/{family_id}/sbd-account/transactions`

**Description**: Retrieve paginated transaction history with member attribution.

**Authentication**: Required (family member)

**Rate Limit**: 20 requests/hour

**Request**:
```http
GET /family/fam_xxx/sbd-account/transactions?skip=0&limit=20 HTTP/1.1
Authorization: Bearer <token>
```

**Query Parameters**:
- `skip`: Number of transactions to skip (default: 0)
- `limit`: Maximum transactions to return (default: 20, max: 100)

**Response**:
```json
{
  "status": "success",
  "data": {
    "family_id": "fam_xxx",
    "account_username": "family_smiths",
    "current_balance": 5000,
    "transactions": [
      {
        "type": "send",
        "to": "merchant_xyz",
        "amount": 100,
        "timestamp": "2025-10-22T00:00:00Z",
        "transaction_id": "txn_xxx",
        "family_member_id": "user2",
        "family_member_username": "alice",
        "family_member_details": {
          "username": "alice",
          "email": "alice@example.com"
        },
        "note": "Groceries"
      }
    ],
    "pagination": {
      "skip": 0,
      "limit": 20,
      "total": 150,
      "has_more": true
    }
  }
}
```

**Error Responses**:
- `404`: Family not found
- `403`: User not a family member
- `500`: Server error

---

### 5. Validate Spending Permission

**Endpoint**: `POST /family/{family_id}/sbd-account/validate-spending`

**Description**: Check if the current user can spend a specific amount before initiating transaction.

**Authentication**: Required (family member)

**Rate Limit**: 50 requests/hour

**Request**:
```http
POST /family/fam_xxx/sbd-account/validate-spending HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "amount": 500
}
```

**Response (Allowed)**:
```json
{
  "status": "success",
  "data": {
    "can_spend": true,
    "amount": 500,
    "family_id": "fam_xxx",
    "account_username": "family_smiths",
    "user_permissions": {
      "spending_limit": 1000,
      "can_spend": true,
      "role": "member"
    },
    "account_status": {
      "is_frozen": false,
      "current_balance": 5000
    }
  }
}
```

**Response (Denied)**:
```json
{
  "status": "success",
  "data": {
    "can_spend": false,
    "amount": 500,
    "family_id": "fam_xxx",
    "account_username": "family_smiths",
    "user_permissions": {
      "spending_limit": 100,
      "can_spend": true,
      "role": "member"
    },
    "account_status": {
      "is_frozen": false,
      "current_balance": 5000
    },
    "denial_reason": "SPENDING_LIMIT_EXCEEDED",
    "denial_message": "Amount exceeds your spending limit of 100 tokens"
  }
}
```

**Denial Reasons**:
- `ACCOUNT_FROZEN`: Family account is frozen
- `NO_SPENDING_PERMISSION`: User lacks spending permission
- `SPENDING_LIMIT_EXCEEDED`: Amount exceeds user's limit
- `INSUFFICIENT_BALANCE`: Insufficient family account balance

---

## Spending & Permission Management

### Spending Validation Flow

```
┌─────────────────────────────────────────────────────────────┐
│              Spending Validation Process                     │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  Transaction Request │
              └──────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │ Is Virtual Account?  │
              └──────────────────────┘
                   │            │
                 Yes           No
                   │            │
                   ▼            └──▶ [Allow]
       ┌──────────────────────┐
       │ Is Family Member?    │
       └──────────────────────┘
                   │
                 Yes│  No
                   │  └──▶ [Deny: Not Family Member]
                   ▼
       ┌──────────────────────┐
       │ Is Account Frozen?   │
       └──────────────────────┘
                   │
                 No │  Yes
                   │  └──▶ [Deny: Account Frozen]
                   ▼
       ┌──────────────────────┐
       │ Has Spend Permission?│
       └──────────────────────┘
                   │
                 Yes│  No
                   │  └──▶ [Deny: No Permission]
                   ▼
       ┌──────────────────────┐
       │ Within Limit?        │
       └──────────────────────┘
                   │
                 Yes│  No
                   │  └──▶ [Deny: Limit Exceeded]
                   ▼
       ┌──────────────────────┐
       │ Sufficient Balance?  │
       └──────────────────────┘
                   │
                 Yes│  No
                   │  └──▶ [Deny: Insufficient Balance]
                   ▼
              [Allow Transaction]
```

### Permission Management Best Practices

#### 1. Setting Initial Permissions

**For Admins**:
```python
permissions = {
    "role": "admin",
    "spending_limit": -1,  # Unlimited
    "can_spend": True
}
```

**For Trusted Members**:
```python
permissions = {
    "role": "member",
    "spending_limit": 5000,  # Daily/per-transaction limit
    "can_spend": True
}
```

**For Children/Limited Access**:
```python
permissions = {
    "role": "member",
    "spending_limit": 100,  # Small amount
    "can_spend": True
}
```

**For View-Only Members**:
```python
permissions = {
    "role": "member",
    "spending_limit": 0,
    "can_spend": False  # Cannot spend
}
```

#### 2. Progressive Permission Model

**Example**: Gradually increasing child's spending limit

```python
# Month 1: Small allowance
await family_manager.update_spending_permissions(
    family_id, admin_id, child_id,
    {"spending_limit": 50, "can_spend": True}
)

# Month 3: Increased after demonstrating responsibility
await family_manager.update_spending_permissions(
    family_id, admin_id, child_id,
    {"spending_limit": 150, "can_spend": True}
)

# Month 6: Further increase
await family_manager.update_spending_permissions(
    family_id, admin_id, child_id,
    {"spending_limit": 300, "can_spend": True}
)
```

#### 3. Emergency Permission Revocation

```python
# Immediately revoke spending access
await family_manager.update_spending_permissions(
    family_id, admin_id, member_id,
    {"spending_limit": 0, "can_spend": False}
)

# Also freeze entire account if needed
await family_manager.freeze_family_account(
    family_id, admin_id, 
    reason="Unauthorized access detected"
)
```

### Transaction Attribution

All transactions automatically include:
- **Spender Identification**: User ID and username
- **Family Context**: Family ID and account
- **Request Metadata**: IP address, user agent
- **Transaction Details**: Amount, recipient, timestamp
- **Optional Notes**: Custom transaction descriptions

**Example Enhanced Transaction**:
```json
{
  "type": "send",
  "to": "merchant_xyz",
  "amount": 100,
  "timestamp": "2025-10-22T00:00:00Z",
  "transaction_id": "txn_xxx",
  "family_member_id": "user2",
  "family_member_username": "alice",
  "family_id": "fam_xxx",
  "note": "Groceries for the week",
  "request_context": {
    "ip_address": "192.168.1.1",
    "user_agent": "emotion_tracker/1.0.0"
  },
  "audit_info": {
    "logged_at": "2025-10-22T00:00:00Z",
    "validation_passed": true,
    "spending_limit_at_time": 1000
  }
}
```

---

## Security & Compliance

### Security Layers

#### 1. Authentication & Authorization
- **JWT Token**: Required for all endpoints
- **Family Membership**: Verified on every request
- **Admin Privileges**: Checked for management operations
- **Rate Limiting**: Prevents abuse and DoS attacks

#### 2. Validation Checks
- **Virtual Account Verification**: Ensures account exists and is active
- **Family Association**: Validates user belongs to family
- **Permission Checks**: Verifies spending permissions and limits
- **Balance Validation**: Confirms sufficient funds
- **Freeze Status**: Blocks spending when account frozen

#### 3. Transaction Safety
- **Replica Set Support**: Uses MongoDB transactions when available
- **Atomic Operations**: Ensures consistency
- **Race Condition Prevention**: Optimistic locking patterns
- **Rollback Capability**: Transaction failures don't corrupt state

#### 4. Audit Trail
- **Complete Logging**: Every operation logged with context
- **Immutable Records**: Transaction history preserved
- **Attribution Tracking**: Know who did what and when
- **Security Events**: Suspicious activity monitoring

### Security Event Monitoring

**Events Tracked**:
```python
security_events = [
    "spending_validation_failure",
    "spending_validation_success",
    "large_transaction_validation",
    "account_freeze",
    "account_unfreeze",
    "permission_update",
    "unauthorized_access_attempt",
    "rate_limit_exceeded"
]
```

**Alert Thresholds**:
- Multiple failed validation attempts (>5 in 10 minutes)
- Large transactions (>10,000 tokens)
- Rapid permission changes (>3 in 1 hour)
- Account freeze/unfreeze cycles (>2 in 1 day)

### Compliance Features

#### 1. Data Retention
- **Transaction History**: Retained indefinitely
- **Audit Logs**: 7 years retention
- **Permission Changes**: Complete history maintained
- **Security Events**: 2 years retention

#### 2. Export Capabilities
```python
# Export transaction history
transactions = await family_manager.get_family_transactions(
    family_id, user_id, skip=0, limit=1000
)

# Generate compliance report
report = await family_audit_manager.generate_family_compliance_report(
    family_id, start_date, end_date
)
```

#### 3. Privacy Controls
- **PII Protection**: Sensitive data sanitized in logs
- **Member Privacy**: Transaction details visible only to family members
- **Access Control**: Strict role-based permissions
- **Data Minimization**: Only necessary data retained

---

## Edge Cases & Error Handling

### Critical Edge Cases

#### 1. Account Frozen During Transaction

**Scenario**: Admin freezes account while member initiates transaction

**Handling**:
```python
# Validation occurs at transaction time
if family["sbd_account"]["is_frozen"]:
    raise AccountFrozen(
        "Family account is frozen and cannot be used for spending"
    )
```

**Prevention**: Check freeze status before AND during transaction

**User Experience**: Clear error message with reason and frozen_by info

---

#### 2. Permission Changed During Transaction

**Scenario**: Admin reduces spending limit while transaction in progress

**Handling**:
- MongoDB atomic operations ensure consistency
- Transaction succeeds or fails atomically
- No partial state possible

**Validation Timing**:
1. Pre-validation: Before transaction starts
2. Transaction validation: During database operation
3. Post-validation: Confirmation after completion

---

#### 3. Multiple Admins Modifying Permissions

**Scenario**: Two admins update same user's permissions simultaneously

**Handling**:
```python
# MongoDB update with timestamp tracking
await families_collection.update_one(
    {"family_id": family_id},
    {
        "$set": {
            f"sbd_account.spending_permissions.{user_id}": {
                "spending_limit": new_limit,
                "updated_by": admin_id,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    }
)
```

**Resolution**: Last write wins (timestamped)

**Mitigation**: Notification sent to both admins showing final state

---

#### 4. Family Deletion with Pending Transactions

**Scenario**: Family deleted while virtual account has balance

**Handling**:
```python
# Cleanup process transfers balance back
async def _cleanup_family_account(self, family_id: str):
    family = await self._get_family_by_id(family_id)
    account_username = family["sbd_account"]["account_username"]
    
    # Get current balance
    balance = await self.get_family_sbd_balance(account_username)
    
    if balance > 0:
        # Distribute to admin or family creator
        admin_id = family["admin_user_ids"][0]
        await self._transfer_balance_to_admin(
            account_username, admin_id, balance
        )
    
    # Mark virtual account as inactive
    await self._cleanup_virtual_sbd_account(
        account_username, family_id
    )
```

**Protection**: Balance never lost, always returned

---

#### 5. Spending Limit Exactly at Transaction Amount

**Scenario**: User has 100 token limit, tries to spend exactly 100

**Handling**:
```python
# Inclusive check: limit of 100 allows spending up to 100
spending_limit = permissions.get("spending_limit", 0)
if spending_limit != -1 and amount > spending_limit:
    # Rejects ONLY if amount > limit, not >=
    return False
```

**Expected Behavior**: Transaction allowed if amount ≤ limit

---

#### 6. Negative or Zero Spending Limits

**Validation**:
```python
# -1: Unlimited spending (admin default)
# 0: No spending allowed
# >0: Specific limit

if spending_limit == -1:
    # Unlimited spending
    return True
elif spending_limit == 0:
    # No spending permission
    return False
else:
    # Check against specific limit
    return amount <= spending_limit
```

---

#### 7. Virtual Account Username Collision

**Scenario**: Two families with similar names create accounts

**Prevention**:
```python
# Sanitize and uniquify
base_username = f"family_{sanitize_name(family_name)}"
username = base_username
suffix = 1

while await self._username_exists(username):
    username = f"{base_username}_{suffix}"
    suffix += 1

return username
```

**Example**: "Smith Family" → family_smiths, "Smith Family" (duplicate) → family_smiths_1

---

#### 8. Member Removal with Active Permissions

**Scenario**: Member removed from family but still has spending permissions

**Handling**:
```python
async def remove_member(self, family_id: str, admin_id: str, member_id: str):
    # Remove from family relationships
    await self._remove_family_relationship(family_id, member_id)
    
    # Clean up spending permissions
    await families_collection.update_one(
        {"family_id": family_id},
        {
            "$unset": {
                f"sbd_account.spending_permissions.{member_id}": ""
            }
        }
    )
    
    # Clean up user's family membership
    await users_collection.update_one(
        {"_id": member_id},
        {
            "$pull": {
                "family_memberships": {"family_id": family_id}
            }
        }
    )
```

**Guarantee**: Removed members lose all access immediately

---

#### 9. Insufficient Balance After Validation

**Scenario**: Balance changes between validation and transaction execution

**Handling**:
```python
# MongoDB ensures atomicity
result = await users_collection.update_one(
    {
        "username": from_user,
        "sbd_tokens": {"$gte": amount}  # Balance check in query
    },
    {
        "$inc": {"sbd_tokens": -amount},
        "$push": {"sbd_tokens_transactions": transaction}
    }
)

if result.modified_count == 0:
    # Transaction failed - balance changed
    raise InsufficientBalance("Insufficient tokens")
```

**Protection**: Transaction only succeeds if balance sufficient at execution time

---

#### 10. Admin Attempts Self-Demotion

**Scenario**: Last admin tries to remove their own admin status

**Handling**:
```python
async def demote_admin(self, family_id: str, admin_id: str, target_id: str):
    family = await self._get_family_by_id(family_id)
    
    # Check if this would leave no admins
    if target_id in family["admin_user_ids"]:
        remaining_admins = [a for a in family["admin_user_ids"] if a != target_id]
        
        if len(remaining_admins) == 0:
            raise MultipleAdminsRequired(
                "Cannot remove the last family administrator. "
                "Promote another member to admin first."
            )
```

**Protection**: Always at least one admin exists

---

### Error Handling Matrix

| Error Type | HTTP Code | User Message | Log Level | Action |
|------------|-----------|--------------|-----------|--------|
| FamilyNotFound | 404 | "Family not found" | WARNING | Return to family list |
| InsufficientPermissions | 403 | "You don't have permission for this action" | WARNING | Show permission requirements |
| AccountFrozen | 403 | "Family account is frozen: {reason}" | INFO | Show unfreeze instructions |
| SpendingLimitExceeded | 403 | "Amount exceeds your limit of {limit}" | INFO | Show current permissions |
| InsufficientBalance | 400 | "Insufficient balance in family account" | INFO | Show current balance |
| ValidationError | 400 | "{specific validation message}" | WARNING | Show validation requirements |
| RateLimitExceeded | 429 | "Too many requests. Try again in {time}" | WARNING | Implement backoff |
| ServerError | 500 | "Unable to process request" | ERROR | Contact support |

---

## Integration Guide

### Frontend Integration

#### 1. Display Family Wallet Balance

```typescript
interface FamilySBDAccount {
  account_username: string;
  balance: number;
  is_frozen: boolean;
  frozen_by?: string;
  frozen_at?: string;
  spending_permissions: {
    [user_id: string]: {
      role: string;
      spending_limit: number;
      can_spend: boolean;
      updated_at: string;
    }
  };
  recent_transactions: Transaction[];
}

async function loadFamilyWallet(familyId: string): Promise<FamilySBDAccount> {
  const response = await fetch(`/family/${familyId}/sbd-account`, {
    headers: {
      'Authorization': `Bearer ${authToken}`
    }
  });
  
  if (!response.ok) {
    throw new Error('Failed to load family wallet');
  }
  
  return await response.json();
}
```

#### 2. Spending Validation UI

```typescript
async function validateSpending(
  familyId: string, 
  amount: number
): Promise<SpendingValidation> {
  const response = await fetch(
    `/family/${familyId}/sbd-account/validate-spending`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ amount })
    }
  );
  
  const data = await response.json();
  
  if (!data.data.can_spend) {
    // Show user-friendly error
    showSpendingError(data.data.denial_reason, data.data.denial_message);
    return { allowed: false, reason: data.data.denial_reason };
  }
  
  return { allowed: true };
}
```

#### 3. Real-Time Balance Updates

```typescript
class FamilyWalletSubscription {
  private eventSource: EventSource;
  
  subscribe(familyId: string, callback: (balance: number) => void) {
    // WebSocket or SSE connection for real-time updates
    this.eventSource = new EventSource(
      `/family/${familyId}/sbd-account/stream`,
      { headers: { 'Authorization': `Bearer ${authToken}` } }
    );
    
    this.eventSource.addEventListener('balance-update', (event) => {
      const data = JSON.parse(event.data);
      callback(data.balance);
    });
    
    this.eventSource.addEventListener('transaction', (event) => {
      const transaction = JSON.parse(event.data);
      this.handleNewTransaction(transaction);
    });
  }
  
  unsubscribe() {
    this.eventSource.close();
  }
}
```

### Mobile App Integration

#### 1. Local Spending Cache

```dart
class FamilyWalletCache {
  final String familyId;
  FamilySBDAccount? _cachedAccount;
  DateTime? _lastFetch;
  
  Future<FamilySBDAccount> getAccount({bool forceRefresh = false}) async {
    if (forceRefresh || _shouldRefresh()) {
      _cachedAccount = await _fetchAccount();
      _lastFetch = DateTime.now();
    }
    
    return _cachedAccount!;
  }
  
  bool _shouldRefresh() {
    if (_cachedAccount == null || _lastFetch == null) return true;
    
    final age = DateTime.now().difference(_lastFetch!);
    return age.inMinutes > 5; // Refresh every 5 minutes
  }
  
  Future<FamilySBDAccount> _fetchAccount() async {
    final response = await http.get(
      Uri.parse('$baseUrl/family/$familyId/sbd-account'),
      headers: {'Authorization': 'Bearer $authToken'}
    );
    
    return FamilySBDAccount.fromJson(jsonDecode(response.body));
  }
}
```

#### 2. Offline Transaction Queue

```dart
class OfflineTransactionQueue {
  final _queue = <PendingTransaction>[];
  
  void queueTransaction(PendingTransaction transaction) {
    _queue.add(transaction);
    _saveQueue();
  }
  
  Future<void> processQueue() async {
    while (_queue.isNotEmpty) {
      final transaction = _queue.first;
      
      try {
        await _executeTransaction(transaction);
        _queue.removeAt(0);
        _saveQueue();
      } catch (e) {
        // Keep in queue and try again later
        print('Failed to process transaction: $e');
        break;
      }
    }
  }
  
  Future<void> _executeTransaction(PendingTransaction txn) async {
    // Validate spending first
    final validation = await http.post(
      Uri.parse('$baseUrl/family/${txn.familyId}/sbd-account/validate-spending'),
      headers: {
        'Authorization': 'Bearer $authToken',
        'Content-Type': 'application/json'
      },
      body: jsonEncode({'amount': txn.amount})
    );
    
    final validationData = jsonDecode(validation.body);
    if (!validationData['data']['can_spend']) {
      throw Exception(validationData['data']['denial_message']);
    }
    
    // Execute actual transfer
    final response = await http.post(
      Uri.parse('$baseUrl/sbd-tokens/send'),
      headers: {
        'Authorization': 'Bearer $authToken',
        'Content-Type': 'application/json'
      },
      body: jsonEncode({
        'from_user': txn.fromUser,
        'to_user': txn.toUser,
        'amount': txn.amount,
        'note': txn.note
      })
    );
    
    if (response.statusCode != 200) {
      throw Exception('Transaction failed');
    }
  }
}
```

### Backend Service Integration

#### 1. Spending Hook for External Services

```python
# In your service (e.g., shop, subscription system)

async def process_family_purchase(
    user_id: str,
    family_account: str,
    amount: int,
    item: str
) -> Dict[str, Any]:
    """Process purchase using family account."""
    
    # Get family ID from account
    family_id = await family_manager.get_family_id_by_sbd_account(family_account)
    
    if not family_id:
        raise ValueError("Invalid family account")
    
    # Validate spending permission
    can_spend = await family_manager.validate_family_spending(
        family_username=family_account,
        spender_id=user_id,
        amount=amount,
        request_context={"service": "shop", "item": item}
    )
    
    if not can_spend:
        raise InsufficientPermissions("Not authorized to spend from family account")
    
    # Execute purchase via SBD token system
    result = await sbd_token_manager.transfer(
        from_user=family_account,
        to_user="merchant_account",
        amount=amount,
        note=f"Purchase: {item}"
    )
    
    return {
        "transaction_id": result["transaction_id"],
        "family_id": family_id,
        "spender_id": user_id,
        "amount": amount,
        "item": item
    }
```

#### 2. Notification Integration

```python
async def send_family_spending_notification(
    family_id: str,
    spender_id: str,
    transaction: Dict[str, Any]
) -> None:
    """Send notifications about family spending."""
    
    # Get family and notification settings
    family = await family_manager.get_family_by_id(family_id)
    settings = family["sbd_account"]["notification_settings"]
    
    # Check if notification should be sent
    if not settings.get("notify_on_spend"):
        return
    
    # Check threshold
    threshold = settings.get("notify_threshold", 0)
    if transaction["amount"] < threshold:
        return
    
    # Get recipients
    if settings.get("notify_admins_only"):
        recipients = family["admin_user_ids"]
    else:
        # Get all family members
        members = await family_manager.get_family_members(family_id, spender_id)
        recipients = [m["user_id"] for m in members if m["user_id"] != spender_id]
    
    # Send notifications
    for recipient_id in recipients:
        await notification_manager.send_notification(
            user_id=recipient_id,
            notification_type="family_spending",
            title="Family Account Transaction",
            body=f"{transaction['spender_name']} spent {transaction['amount']} tokens",
            data={
                "family_id": family_id,
                "transaction_id": transaction["transaction_id"],
                "amount": transaction["amount"],
                "spender_id": spender_id
            }
        )
```

---

## Testing Scenarios

### Unit Tests

#### 1. Permission Validation

```python
import pytest
from second_brain_database.managers.family_manager import family_manager

@pytest.mark.asyncio
async def test_spending_permission_unlimited():
    """Test unlimited spending permission."""
    # Setup
    family_id = await create_test_family()
    admin_id = get_test_admin()
    
    # Admin has unlimited spending
    can_spend = await family_manager.validate_family_spending(
        family_username=f"family_test",
        spender_id=admin_id,
        amount=999999
    )
    
    assert can_spend is True

@pytest.mark.asyncio
async def test_spending_permission_limit():
    """Test spending limit enforcement."""
    family_id = await create_test_family()
    member_id = await add_test_member(family_id, spending_limit=100)
    
    # Within limit
    can_spend_within = await family_manager.validate_family_spending(
        family_username=f"family_test",
        spender_id=member_id,
        amount=50
    )
    assert can_spend_within is True
    
    # Exceeds limit
    can_spend_over = await family_manager.validate_family_spending(
        family_username=f"family_test",
        spender_id=member_id,
        amount=150
    )
    assert can_spend_over is False

@pytest.mark.asyncio
async def test_spending_frozen_account():
    """Test spending on frozen account."""
    family_id = await create_test_family()
    admin_id = get_test_admin()
    
    # Freeze account
    await family_manager.freeze_family_account(
        family_id, admin_id, "Test freeze"
    )
    
    # Attempt spending
    can_spend = await family_manager.validate_family_spending(
        family_username=f"family_test",
        spender_id=admin_id,
        amount=10
    )
    
    assert can_spend is False
```

#### 2. Transaction Attribution

```python
@pytest.mark.asyncio
async def test_transaction_attribution():
    """Test family member attribution in transactions."""
    family_id = await create_test_family()
    member_id = await add_test_member(family_id)
    family_username = f"family_test"
    
    # Execute transaction
    await sbd_token_manager.transfer(
        from_user=family_username,
        to_user="recipient",
        amount=50,
        spender_id=member_id
    )
    
    # Check transaction has attribution
    transactions = await family_manager.get_family_transactions(
        family_id, member_id, skip=0, limit=1
    )
    
    assert len(transactions["transactions"]) > 0
    txn = transactions["transactions"][0]
    
    assert txn["family_member_id"] == member_id
    assert "family_id" in txn
    assert "family_member_username" in txn
```

### Integration Tests

#### 1. End-to-End Spending Flow

```python
@pytest.mark.asyncio
async def test_end_to_end_family_spending(test_client):
    """Test complete spending flow from validation to execution."""
    # Create family and add member
    family_response = await test_client.post(
        "/family/create",
        json={"name": "Test Family"}
    )
    family_id = family_response.json()["family_id"]
    
    # Add tokens to family account
    await test_client.post(
        "/sbd-tokens/send",
        json={
            "from_user": "system",
            "to_user": f"family_test_family",
            "amount": 1000
        }
    )
    
    # Validate spending
    validation_response = await test_client.post(
        f"/family/{family_id}/sbd-account/validate-spending",
        json={"amount": 100}
    )
    
    assert validation_response.status_code == 200
    assert validation_response.json()["data"]["can_spend"] is True
    
    # Execute transaction
    spend_response = await test_client.post(
        "/sbd-tokens/send",
        json={
            "from_user": f"family_test_family",
            "to_user": "merchant",
            "amount": 100
        }
    )
    
    assert spend_response.status_code == 200
    
    # Verify balance updated
    account_response = await test_client.get(
        f"/family/{family_id}/sbd-account"
    )
    
    assert account_response.json()["balance"] == 900
```

### Load Testing

```python
import asyncio
import aiohttp

async def concurrent_spending_test():
    """Test concurrent spending from same family account."""
    family_id = "test_family_id"
    family_username = "family_test"
    
    # Create 10 concurrent spending requests
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(10):
            task = session.post(
                f"http://localhost:8000/sbd-tokens/send",
                json={
                    "from_user": family_username,
                    "to_user": f"merchant_{i}",
                    "amount": 10
                },
                headers={"Authorization": f"Bearer {get_test_token()}"}
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful transactions
        successful = sum(1 for r in responses if not isinstance(r, Exception))
        
        print(f"Successful transactions: {successful}/10")
        
        # Verify final balance
        balance = await get_family_balance(family_id)
        expected_balance = 1000 - (successful * 10)
        
        assert balance == expected_balance, f"Balance mismatch: {balance} != {expected_balance}"
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Transaction numbers not allowed (MongoDB standalone)

**Error**:
```
Transaction numbers are only allowed on a replica set member or mongos
```

**Cause**: Code uses MongoDB transactions but server is standalone

**Solution**:
```python
# Check replica set status first
is_replica_set = False
try:
    ismaster = await db_manager.client.admin.command("ismaster")
    is_replica_set = bool(ismaster.get("setName"))
except Exception:
    pass

# Use transactions only if replica set
if is_replica_set:
    async with await db_manager.client.start_session() as session:
        async with session.start_transaction():
            # Transaction operations
            pass
else:
    # Non-transactional operations
    pass
```

---

#### Issue 2: Spending validation passes but transaction fails

**Symptom**: `validate_family_spending` returns True but transfer fails

**Possible Causes**:
1. Balance changed between validation and execution
2. Account frozen after validation
3. Permissions revoked after validation

**Solution**: Always perform validation within transaction
```python
# In SBD token transfer
if await family_manager.is_virtual_family_account(from_user):
    # Validate at transaction time, not before
    can_spend = await family_manager.validate_family_spending(
        from_user, user_id, amount
    )
    if not can_spend:
        raise InsufficientPermissions("Spending not allowed")
```

---

#### Issue 3: AttributeError: 'FamilyManager' object has no attribute 'MultipleAdminsRequired'

**Error**:
```python
except family_manager.MultipleAdminsRequired as e:
AttributeError: 'FamilyManager' object has no attribute 'MultipleAdminsRequired'
```

**Cause**: Exception imported incorrectly

**Solution**: Import exception from module, not manager instance
```python
# Incorrect
except family_manager.MultipleAdminsRequired as e:

# Correct
from second_brain_database.managers.family_manager import MultipleAdminsRequired

except MultipleAdminsRequired as e:
```

---

#### Issue 4: Permission updates not reflected immediately

**Symptom**: Permission changes don't affect next transaction

**Cause**: Caching or stale data

**Solution**:
```python
# Always fetch fresh data from database
family = await self._get_family_by_id(family_id)  # No cache
permissions = family["sbd_account"]["spending_permissions"].get(user_id)
```

**Alternative**: Implement cache invalidation
```python
async def update_spending_permissions(self, family_id: str, ...):
    # Update database
    await families_collection.update_one(...)
    
    # Invalidate cache
    await cache_manager.invalidate(f"family:{family_id}")
```

---

#### Issue 5: Family account balance not updating

**Symptom**: Transactions succeed but balance doesn't change

**Possible Causes**:
1. Wrong account username
2. Virtual account not found
3. Transaction not recorded

**Debugging**:
```python
# Check account exists
users_collection = db_manager.get_collection("users")
account = await users_collection.find_one({
    "username": family_username,
    "is_virtual_account": True
})

if not account:
    print(f"Virtual account {family_username} not found!")

# Check recent transactions
print(f"Balance: {account.get('sbd_tokens', 0)}")
print(f"Transactions: {len(account.get('sbd_tokens_transactions', []))}")
```

---

### Debug Logging

Enable detailed logging:

```python
import logging

# Enable family manager debug logging
logging.getLogger("second_brain_database.managers.family_manager").setLevel(logging.DEBUG)

# Enable SBD token debug logging
logging.getLogger("second_brain_database.routes.sbd_tokens").setLevel(logging.DEBUG)

# Enable database query logging
logging.getLogger("second_brain_database.managers.database_manager").setLevel(logging.DEBUG)
```

Check logs for:
- Validation failures with reasons
- Permission checks
- Transaction execution
- Balance updates

---

### Performance Optimization

#### 1. Reduce Database Queries

```python
# Bad: Multiple queries
family = await self._get_family_by_id(family_id)
balance = await self.get_family_sbd_balance(family["sbd_account"]["account_username"])
transactions = await self._get_recent_family_transactions(family["sbd_account"]["account_username"])

# Good: Single aggregation
result = await families_collection.aggregate([
    {"$match": {"family_id": family_id}},
    {
        "$lookup": {
            "from": "users",
            "localField": "sbd_account.account_username",
            "foreignField": "username",
            "as": "account_data"
        }
    },
    {
        "$project": {
            "family_id": 1,
            "sbd_account": 1,
            "balance": {"$arrayElemAt": ["$account_data.sbd_tokens", 0]},
            "recent_transactions": {
                "$slice": [
                    {"$arrayElemAt": ["$account_data.sbd_tokens_transactions", 0]},
                    -10
                ]
            }
        }
    }
]).to_list(1)
```

#### 2. Cache Frequently Accessed Data

```python
from functools import lru_cache
from datetime import datetime, timedelta

class FamilyWalletCache:
    def __init__(self):
        self._cache = {}
        self._expiry = {}
    
    async def get_family_account(self, family_id: str) -> Dict[str, Any]:
        # Check cache
        if family_id in self._cache:
            if self._expiry[family_id] > datetime.now():
                return self._cache[family_id]
        
        # Fetch from database
        account = await family_manager.get_family_sbd_account(family_id, admin_id)
        
        # Cache for 5 minutes
        self._cache[family_id] = account
        self._expiry[family_id] = datetime.now() + timedelta(minutes=5)
        
        return account
```

---

## Conclusion

This comprehensive guide covers all aspects of the Family SBD Wallet system including:

✅ **Complete API documentation** with examples  
✅ **Security and compliance features**  
✅ **Edge case handling** for production reliability  
✅ **Integration examples** for frontend and backend  
✅ **Testing scenarios** for quality assurance  
✅ **Troubleshooting guide** for common issues  

### Next Steps

1. **Review Implementation**: Verify all endpoints work as documented
2. **Test Edge Cases**: Run comprehensive test suite
3. **Security Audit**: Review permission system and validation flow
4. **Performance Testing**: Load test concurrent transactions
5. **Documentation Updates**: Keep this guide current with code changes

### Support Resources

- **Code Location**: `/src/second_brain_database/routes/family/sbd_routes.py`
- **Manager**: `/src/second_brain_database/managers/family_manager.py`
- **Tests**: `/tests/test_family_*.py`
- **Additional Docs**: `/docs/family_*.md`

---

**Document Maintenance**: This guide should be updated whenever:
- New endpoints are added
- Permission logic changes
- Edge cases are discovered
- Security measures are enhanced
- Integration patterns evolve
