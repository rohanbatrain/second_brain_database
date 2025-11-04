# SBD Token System Integration Guide

## Overview

The SBD (Second Brain Database) Token System provides shared financial accounts for families with comprehensive permission management, spending controls, and transaction tracking. This guide covers integration patterns, workflows, and best practices.

## Core Concepts

### Virtual Family Accounts
- **Account Format**: `family_[identifier]` (e.g., `family_smith`)
- **Shared Balance**: All family members share the same token pool
- **Permission-Based**: Spending controlled by individual permissions
- **Audit Trail**: All transactions tracked with member attribution

### Permission Levels
- **Admin**: Unlimited spending, can manage permissions
- **Member**: Limited spending based on configured limits
- **Frozen**: No spending allowed, deposits still accepted

### Transaction Types
- **Spending**: Tokens leaving the family account
- **Deposits**: Tokens added to the family account
- **Transfers**: Internal family member transfers
- **Requests**: Formal token request workflow

## Account Management

### Get Family SBD Account Information

```http
GET /family/{family_id}/sbd-account
Authorization: Bearer <token>
```

**Response**:
```json
{
  "account_username": "family_smith",
  "balance": 1500,
  "is_frozen": false,
  "frozen_by": null,
  "frozen_at": null,
  "spending_permissions": {
    "user_123": {
      "role": "admin",
      "spending_limit": -1,
      "can_spend": true,
      "updated_by": "user_123",
      "updated_at": "2024-01-01T00:00:00Z"
    },
    "user_456": {
      "role": "member",
      "spending_limit": 100,
      "can_spend": true,
      "updated_by": "user_123",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  },
  "notification_settings": {
    "notify_on_spend": true,
    "notify_on_deposit": true,
    "large_transaction_threshold": 1000
  },
  "recent_transactions": [
    {
      "transaction_id": "txn_123",
      "amount": -50,
      "description": "Family grocery shopping",
      "user_id": "user_456",
      "timestamp": "2024-01-01T10:00:00Z",
      "type": "spend"
    },
    {
      "transaction_id": "txn_124",
      "amount": 200,
      "description": "Weekly allowance deposit",
      "user_id": "user_123",
      "timestamp": "2024-01-01T08:00:00Z",
      "type": "deposit"
    }
  ]
}
```

### Update Spending Permissions (Admin Only)

```http
PUT /family/{family_id}/sbd-account/permissions
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "user_id": "user_456",
  "spending_limit": 200,
  "can_spend": true
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Spending permissions updated successfully",
  "updated_permissions": {
    "user_id": "user_456",
    "role": "member",
    "spending_limit": 200,
    "can_spend": true,
    "updated_by": "user_123",
    "updated_at": "2024-01-01T12:00:00Z"
  },
  "notification_sent": true
}
```

### Freeze/Unfreeze Account (Admin Only)

```http
POST /family/{family_id}/sbd-account/freeze
Authorization: Bearer <admin_token>
X-TOTP-Code: 123456
Content-Type: application/json

{
  "freeze": true,
  "reason": "Suspicious activity detected"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Family account frozen successfully",
  "account_status": {
    "is_frozen": true,
    "frozen_by": "user_123",
    "frozen_at": "2024-01-01T12:00:00Z",
    "reason": "Suspicious activity detected"
  },
  "notifications_sent": ["user_456", "user_789"]
}
```

## Spending Validation

### Validate Spending Permission

Before allowing a transaction, validate the user's spending permission:

```http
POST /family/validate-spending
Authorization: Bearer <token>
Content-Type: application/json

{
  "account_username": "family_smith",
  "user_id": "user_456",
  "amount": 75,
  "description": "School lunch money"
}
```

**Response (Success)**:
```json
{
  "valid": true,
  "message": "Spending authorized",
  "details": {
    "user_spending_limit": 100,
    "remaining_limit": 25,
    "account_balance": 1500,
    "sufficient_balance": true
  }
}
```

**Response (Failure)**:
```json
{
  "valid": false,
  "error": "SPENDING_LIMIT_EXCEEDED",
  "message": "Transaction amount exceeds your spending limit",
  "details": {
    "requested_amount": 150,
    "user_spending_limit": 100,
    "exceeded_by": 50,
    "suggestion": "Request additional tokens or ask admin to increase limit"
  }
}
```

