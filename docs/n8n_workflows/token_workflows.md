# N8N Token System & Financial Workflows

## Overview
Token workflows handle SBD token operations, transfers, balance management, and integration with family accounts.

## 1. Token Transfer Automation Workflow

### Workflow Name: `token_transfer_automation`
### Purpose: Automate SBD token transfers with validation and notifications

### Trigger
- **Type**: Webhook
- **Path**: `/webhook/token-transfer`
- **Method**: POST

### Input Parameters
```json
{
  "from_user": "user_123",
  "to_user": "merchant_xyz",
  "amount": 100,
  "note": "Payment for services",
  "family_context": {
    "family_id": "fam_123",
    "validate_permissions": true
  }
}
```

### Workflow Steps

#### 1. Pre-Transfer Validation
- **API Call**: `GET /sbd_tokens` (check sender balance)
- Validate sufficient funds
- Check transfer limits

#### 2. Family Permission Validation (if applicable)
- **API Call**: `POST /family/{{family_id}}/sbd-account/validate-spending`
- **Payload**:
```json
{
  "amount": {{ $json.amount }}
}
```
- Verify spending permissions
- Check account status (frozen/unfrozen)

#### 3. Execute Transfer
- **API Call**: `POST /sbd_tokens/send`
- **Payload**:
```json
{
  "from_user": "{{ $json.from_user }}",
  "to_user": "{{ $json.to_user }}",
  "amount": {{ $json.amount }},
  "note": "{{ $json.note }}"
}
```
- Handle transaction ID generation
- Process transfer with audit trail

#### 4. Post-Transfer Actions
- Update balances
- Send notifications
- Log transaction details
- Trigger downstream workflows

#### 5. Notification & Confirmation
- Send transfer confirmation to sender
- Notify recipient of received funds
- Family notifications for family account transfers

### Error Handling
- Insufficient balance
- Invalid recipients
- Permission denied
- Account frozen
- Rate limiting

### Output
```json
{
  "success": true,
  "transaction_id": "txn_123",
  "amount": 100,
  "from_user": "user_123",
  "to_user": "merchant_xyz",
  "family_involved": true,
  "notifications_sent": 2
}
```

## 2. Balance Monitoring & Alerting Workflow

### Workflow Name: `token_balance_monitoring`
### Purpose: Monitor token balances and send alerts

### Trigger
- **Type**: Schedule
- **Cron**: `*/30 * * * *` (every 30 minutes)

### Workflow Steps

#### 1. Balance Checks
For each monitored account:
- **API Call**: `GET /sbd_tokens`
- Retrieve current balance
- Compare with previous balance

#### 2. Threshold Monitoring
- Check for low balance alerts
- Monitor for unusual activity
- Track balance trends

#### 3. Family Account Monitoring
- **API Call**: `GET /family/{{family_id}}/sbd-account`
- Monitor family account balances
- Check member spending patterns

#### 4. Alert Generation
- Send low balance notifications
- Alert on suspicious activity
- Generate balance reports

### Output
```json
{
  "accounts_monitored": 150,
  "low_balance_alerts": 3,
  "unusual_activity": 0,
  "reports_generated": 1
}
```

## 3. Transaction History & Reporting Workflow

### Workflow Name: `token_transaction_reporting`
### Purpose: Generate transaction reports and analytics

### Trigger
- **Type**: Schedule (daily/weekly) + On-demand webhook

### Workflow Steps

#### 1. Transaction Retrieval
- **API Call**: `GET /sbd_tokens/transactions`
- Retrieve transaction history
- Handle pagination for large datasets

#### 2. Family Transaction Aggregation
- **API Call**: `GET /family/{{family_id}}/sbd-account/transactions`
- Aggregate family member transactions
- Include family context

#### 3. Report Generation
- Calculate spending patterns
- Generate financial summaries
- Create transaction analytics

#### 4. Report Distribution
- Send reports via email
- Store reports in database
- Trigger dashboard updates

### Output
```json
{
  "transactions_processed": 1250,
  "reports_generated": 5,
  "emails_sent": 3,
  "total_volume": 50000
}
```

## 4. Token Request & Approval Workflow

### Workflow Name: `token_request_approval`
### Purpose: Handle token requests from family members

