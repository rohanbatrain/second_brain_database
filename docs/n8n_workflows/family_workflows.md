# N8N Family Management Workflows

## Overview
Family management workflows handle the complex family system including creation, member management, relationships, and financial operations.

## 1. Family Creation & Setup Workflow

### Workflow Name: `family_creation_setup`
### Purpose: Create and configure a new family with initial settings

### Trigger
- **Type**: Webhook
- **Path**: `/webhook/family-create`
- **Method**: POST

### Input Parameters
```json
{
  "admin_user_id": "user_123",
  "family_name": "Smith Family",
  "initial_members": [
    {
      "user_id": "user_456",
      "relationship": "spouse",
      "permissions": {
        "can_spend": true,
        "spending_limit": 1000
      }
    }
  ],
  "settings": {
    "notification_preferences": {...},
    "spending_limits": {...}
  }
}
```

### Workflow Steps

#### 1. Family Creation
- **API Call**: `POST /family/create`
- **Payload**:
```json
{
  "name": "{{ $json.family_name }}"
}
```
- Auth: Admin user token
- Store family_id from response

#### 2. SBD Account Setup
- Family account is auto-created
- **API Call**: `GET /family/{{family_id}}/sbd-account`
- Verify account creation
- Store account details

#### 3. Initial Settings Configuration
- **API Call**: `PUT /family/{{family_id}}`
- Configure family settings
- Set up notification preferences

#### 4. Member Invitations
For each initial member:
- **API Call**: `POST /family/{{family_id}}/invite`
- **Payload**:
```json
{
  "identifier": "{{ member.email || member.username }}",
  "identifier_type": "{{ member.email ? 'email' : 'username' }}",
  "relationship_type": "{{ member.relationship }}"
}
```

#### 5. Permission Setup
- **API Call**: `PUT /family/{{family_id}}/sbd-account/permissions`
- Set spending permissions for each member

#### 6. Welcome Notifications
- Send welcome emails to all members
- Create family creation notifications
- Log setup completion

### Error Handling
- Family name conflicts
- Invalid member data
- Permission setup failures
- Invitation sending failures

### Output
```json
{
  "success": true,
  "family_id": "fam_123",
  "sbd_account": {
    "account_username": "family_smith",
    "balance": 0
  },
  "members_invited": 2,
  "setup_complete": true
}
```

## 2. Member Invitation & Onboarding Workflow

### Workflow Name: `family_member_invitation`
### Purpose: Handle member invitations, reminders, and onboarding

### Trigger
- **Type**: Schedule (daily) + Webhook for responses

### Workflow Steps

#### Invitation Management
1. **API Call**: `GET /family/{{family_id}}/invitations`
2. Check for pending invitations
3. Send reminder emails for old invitations
4. Clean up expired invitations

#### Response Handling (Webhook Trigger)
- **Trigger**: `/webhook/family-invitation-response`
- **API Call**: `POST /family/invitation/{{invitation_id}}/respond`
- Handle accept/decline responses
- Update family relationships
- Set up member permissions

#### Onboarding Process
For accepted invitations:
1. Add member to family
2. Set up spending permissions
3. Send welcome notifications
4. Update family statistics

### Output
```json
{
  "processed_invitations": 5,
  "accepted": 3,
  "declined": 1,
  "expired": 1,
  "reminders_sent": 2
}
```

## 3. Family Financial Management Workflow

### Workflow Name: `family_financial_management`
### Purpose: Manage family spending, approvals, and financial monitoring

### Trigger
- **Type**: Schedule (hourly) + Webhook for requests

### Workflow Steps

#### Token Request Processing
1. **API Call**: `GET /family/{{family_id}}/token-requests/pending`
2. Review pending requests
3. Auto-approve requests under threshold
4. Notify admins for manual approval

#### Spending Permission Updates
- **API Call**: `PUT /family/{{family_id}}/sbd-account/permissions`
- Update member spending limits
- Handle permission changes

#### Account Monitoring
- **API Call**: `GET /family/{{family_id}}/sbd-account`
- Monitor account balance
- Check for unusual activity
- Alert on low balance or high spending

#### Emergency Procedures
- Monitor for emergency unfreeze requests
- Handle account freeze/unfreeze
- Process emergency approvals