### Integration Example

```javascript
class SBDTokenValidator {
  constructor(apiClient) {
    this.apiClient = apiClient;
  }
  
  async validateSpending(accountUsername, userId, amount, description) {
    try {
      const response = await this.apiClient.post('/family/validate-spending', {
        account_username: accountUsername,
        user_id: userId,
        amount: amount,
        description: description
      });
      
      const validation = await response.json();
      
      if (!validation.valid) {
        throw new SpendingValidationError(validation.error, validation.details);
      }
      
      return validation.details;
    } catch (error) {
      console.error('Spending validation failed:', error);
      throw error;
    }
  }
  
  async processTransaction(accountUsername, userId, amount, description) {
    // 1. Validate spending permission
    const validation = await this.validateSpending(
      accountUsername, userId, amount, description
    );
    
    // 2. Process the actual transaction
    const transaction = await this.executeTransaction({
      account_username: accountUsername,
      user_id: userId,
      amount: amount,
      description: description,
      validation_id: validation.validation_id
    });
    
    return transaction;
  }
}

// Usage
const validator = new SBDTokenValidator(apiClient);

try {
  const result = await validator.processTransaction(
    'family_smith',
    'user_456',
    75,
    'School lunch money'
  );
  console.log('Transaction successful:', result);
} catch (error) {
  if (error instanceof SpendingValidationError) {
    console.error('Spending not allowed:', error.message);
    // Show user-friendly error message
  } else {
    console.error('Transaction failed:', error);
  }
}
```

## Token Request Workflow

### Create Token Request

Members can request tokens from the family account:

```http
POST /family/{family_id}/token-request
Authorization: Bearer <member_token>
Content-Type: application/json

{
  "amount": 100,
  "reason": "Need tokens for school supplies and lunch money for the week"
}
```

**Response**:
```json
{
  "request_id": "req_abc123def456",
  "family_id": "fam_abc123def456",
  "requester_user_id": "user_456",
  "amount": 100,
  "reason": "Need tokens for school supplies and lunch money for the week",
  "status": "pending",
  "auto_approved": false,
  "expires_at": "2024-01-08T00:00:00Z",
  "created_at": "2024-01-01T00:00:00Z",
  "admins_notified": ["user_123"]
}
```

### Auto-Approval Logic

Requests may be auto-approved based on family settings:

```javascript
// Auto-approval criteria (configured per family)
const autoApprovalRules = {
  max_amount: 50,           // Auto-approve up to 50 tokens
  daily_limit: 100,         // Max 100 tokens per day per user
  trusted_users: ['user_456'], // Specific users with auto-approval
  time_restrictions: {      // Time-based rules
    weekdays: { max: 25 },
    weekends: { max: 50 }
  }
};
```

### Review Token Request (Admin)

```http
POST /family/{family_id}/token-request/{request_id}/review
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "action": "approve",
  "admin_comments": "Approved for educational expenses. Please use responsibly."
}
```

**Response**:
```json
{
  "status": "success",
  "action": "approve",
  "message": "Token request approved successfully",
  "request_data": {
    "request_id": "req_abc123def456",
    "status": "approved",
    "reviewed_by": "user_123",
    "reviewed_at": "2024-01-01T12:00:00Z",
    "admin_comments": "Approved for educational expenses. Please use responsibly.",
    "tokens_transferred": true,
    "transaction_id": "txn_125"
  },
  "notifications_sent": ["user_456"]
}
```

### Get Token Requests

```http
GET /family/{family_id}/token-requests?status=pending&limit=10
Authorization: Bearer <token>
```

**Response**:
```json
{
  "requests": [
    {
      "request_id": "req_abc123def456",
      "requester_username": "jane_smith",
      "requester_user_id": "user_456",
      "amount": 100,
      "reason": "Need tokens for school supplies and lunch money for the week",
      "status": "pending",
      "created_at": "2024-01-01T00:00:00Z",
      "expires_at": "2024-01-08T00:00:00Z",
      "priority": "normal"
    }
  ],
  "pagination": {
    "total": 1,
    "page": 1,
    "limit": 10,
    "has_more": false
  }
}
```

## Transaction History and Reporting

### Get Transaction History

```http
GET /family/{family_id}/sbd-account/transactions?limit=50&offset=0&type=all
Authorization: Bearer <token>
```

