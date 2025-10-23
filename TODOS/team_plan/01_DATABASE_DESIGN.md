# Database Design: Team Management System

## Overview

This document details the MongoDB collections, schemas, indexes, and data relationships for the Team Management system.

---

## Collection Architecture

### Design Principles

1. **Consistency with Family**: Maintain similar patterns from family collections
2. **Scalability**: Design for teams of 2-500+ members
3. **Performance**: Optimized indexes for common queries
4. **Flexibility**: Support custom roles and complex hierarchies
5. **Audit Trail**: Complete history of all changes

---

## Core Collections

### 1. `teams` Collection

**Purpose**: Store team metadata and configuration

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "team_id": "team_abc123def456",
  "name": "Engineering Team",
  "display_name": "🚀 Engineering Team",
  "slug": "engineering-team",  // URL-friendly
  "description": "Main engineering team for product development",
  
  // Organization
  "organization_id": "org_xyz789",  // Optional: parent organization
  "parent_team_id": null,  // For sub-teams
  "team_type": "department",  // department, project, cross_functional
  "visibility": "private",  // private, internal, public
  
  // Ownership & Administration
  "owner_user_id": "user_123",
  "admin_user_ids": ["user_123", "user_456"],
  "manager_user_ids": ["user_789"],
  
  // Metadata
  "member_count": 25,
  "active_member_count": 23,
  "total_projects": 8,
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-15T10:30:00Z"),
  "created_by": "user_123",
  "updated_by": "user_456",
  
  // Status
  "is_active": true,
  "is_archived": false,
  "archived_at": null,
  "archived_by": null,
  "archived_reason": null,
  
  // SBD Account
  "sbd_account": {
    "account_username": "team_engineering",
    "account_id": "acc_team_eng123",
    "balance": 50000,
    "is_frozen": false,
    "frozen_by": null,
    "frozen_at": null,
    "frozen_reason": null,
    "spending_permissions": {
      "user_789": {
        "spending_limit": 5000,
        "daily_limit": 1000,
        "can_spend": true,
        "requires_approval_above": 2000,
        "updated_at": ISODate("2024-01-01T00:00:00Z")
      }
    },
    "notification_settings": {
      "notify_on_spend": true,
      "notify_on_deposit": true,
      "large_transaction_threshold": 10000,
      "notify_admins_only": false,
      "notify_managers": true
    }
  },
  
  // Budget Management
  "budgets": {
    "total_budget": 100000,
    "allocated_budget": 75000,
    "spent_budget": 25000,
    "available_budget": 50000,
    "budget_period": "monthly",  // monthly, quarterly, yearly
    "budget_reset_date": ISODate("2024-02-01T00:00:00Z"),
    "departments": {
      "engineering": 50000,
      "qa": 15000,
      "devops": 10000
    },
    "projects": {
      "project_alpha": 30000,
      "project_beta": 20000
    }
  },
  
  // Settings
  "settings": {
    "allow_member_invites": false,  // Only admins/managers
    "allow_sub_teams": true,
    "require_approval_for_joining": true,
    "auto_approval_threshold": 1000,
    "token_request_expiry_hours": 168,
    "max_members": 100,
    "require_2fa": false,
    "allowed_domains": ["company.com", "contractor.com"],
    "custom_fields": {}
  },
  
  // Governance
  "governance": {
    "data_retention_days": 365,
    "require_approval_chain": true,
    "max_approval_stages": 3,
    "escalation_enabled": true,
    "escalation_timeout_hours": 48,
    "compliance_level": "standard",  // basic, standard, enterprise
    "audit_level": "comprehensive"  // basic, standard, comprehensive
  },
  
  // Integration
  "integrations": {
    "slack": {
      "enabled": true,
      "workspace_id": "T123456",
      "channel_id": "C789012",
      "webhook_url": "https://hooks.slack.com/..."
    },
    "webhooks": {
      "enabled": true,
      "endpoints": [
        {
          "url": "https://api.example.com/webhook",
          "events": ["member_added", "token_approved"],
          "secret": "webhook_secret_123"
        }
      ]
    }
  },
  
  // Statistics
  "stats": {
    "total_transactions": 150,
    "total_spent": 25000,
    "total_approved_requests": 45,
    "total_pending_requests": 3,
    "average_approval_time_hours": 4.5,
    "active_projects": 8
  },
  
  // Metadata
  "tags": ["engineering", "product", "core"],
  "metadata": {}
}
```

**Indexes**:
```javascript
db.teams.createIndex({ "team_id": 1 }, { unique: true })
db.teams.createIndex({ "slug": 1 }, { unique: true, sparse: true })
db.teams.createIndex({ "owner_user_id": 1 })
db.teams.createIndex({ "admin_user_ids": 1 })
db.teams.createIndex({ "manager_user_ids": 1 })
db.teams.createIndex({ "organization_id": 1 })
db.teams.createIndex({ "parent_team_id": 1 })
db.teams.createIndex({ "is_active": 1, "is_archived": 1 })
db.teams.createIndex({ "created_at": -1 })
db.teams.createIndex({ "tags": 1 })
db.teams.createIndex({ 
  "name": "text", 
  "description": "text", 
  "tags": "text" 
})  // Text search
```

---

### 2. `team_members` Collection

**Purpose**: Track team membership with roles and permissions

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "membership_id": "mem_abc123def456",
  "team_id": "team_abc123def456",
  "user_id": "user_123",
  
  // Role Information
  "role": "member",  // owner, admin, manager, member, contributor, viewer
  "custom_role_id": null,  // References team_roles collection
  "department": "engineering",
  "title": "Senior Software Engineer",
  
  // Status
  "status": "active",  // active, inactive, suspended, pending
  "is_active": true,
  "invited_by": "user_456",
  "joined_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-15T10:30:00Z"),
  
  // Permissions (can override role defaults)
  "permissions": {
    "can_invite_members": false,
    "can_create_projects": true,
    "can_approve_tokens": false,
    "can_view_budgets": true,
    "can_manage_budgets": false,
    "can_view_audit_logs": true,
    "spending_limit": 1000,
    "approval_limit": 5000
  },
  
  // Activity Tracking
  "last_active_at": ISODate("2024-01-15T09:00:00Z"),
  "login_count": 45,
  "activity_score": 85,  // 0-100 based on engagement
  
  // Projects & Departments
  "projects": [
    {
      "project_id": "proj_123",
      "role": "contributor",
      "joined_at": ISODate("2024-01-05T00:00:00Z")
    }
  ],
  "sub_teams": ["team_qa_subteam"],
  
  // Notifications
  "notification_preferences": {
    "email_notifications": true,
    "slack_notifications": true,
    "push_notifications": false,
    "notify_on_mentions": true,
    "digest_frequency": "daily"  // realtime, daily, weekly
  },
  
  // Metadata
  "notes": "Key contributor to Project Alpha",
  "tags": ["full-time", "senior"],
  "custom_fields": {},
  "metadata": {}
}
```