### Output
```json
{
  "requests_processed": 3,
  "auto_approved": 1,
  "pending_admin_review": 2,
  "balance_alerts": 0,
  "emergency_actions": 0
}
```

## 4. Family Notification System Workflow

### Workflow Name: `family_notification_system`
### Purpose: Manage family notifications and communication

### Trigger
- **Type**: Schedule (every 15 minutes) + Event-based

### Workflow Steps

#### Notification Processing
1. **API Call**: `GET /family/{{family_id}}/notifications`
2. Process unread notifications
3. Send email notifications based on preferences
4. Handle notification preferences

#### Digest Generation
- Generate daily/weekly notification digests
- Send summary emails
- Clean up old notifications

#### Preference Management
- **API Call**: `PUT /family/notifications/preferences`
- Update user preferences
- Sync preferences across devices

### Output
```json
{
  "notifications_processed": 25,
  "emails_sent": 10,
  "digests_generated": 3,
  "preferences_updated": 2
}
```

## 5. Family Audit & Compliance Workflow

### Workflow Name: `family_audit_compliance`
### Purpose: Maintain audit trails and ensure compliance

### Trigger
- **Type**: Schedule (daily/weekly)

### Workflow Steps

#### Audit Trail Verification
1. **API Call**: `GET /family/{{family_id}}/audit/integrity-check`
2. Verify audit trail integrity
3. Check for tampering or corruption

#### Compliance Reporting
- **API Call**: `POST /family/{{family_id}}/compliance/report`
- Generate compliance reports
- Check regulatory requirements

#### Data Retention
- Clean up old audit data per retention policy
- Archive historical data
- Maintain compliance records

### Output
```json
{
  "integrity_checks_passed": true,
  "reports_generated": 2,
  "data_cleaned": 150,
  "compliance_status": "compliant"
}
```

## 6. Family Emergency Response Workflow

### Workflow Name: `family_emergency_response`
### Purpose: Handle emergency situations and account recovery

### Trigger
- **Type**: Webhook + Schedule monitoring

### Workflow Steps

#### Emergency Unfreeze
1. Monitor for emergency unfreeze requests
2. **API Call**: `POST /family/emergency-unfreeze/{{request_id}}/approve`
3. Collect required approvals
4. Execute unfreeze when threshold met

#### Account Recovery
- **API Call**: `POST /family/{{family_id}}/recovery/initiate`
- Handle account recovery processes
- Promote backup admins if needed

#### Security Incidents
- Detect and respond to security issues
- Freeze accounts if compromised
- Notify affected members

### Output
```json
{
  "emergencies_handled": 1,
  "accounts_recovered": 0,
  "security_incidents": 0,
  "notifications_sent": 5
}
```

## Technical Implementation Notes

### Authentication
All family API calls require family member authentication:
```
Authorization: Bearer {{ $credentials.familyMemberToken }}
```

### Family Context
Maintain family_id context across workflow executions using:
- Workflow data storage
- External database
- n8n's built-in data structures

### Error Handling
Family-specific errors:
```json
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "Only family administrators can perform this action"
  }
}
```

### Rate Limiting Awareness
Family endpoints have varying rate limits:
- Basic operations: 30/hour
- Administrative: 10/hour
- Emergency: 2/hour

### Batch Processing
For bulk operations:
- Process in batches of 10-50 items
- Implement progress tracking
- Handle partial failures gracefully

### Monitoring & Alerting
- Track family health metrics
- Alert on unusual activity
- Monitor member engagement
- Report on financial activity

## Testing Scenarios

1. **Family Creation**: Complete setup with members and permissions
2. **Invitation Flow**: Send, accept, decline, reminders
3. **Financial Operations**: Requests, approvals, spending limits
4. **Emergency Scenarios**: Account freeze, recovery, unfreeze
5. **Audit & Compliance**: Report generation, integrity checks
6. **Error Conditions**: Permission denied, rate limits, network failures

## Dependencies

- HTTP Request nodes for API calls
- Email nodes for notifications
- Database nodes for state management
- Schedule nodes for recurring tasks
- Webhook nodes for event handling
- Crypto nodes for data validation
- Monitoring nodes for health checks</content>
<parameter name="filePath">/Users/rohan/Documents/repos/second_brain_database/n8n_workflows/family_workflows.md