**Query Parameters**:
- `limit`: Number of transactions to return (max 100)
- `offset`: Number of transactions to skip
- `type`: Filter by type (`spend`, `deposit`, `transfer`, `all`)
- `user_id`: Filter by specific user
- `start_date`: Filter from date (ISO 8601)
- `end_date`: Filter to date (ISO 8601)

**Response**:
```json
{
  "transactions": [
    {
      "transaction_id": "txn_125",
      "type": "spend",
      "amount": -100,
      "balance_after": 1400,
      "description": "Token request approval - educational expenses",
      "user_id": "user_456",
      "user_username": "jane_smith",
      "timestamp": "2024-01-01T12:00:00Z",
      "metadata": {
        "request_id": "req_abc123def456",
        "approved_by": "user_123",
        "category": "education"
      }
    },
    {
      "transaction_id": "txn_124",
      "type": "deposit",
      "amount": 200,
      "balance_after": 1500,
      "description": "Weekly allowance deposit",
      "user_id": "user_123",
      "user_username": "john_smith",
      "timestamp": "2024-01-01T08:00:00Z",
      "metadata": {
        "source": "external_transfer",
        "category": "allowance"
      }
    }
  ],
  "pagination": {
    "total": 25,
    "limit": 50,
    "offset": 0,
    "has_more": false
  },
  "summary": {
    "total_spent": -350,
    "total_deposited": 500,
    "net_change": 150,
    "transaction_count": 25
  }
}
```

### Generate Spending Report

```http
POST /family/{family_id}/sbd-account/reports/spending
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-01-31T23:59:59Z",
  "group_by": "user",
  "include_categories": true
}
```

**Response**:
```json
{
  "report_id": "rpt_abc123def456",
  "period": {
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z"
  },
  "summary": {
    "total_spent": 850,
    "total_deposited": 1200,
    "net_change": 350,
    "transaction_count": 42,
    "unique_users": 3
  },
  "by_user": [
    {
      "user_id": "user_456",
      "username": "jane_smith",
      "total_spent": 450,
      "transaction_count": 18,
      "average_transaction": 25,
      "categories": {
        "education": 200,
        "food": 150,
        "entertainment": 100
      }
    },
    {
      "user_id": "user_789",
      "username": "bob_smith",
      "total_spent": 400,
      "transaction_count": 12,
      "average_transaction": 33.33,
      "categories": {
        "transportation": 250,
        "food": 100,
        "miscellaneous": 50
      }
    }
  ],
  "trends": {
    "daily_average": 27.42,
    "peak_day": "2024-01-15",
    "peak_amount": 125,
    "most_active_user": "user_456"
  }
}
```

## Notification System Integration

### Configure Notification Preferences

```http
PUT /family/{family_id}/sbd-account/notifications
Authorization: Bearer <token>
Content-Type: application/json

{
  "notify_on_spend": true,
  "notify_on_deposit": true,
  "large_transaction_threshold": 500,
  "daily_summary": true,
  "weekly_report": true,
  "channels": ["email", "push"],
  "quiet_hours": {
    "start": "22:00",
    "end": "08:00",
    "timezone": "America/New_York"
  }
}
```

### Notification Types

The system sends various notifications for SBD account activities:

```javascript
const notificationTypes = {
  SBD_SPEND: {
    trigger: 'When tokens are spent from family account',
    recipients: 'All family members (configurable)',
    example: 'Jane spent 50 tokens on school lunch'
  },
  
  SBD_DEPOSIT: {
    trigger: 'When tokens are added to family account',
    recipients: 'All family members (configurable)',
    example: 'John added 200 tokens to the family account'
  },
  
  LARGE_TRANSACTION: {
    trigger: 'When transaction exceeds threshold',
    recipients: 'All family administrators',
    example: 'Large transaction alert: 750 tokens spent'
  },
  
  SPENDING_LIMIT_REACHED: {
    trigger: 'When user approaches or reaches spending limit',
    recipients: 'User and family administrators',
    example: 'Jane has reached 90% of her spending limit'
  },
  
  ACCOUNT_FROZEN: {
    trigger: 'When family account is frozen',
    recipients: 'All family members',
    example: 'Family account has been frozen due to security concerns'
  },
  
  TOKEN_REQUEST_CREATED: {
    trigger: 'When member creates token request',
    recipients: 'All family administrators',
    example: 'Jane requested 100 tokens for school supplies'
  },
  
  TOKEN_REQUEST_APPROVED: {
    trigger: 'When admin approves token request',
    recipients: 'Requester',
    example: 'Your token request for 100 tokens has been approved'
  }
};
```