**Indexes**:
```javascript
db.team_members.createIndex({ "membership_id": 1 }, { unique: true })
db.team_members.createIndex({ "team_id": 1, "user_id": 1 }, { unique: true })
db.team_members.createIndex({ "team_id": 1, "role": 1 })
db.team_members.createIndex({ "team_id": 1, "status": 1 })
db.team_members.createIndex({ "team_id": 1, "is_active": 1 })
db.team_members.createIndex({ "user_id": 1 })
db.team_members.createIndex({ "department": 1 })
db.team_members.createIndex({ "joined_at": -1 })
db.team_members.createIndex({ "last_active_at": -1 })
```

---

### 3. `team_invitations` Collection

**Purpose**: Manage pending team invitations

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "invitation_id": "inv_abc123def456",
  "team_id": "team_abc123def456",
  "inviter_user_id": "user_123",
  
  // Invitee Information
  "invitee_email": "newmember@company.com",
  "invitee_user_id": "user_789",  // null if not registered
  "invitee_name": "John Doe",
  
  // Role & Permissions
  "invited_role": "member",
  "custom_role_id": null,
  "department": "engineering",
  "initial_permissions": {},
  
  // Invitation Details
  "invitation_token": "secure_token_abc123",
  "invitation_message": "Welcome to our engineering team!",
  "invitation_type": "email",  // email, link, domain
  
  // Status
  "status": "pending",  // pending, accepted, declined, expired, cancelled
  "expires_at": ISODate("2024-01-08T00:00:00Z"),
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "responded_at": null,
  "accepted_at": null,
  
  // Email Tracking
  "email_sent": true,
  "email_sent_at": ISODate("2024-01-01T00:00:01Z"),
  "email_opened": false,
  "email_opened_at": null,
  "reminder_sent_count": 1,
  "last_reminder_at": ISODate("2024-01-04T00:00:00Z"),
  
  // Links
  "accept_link": "https://app.example.com/teams/invite/accept/...",
  "decline_link": "https://app.example.com/teams/invite/decline/...",
  
  // Metadata
  "metadata": {},
  "custom_fields": {}
}
```

**Indexes**:
```javascript
db.team_invitations.createIndex({ "invitation_id": 1 }, { unique: true })
db.team_invitations.createIndex({ "invitation_token": 1 }, { unique: true })
db.team_invitations.createIndex({ "team_id": 1, "status": 1 })
db.team_invitations.createIndex({ "invitee_email": 1 })
db.team_invitations.createIndex({ "invitee_user_id": 1 })
db.team_invitations.createIndex({ "inviter_user_id": 1 })
db.team_invitations.createIndex({ "status": 1, "expires_at": 1 })
db.team_invitations.createIndex(
  { "created_at": 1 }, 
  { expireAfterSeconds: 604800 }  // TTL: 7 days
)
```

---

### 4. `team_roles` Collection

**Purpose**: Define custom roles with granular permissions

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "role_id": "role_abc123def456",
  "team_id": "team_abc123def456",
  "role_name": "Project Lead",
  "role_slug": "project-lead",
  "description": "Leads project development and approves budgets",
  
  // Type
  "is_system_role": false,  // true for predefined roles
  "is_custom": true,
  "based_on_role": "manager",  // Template role
  
  // Permissions
  "permissions": {
    // Team Management
    "can_view_team": true,
    "can_edit_team": false,
    "can_delete_team": false,
    "can_archive_team": false,
    
    // Member Management
    "can_view_members": true,
    "can_invite_members": true,
    "can_remove_members": false,
    "can_manage_roles": false,
    "can_edit_permissions": false,
    
    // Project Management
    "can_create_projects": true,
    "can_edit_projects": true,
    "can_delete_projects": false,
    "can_assign_members": true,
    
    // Budget Management
    "can_view_budgets": true,
    "can_manage_budgets": true,
    "can_allocate_budgets": true,
    "can_approve_expenses": true,
    "approval_limit": 10000,
    "spending_limit": 5000,
    
    // Token Management
    "can_request_tokens": true,
    "can_approve_tokens": true,
    "can_view_transactions": true,
    "token_approval_limit": 5000,
    
    // Audit & Compliance
    "can_view_audit_logs": true,
    "can_export_audit_logs": false,
    "can_view_reports": true,
    "can_generate_reports": true,
    
    // Integrations
    "can_manage_webhooks": false,
    "can_manage_integrations": false,
    
    // Advanced
    "can_create_sub_teams": false,
    "can_manage_departments": false
  },
  
  // Usage
  "member_count": 5,
  "is_active": true,
  "created_by": "user_123",
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-10T00:00:00Z"),
  
  // Metadata
  "color": "#FF5733",
  "icon": "👨‍💼",
  "priority": 3,  // Display order
  "metadata": {}
}
```