### Trigger
- **Type**: Schedule (hourly) + Webhook for submissions

### Workflow Steps

#### 1. Request Submission (Webhook)
- **API Call**: `POST /family/{{family_id}}/token-requests`
- Validate request data
- Check auto-approval thresholds

#### 2. Auto-Approval Processing
- Check request amount vs. auto-approval limits
- Auto-approve small requests
- Transfer tokens immediately

#### 3. Manual Review Process
- Notify family administrators
- **API Call**: `GET /family/{{family_id}}/token-requests/pending`
- Present requests for review

#### 4. Approval/Rejection Handling
- **API Call**: `POST /family/{{family_id}}/token-requests/{{request_id}}/review`
- Process admin decisions
- Transfer tokens or send rejection notifications

#### 5. Follow-up Actions
- Update request status
- Send notifications to requesters
- Log approval decisions

### Output
```json
{
  "requests_processed": 8,
  "auto_approved": 5,
  "manual_reviews": 3,
  "tokens_distributed": 2500
}
```

## 5. Family Spending Permission Management Workflow

### Workflow Name: `family_spending_permissions`
### Purpose: Manage and update family member spending permissions

### Trigger
- **Type**: Webhook + Schedule for reviews

### Workflow Steps

#### 1. Permission Updates
- **API Call**: `PUT /family/{{family_id}}/sbd-account/permissions`
- Update individual member permissions
- Bulk permission updates

#### 2. Permission Validation
- Verify admin permissions for changes
- Check permission consistency
- Validate spending limits

#### 3. Notification & Audit
- Notify affected members
- Log permission changes
- Update audit trails

#### 4. Periodic Reviews
- Review permission effectiveness
- Suggest permission adjustments
- Generate permission reports

### Output
```json
{
  "permissions_updated": 3,
  "members_notified": 3,
  "audit_entries": 3,
  "reviews_completed": 1
}
```

## 6. Account Freeze/Unfreeze Management Workflow

### Workflow Name: `account_freeze_management`
### Purpose: Handle account freezing and emergency unfreezing

### Trigger
- **Type**: Webhook + Emergency monitoring

### Workflow Steps

#### 1. Freeze Initiation
- **API Call**: `POST /family/{{family_id}}/sbd-account/freeze`
- Require admin authorization
- Provide freeze reason

#### 2. Emergency Unfreeze Process
- **API Call**: `POST /family/{{family_id}}/account/emergency-unfreeze`
- Collect member approvals
- Monitor approval progress

#### 3. Approval Processing
- **API Call**: `POST /family/emergency-unfreeze/{{request_id}}/approve`
- Track approval thresholds
- Execute unfreeze when approved

#### 4. Status Monitoring
- Monitor frozen account status
- Send status notifications
- Handle freeze expiration

### Output
```json
{
  "accounts_frozen": 1,
  "emergency_requests": 0,
  "approvals_processed": 0,
  "accounts_unfrozen": 0
}
```

## Technical Implementation Notes

### Transaction Safety
- Use idempotency keys for transfers
- Implement transaction rollback on failures
- Maintain audit trails for all operations

### Family Integration
- Always check family context for transfers
- Validate permissions before operations
- Include family metadata in transactions

### Rate Limiting
Token endpoints have specific limits:
- Balance checks: 10/minute
- Transfers: 5/minute
- Transaction history: 20/hour

### Error Handling
Token-specific errors:
```json
{
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Sender has insufficient token balance"
  }
}
```

### Monitoring & Analytics
- Track transaction volumes
- Monitor transfer success rates
- Generate financial analytics
- Alert on anomalies

## Testing Scenarios

1. **Normal Transfers**: Standard user-to-user transfers
2. **Family Transfers**: Transfers from family accounts with permissions
3. **Permission Validation**: Spending limit enforcement
4. **Error Conditions**: Insufficient balance, frozen accounts
5. **Bulk Operations**: Multiple transfers, batch processing
6. **Emergency Scenarios**: Account freezing and unfreezing

## Dependencies

- HTTP Request nodes for API calls
- Database nodes for transaction storage
- Email/SMS nodes for notifications
- Schedule nodes for recurring tasks
- Crypto nodes for transaction validation
- Analytics nodes for reporting
- Monitoring nodes for health checks</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/n8n_workflows/token_workflows.md