## Advanced Integration Patterns

### Real-Time Balance Monitoring

```javascript
class FamilyAccountMonitor {
  constructor(familyId, apiClient) {
    this.familyId = familyId;
    this.apiClient = apiClient;
    this.balance = 0;
    this.listeners = [];
  }
  
  async startMonitoring(intervalMs = 30000) {
    // Initial balance fetch
    await this.updateBalance();
    
    // Set up periodic updates
    this.monitoringInterval = setInterval(async () => {
      await this.updateBalance();
    }, intervalMs);
    
    // Set up WebSocket for real-time updates (if available)
    this.setupWebSocket();
  }
  
  async updateBalance() {
    try {
      const response = await this.apiClient.get(
        `/family/${this.familyId}/sbd-account`
      );
      const accountData = await response.json();
      
      const oldBalance = this.balance;
      this.balance = accountData.balance;
      
      if (oldBalance !== this.balance) {
        this.notifyListeners('balance_changed', {
          old_balance: oldBalance,
          new_balance: this.balance,
          change: this.balance - oldBalance
        });
      }
    } catch (error) {
      console.error('Failed to update balance:', error);
      this.notifyListeners('error', error);
    }
  }
  
  onBalanceChange(callback) {
    this.listeners.push({ event: 'balance_changed', callback });
  }
  
  onError(callback) {
    this.listeners.push({ event: 'error', callback });
  }
  
  notifyListeners(event, data) {
    this.listeners
      .filter(listener => listener.event === event)
      .forEach(listener => listener.callback(data));
  }
  
  stopMonitoring() {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
    }
    if (this.websocket) {
      this.websocket.close();
    }
  }
}

// Usage
const monitor = new FamilyAccountMonitor('fam_abc123', apiClient);

monitor.onBalanceChange((data) => {
  console.log(`Balance changed: ${data.old_balance} → ${data.new_balance}`);
  updateUI(data.new_balance);
});

monitor.onError((error) => {
  console.error('Monitoring error:', error);
  showErrorMessage('Failed to update account balance');
});

await monitor.startMonitoring();
```

### Spending Analytics Dashboard

```javascript
class SpendingAnalytics {
  constructor(familyId, apiClient) {
    this.familyId = familyId;
    this.apiClient = apiClient;
  }
  
  async getSpendingTrends(days = 30) {
    const endDate = new Date();
    const startDate = new Date(endDate.getTime() - (days * 24 * 60 * 60 * 1000));
    
    const response = await this.apiClient.post(
      `/family/${this.familyId}/sbd-account/reports/spending`,
      {
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
        group_by: 'day',
        include_categories: true
      }
    );
    
    return response.json();
  }
  
  async getUserSpendingComparison() {
    const report = await this.getSpendingTrends();
    
    return report.by_user.map(user => ({
      username: user.username,
      total_spent: user.total_spent,
      percentage: (user.total_spent / report.summary.total_spent) * 100,
      categories: user.categories
    }));
  }
  
  async getPredictedMonthlySpending() {
    const currentMonth = await this.getSpendingTrends(30);
    const dailyAverage = currentMonth.summary.total_spent / 30;
    const daysInMonth = new Date().getDate();
    const remainingDays = 30 - daysInMonth;
    
    return {
      current_spending: currentMonth.summary.total_spent,
      daily_average: dailyAverage,
      predicted_total: currentMonth.summary.total_spent + (dailyAverage * remainingDays),
      days_remaining: remainingDays
    };
  }
}
```

### Automated Allowance System