**Indexes**:
```javascript
db.team_roles.createIndex({ "role_id": 1 }, { unique: true })
db.team_roles.createIndex({ "team_id": 1, "role_slug": 1 }, { unique: true })
db.team_roles.createIndex({ "team_id": 1, "is_active": 1 })
db.team_roles.createIndex({ "is_system_role": 1 })
```

---

### 5. `team_departments` Collection

**Purpose**: Organizational structure within teams

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "department_id": "dept_abc123def456",
  "team_id": "team_abc123def456",
  "name": "Backend Engineering",
  "slug": "backend-engineering",
  "description": "Server-side development team",
  
  // Hierarchy
  "parent_department_id": null,
  "level": 0,
  "path": "/backend-engineering",
  
  // Leadership
  "head_user_id": "user_123",
  "manager_user_ids": ["user_456"],
  
  // Members
  "member_count": 12,
  "member_user_ids": ["user_123", "user_456", "..."],
  
  // Budget
  "budget_allocation": 30000,
  "spent_amount": 12000,
  "available_amount": 18000,
  
  // Status
  "is_active": true,
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-15T00:00:00Z"),
  
  // Metadata
  "tags": ["backend", "infrastructure"],
  "metadata": {}
}
```

**Indexes**:
```javascript
db.team_departments.createIndex({ "department_id": 1 }, { unique: true })
db.team_departments.createIndex({ "team_id": 1, "slug": 1 }, { unique: true })
db.team_departments.createIndex({ "team_id": 1, "is_active": 1 })
db.team_departments.createIndex({ "parent_department_id": 1 })
db.team_departments.createIndex({ "head_user_id": 1 })
```

---

### 6. `team_projects` Collection

**Purpose**: Project tracking and resource allocation

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "project_id": "proj_abc123def456",
  "team_id": "team_abc123def456",
  "name": "Project Alpha",
  "slug": "project-alpha",
  "description": "Next-gen product feature",
  
  // Management
  "owner_user_id": "user_123",
  "manager_user_ids": ["user_456"],
  "member_count": 8,
  
  // Status
  "status": "in_progress",  // planning, in_progress, on_hold, completed, cancelled
  "priority": "high",  // low, medium, high, critical
  "progress_percentage": 65,
  
  // Timeline
  "start_date": ISODate("2024-01-01T00:00:00Z"),
  "target_end_date": ISODate("2024-06-30T00:00:00Z"),
  "actual_end_date": null,
  "created_at": ISODate("2023-12-15T00:00:00Z"),
  "updated_at": ISODate("2024-01-15T00:00:00Z"),
  
  // Budget
  "budget_allocated": 50000,
  "budget_spent": 18000,
  "budget_remaining": 32000,
  
  // Resources
  "departments": ["backend-engineering", "qa"],
  "external_resources": [],
  
  // Metadata
  "tags": ["core-product", "q1-2024"],
  "custom_fields": {},
  "metadata": {}
}
```

**Indexes**:
```javascript
db.team_projects.createIndex({ "project_id": 1 }, { unique: true })
db.team_projects.createIndex({ "team_id": 1, "slug": 1 }, { unique: true })
db.team_projects.createIndex({ "team_id": 1, "status": 1 })
db.team_projects.createIndex({ "owner_user_id": 1 })
db.team_projects.createIndex({ "status": 1, "priority": 1 })
db.team_projects.createIndex({ "tags": 1 })
```

---

### 7. `team_token_requests` Collection

**Purpose**: Token request and approval workflow

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "request_id": "req_abc123def456",
  "team_id": "team_abc123def456",
  "requester_user_id": "user_123",
  
  // Request Details
  "amount": 5000,
  "reason": "Infrastructure costs for Q1",
  "category": "infrastructure",  // infrastructure, tools, services, etc.
  "project_id": "proj_abc123",
  "department_id": "dept_backend",
  
  // Approval Workflow
  "approval_chain": [
    {
      "stage": 1,
      "approver_user_id": "user_456",
      "approver_role": "manager",
      "status": "approved",
      "approved_at": ISODate("2024-01-02T10:00:00Z"),
      "comments": "Approved for Q1 roadmap"
    },
    {
      "stage": 2,
      "approver_user_id": "user_789",
      "approver_role": "admin",
      "status": "pending",
      "approved_at": null,
      "comments": null
    }
  ],
  "current_stage": 2,
  "total_stages": 2,
  
  // Status
  "status": "pending",  // pending, approved, denied, cancelled, expired
  "final_approver_user_id": null,
  "final_decision_at": null,
  "admin_comments": null,
  
  // Auto-approval
  "auto_approved": false,
  "auto_approval_reason": null,
  
  // Timestamps
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "expires_at": ISODate("2024-01-08T00:00:00Z"),
  "reviewed_at": null,
  "processed_at": null,
  "updated_at": ISODate("2024-01-02T10:00:00Z"),
  
  // Processing
  "transaction_id": null,
  "processed_amount": null,
  
  // Attachments
  "attachments": [
    {
      "file_id": "file_123",
      "filename": "quote.pdf",
      "url": "https://storage.example.com/..."
    }
  ],
  
  // Metadata
  "metadata": {},
  "tags": []
}
```

**Indexes**:
```javascript
db.team_token_requests.createIndex({ "request_id": 1 }, { unique: true })
db.team_token_requests.createIndex({ "team_id": 1, "status": 1 })
db.team_token_requests.createIndex({ "requester_user_id": 1 })
db.team_token_requests.createIndex({ "project_id": 1 })
db.team_token_requests.createIndex({ "department_id": 1 })
db.team_token_requests.createIndex({ "status": 1, "expires_at": 1 })
db.team_token_requests.createIndex({ 
  "approval_chain.approver_user_id": 1, 
  "approval_chain.status": 1 
})
db.team_token_requests.createIndex(
  { "created_at": 1 }, 
  { expireAfterSeconds: 2592000 }  // TTL: 30 days after creation
)
```

---

### 8. `team_notifications` Collection

**Purpose**: Team-specific notifications

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "notification_id": "notif_abc123def456",
  "team_id": "team_abc123def456",
  
  // Recipients
  "recipient_user_ids": ["user_123", "user_456"],
  "recipient_roles": ["admin", "manager"],  // Role-based targeting
  "recipient_departments": ["engineering"],
  
  // Content
  "type": "token_request_pending",
  "title": "New token request pending approval",
  "message": "User John Doe requested 5000 tokens for Project Alpha",
  "priority": "normal",  // low, normal, high, urgent
  
  // Data
  "data": {
    "request_id": "req_abc123",
    "requester_name": "John Doe",
    "amount": 5000,
    "project_name": "Project Alpha"
  },
  
  // Action
  "action_url": "/teams/team_abc123/requests/req_abc123",
  "action_text": "Review Request",
  
  // Status
  "status": "pending",  // pending, sent, failed
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "sent_at": null,
  "failed_at": null,
  "failure_reason": null,
  
  // Read Status
  "read_by": {
    "user_123": ISODate("2024-01-01T01:00:00Z"),
    "user_456": null
  },
  "read_count": 1,
  "total_recipients": 2,
  
  // Channels
  "channels": {
    "email": {
      "sent": true,
      "sent_at": ISODate("2024-01-01T00:00:01Z")
    },
    "slack": {
      "sent": true,
      "message_id": "1234567890.123456"
    },
    "push": {
      "sent": false
    }
  },
  
  // Metadata
  "metadata": {}
}
```