```javascript
class AutomatedAllowanceManager {
  constructor(familyId, apiClient) {
    this.familyId = familyId;
    this.apiClient = apiClient;
  }
  
  async setupWeeklyAllowance(userId, amount, dayOfWeek = 0) {
    // Create recurring allowance schedule
    const schedule = {
      user_id: userId,
      amount: amount,
      frequency: 'weekly',
      day_of_week: dayOfWeek, // 0 = Sunday
      description: 'Weekly allowance',
      auto_approve: true
    };
    
    return this.apiClient.post(
      `/family/${this.familyId}/allowance/schedule`,
      schedule
    );
  }
  
  async processScheduledAllowances() {
    // This would typically be called by a scheduled job
    const response = await this.apiClient.post(
      `/family/${this.familyId}/allowance/process-scheduled`
    );
    
    const results = await response.json();
    
    // Log results
    results.processed.forEach(allowance => {
      console.log(`Processed allowance: ${allowance.amount} tokens for ${allowance.username}`);
    });
    
    return results;
  }
}
```

## Security Best Practices

### 1. Validate All Transactions

```javascript
async function secureTransactionFlow(accountUsername, userId, amount, description) {
  // 1. Validate user permissions
  const validation = await validateSpending(accountUsername, userId, amount, description);
  
  // 2. Check for suspicious patterns
  const riskAssessment = await assessTransactionRisk(userId, amount, description);
  
  if (riskAssessment.risk_level === 'high') {
    // Require additional verification
    await requireAdditionalVerification(userId, riskAssessment);
  }
  
  // 3. Execute transaction with audit trail
  const transaction = await executeTransaction({
    account_username: accountUsername,
    user_id: userId,
    amount: amount,
    description: description,
    validation_id: validation.validation_id,
    risk_assessment_id: riskAssessment.assessment_id
  });
  
  // 4. Send notifications
  await sendTransactionNotifications(transaction);
  
  return transaction;
}
```

### 2. Implement Spending Limits

```javascript
class SpendingLimitManager {
  static async checkDailyLimit(userId, amount) {
    const today = new Date().toISOString().split('T')[0];
    const dailySpending = await this.getDailySpending(userId, today);
    const dailyLimit = await this.getUserDailyLimit(userId);
    
    if (dailySpending + amount > dailyLimit) {
      throw new Error(`Daily spending limit exceeded: ${dailyLimit} tokens`);
    }
  }
  
  static async checkWeeklyLimit(userId, amount) {
    const weekStart = this.getWeekStart();
    const weeklySpending = await this.getWeeklySpending(userId, weekStart);
    const weeklyLimit = await this.getUserWeeklyLimit(userId);
    
    if (weeklySpending + amount > weeklyLimit) {
      throw new Error(`Weekly spending limit exceeded: ${weeklyLimit} tokens`);
    }
  }
  
  static async checkVelocityLimits(userId, amount) {
    const recentTransactions = await this.getRecentTransactions(userId, '1h');
    const totalRecent = recentTransactions.reduce((sum, tx) => sum + tx.amount, 0);
    
    if (totalRecent + amount > 200) { // Max 200 tokens per hour
      throw new Error('Transaction velocity limit exceeded');
    }
  }
}
```

### 3. Audit and Compliance

```javascript
class SBDAuditLogger {
  static async logTransaction(transaction, context) {
    const auditEntry = {
      timestamp: new Date().toISOString(),
      transaction_id: transaction.transaction_id,
      family_id: transaction.family_id,
      user_id: transaction.user_id,
      amount: transaction.amount,
      type: transaction.type,
      description: transaction.description,
      ip_address: context.ip_address,
      user_agent: context.user_agent,
      validation_checks: context.validation_checks,
      risk_assessment: context.risk_assessment
    };
    
    // Store in audit log
    await this.storeAuditEntry(auditEntry);
    
    // Check for compliance requirements
    await this.checkComplianceRules(auditEntry);
  }
  
  static async generateComplianceReport(familyId, startDate, endDate) {
    const transactions = await this.getTransactions(familyId, startDate, endDate);
    
    return {
      period: { start: startDate, end: endDate },
      total_transactions: transactions.length,
      total_volume: transactions.reduce((sum, tx) => sum + Math.abs(tx.amount), 0),
      suspicious_transactions: transactions.filter(tx => tx.risk_level === 'high'),
      compliance_violations: await this.checkComplianceViolations(transactions),
      recommendations: await this.generateRecommendations(transactions)
    };
  }
}
```

This comprehensive integration guide provides all the necessary information for developers to integrate with the SBD Token System effectively, including security considerations, best practices, and advanced patterns for building robust family financial management applications.