**Indexes**:
```javascript
db.team_notifications.createIndex({ "notification_id": 1 }, { unique: true })
db.team_notifications.createIndex({ "team_id": 1, "status": 1 })
db.team_notifications.createIndex({ "recipient_user_ids": 1 })
db.team_notifications.createIndex({ "type": 1, "created_at": -1 })
db.team_notifications.createIndex({ "created_at": -1 })
```

---

### 9. `team_audit_trail` Collection

**Purpose**: Comprehensive audit logging for compliance

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "audit_id": "audit_abc123def456",
  "team_id": "team_abc123def456",
  
  // Event Information
  "event_type": "member_role_changed",
  "event_category": "member_management",  // team_management, member_management, token_management, etc.
  "severity": "info",  // debug, info, warning, error, critical
  
  // Actor
  "actor_user_id": "user_123",
  "actor_role": "admin",
  "actor_ip_address": "192.168.1.1",
  "actor_user_agent": "Mozilla/5.0...",
  
  // Target
  "target_type": "member",  // team, member, project, token_request, etc.
  "target_id": "mem_abc123",
  "target_user_id": "user_456",
  
  // Changes
  "changes": {
    "before": {
      "role": "member",
      "permissions": {}
    },
    "after": {
      "role": "manager",
      "permissions": {"can_approve_tokens": true}
    }
  },
  
  // Details
  "description": "User role changed from member to manager",
  "reason": "Promotion to team lead",
  
  // Context
  "request_id": "req_xyz789",
  "session_id": "sess_abc123",
  "api_endpoint": "/api/v1/teams/{team_id}/members/{user_id}/role",
  "http_method": "PUT",
  
  // Timestamps
  "timestamp": ISODate("2024-01-01T00:00:00Z"),
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  
  // Compliance
  "retention_category": "member_changes",
  "retention_days": 365,
  "is_pii": false,
  "is_sensitive": false,
  
  // Metadata
  "metadata": {},
  "tags": ["role_change", "promotion"]
}
```

**Indexes**:
```javascript
db.team_audit_trail.createIndex({ "audit_id": 1 }, { unique: true })
db.team_audit_trail.createIndex({ "team_id": 1, "timestamp": -1 })
db.team_audit_trail.createIndex({ "actor_user_id": 1, "timestamp": -1 })
db.team_audit_trail.createIndex({ "event_type": 1, "timestamp": -1 })
db.team_audit_trail.createIndex({ "event_category": 1, "severity": 1 })
db.team_audit_trail.createIndex({ "target_type": 1, "target_id": 1 })
db.team_audit_trail.createIndex({ "timestamp": -1 })
// Partitioned index for compliance queries
db.team_audit_trail.createIndex({ 
  "retention_category": 1, 
  "timestamp": -1 
})
```

---

### 10. `team_webhooks` Collection

**Purpose**: Webhook configuration and delivery tracking

```javascript
{
  "_id": ObjectId("..."),
  "_schema_version": "1.0.0",
  
  // Identity
  "webhook_id": "webhook_abc123def456",
  "team_id": "team_abc123def456",
  
  // Configuration
  "name": "Slack Integration",
  "url": "https://hooks.slack.com/services/...",
  "secret": "webhook_secret_abc123",
  "events": [
    "member_added",
    "member_removed",
    "token_request_created",
    "token_request_approved",
    "project_created"
  ],
  
  // Filters
  "filters": {
    "departments": ["engineering"],
    "roles": ["admin", "manager"],
    "min_amount": 1000
  },
  
  // Status
  "is_active": true,
  "is_verified": true,
  "verified_at": ISODate("2024-01-01T00:05:00Z"),
  
  // Delivery Stats
  "total_deliveries": 150,
  "successful_deliveries": 148,
  "failed_deliveries": 2,
  "last_delivery_at": ISODate("2024-01-15T10:30:00Z"),
  "last_success_at": ISODate("2024-01-15T10:30:00Z"),
  "last_failure_at": ISODate("2024-01-10T08:15:00Z"),
  "consecutive_failures": 0,
  
  // Health
  "health_status": "healthy",  // healthy, degraded, failing
  "avg_response_time_ms": 250,
  
  // Timestamps
  "created_by": "user_123",
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-15T10:30:00Z"),
  
  // Metadata
  "description": "Send notifications to Slack",
  "metadata": {}
}
```

**Indexes**:
```javascript
db.team_webhooks.createIndex({ "webhook_id": 1 }, { unique: true })
db.team_webhooks.createIndex({ "team_id": 1, "is_active": 1 })
db.team_webhooks.createIndex({ "events": 1 })
db.team_webhooks.createIndex({ "health_status": 1 })
```

---

## Schema Versioning

All collections include `_schema_version` field to support schema evolution:

```javascript
{
  "_schema_version": "1.0.0",
  // ... rest of document
}
```

**Migration Strategy**:
1. New features increment minor version (1.0.0 → 1.1.0)
2. Breaking changes increment major version (1.x.x → 2.0.0)
3. Migration scripts handle schema upgrades
4. Old versions supported for 6 months

---

## Data Retention

| Collection | Retention Period | Archive Strategy |
|------------|------------------|------------------|
| teams | Indefinite | Archive after 90 days inactive |
| team_members | Indefinite | Archive after member leaves + 90 days |
| team_invitations | 7 days (TTL) | Auto-deleted |
| team_roles | Indefinite | Archive when no longer used |
| team_departments | Indefinite | Archive when deleted |
| team_projects | Indefinite | Archive 180 days after completion |
| team_token_requests | 30 days (TTL) | Archive to cold storage |
| team_notifications | 90 days | Archive after read |
| team_audit_trail | 365 days (configurable) | Archive to compliance storage |
| team_webhooks | Indefinite | None |

---

## Sharding Strategy (for Scale)

**When to shard**: > 500 teams or > 10,000 members

**Shard Key**: `team_id` (high cardinality, even distribution)

**Collections to shard**:
- `teams` - shard by `team_id`
- `team_members` - shard by `team_id`
- `team_audit_trail` - compound shard: `{team_id: 1, timestamp: -1}`
- `team_notifications` - shard by `team_id`

---

## Performance Considerations

1. **Compound Indexes**: Create for common query patterns
2. **Partial Indexes**: Use for status-based queries
3. **Text Indexes**: Enable search functionality
4. **TTL Indexes**: Auto-cleanup for temporary data
5. **Covered Queries**: Design indexes to cover common queries
6. **Index Intersection**: Leverage MongoDB's ability to combine indexes

---

## Next Steps

1. Review schema design with stakeholders
2. Create migration scripts
3. Implement validation rules
4. Set up monitoring for collection sizes
5. Plan for sharding if needed

---

**Document Version**: 1.0  
**Last Updated**: October 18, 2025  
**Status**: Design Phase
