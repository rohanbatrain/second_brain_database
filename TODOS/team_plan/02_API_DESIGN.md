# API Design: Team Management Endpoints

## Overview

This document specifies all REST API endpoints for the Team Management system, including request/response models, authentication, rate limiting, and error handling.

---

## API Principles

1. **RESTful Design**: Follow REST conventions
2. **Consistent Patterns**: Match Family API patterns
3. **Versioning**: API versioned at `/api/v1`
4. **Security First**: All endpoints require authentication
5. **Rate Limited**: Prevent abuse
6. **Well Documented**: OpenAPI/Swagger specs

---

## Base URL

```
https://api.example.com/api/v1/team
```

---

## Authentication

All endpoints require JWT authentication via:
```
Authorization: Bearer <access_token>
```

---

## Core Team Management

### 1. Create Team

**Endpoint**: `POST /team/create`

**Description**: Create a new team with the current user as owner

**Rate Limit**: 5 requests/hour per user

**Request Body**:
```json
{
  "name": "Engineering Team",
  "description": "Main engineering team for product development",
  "team_type": "department",
  "visibility": "private",
  "settings": {
    "max_members": 50,
    "allow_member_invites": false,
    "require_approval_for_joining": true
  }
}
```

**Response** (201 Created):
```json
{
  "team_id": "team_abc123def456",
  "name": "Engineering Team",
  "slug": "engineering-team",
  "description": "Main engineering team for product development",
  "owner_user_id": "user_123",
  "admin_user_ids": ["user_123"],
  "member_count": 1,
  "team_type": "department",
  "visibility": "private",
  "created_at": "2024-01-01T00:00:00Z",
  "is_owner": true,
  "is_admin": true,
  "user_role": "owner",
  "sbd_account": {
    "account_username": "team_engineering",
    "balance": 0,
    "is_frozen": false
  },
  "settings": {
    "max_members": 50,
    "allow_member_invites": false,
    "require_approval_for_joining": true
  },
  "stats": {
    "current_members": 1,
    "active_projects": 0,
    "total_spent": 0
  }
}
```

**Errors**:
- `400 BAD_REQUEST`: Invalid input
- `403 FORBIDDEN`: Team limit exceeded
- `409 CONFLICT`: Team name already exists
- `429 TOO_MANY_REQUESTS`: Rate limit exceeded

---

### 2. Get My Teams

**Endpoint**: `GET /team/my-teams`

**Description**: List all teams where the user is a member

**Query Parameters**:
- `include_archived` (optional): Include archived teams (default: false)
- `role` (optional): Filter by role (owner, admin, manager, member)
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 20, max: 100)

**Response** (200 OK):
```json
{
  "teams": [
    {
      "team_id": "team_abc123",
      "name": "Engineering Team",
      "slug": "engineering-team",
      "member_count": 25,
      "user_role": "admin",
      "is_admin": true,
      "is_owner": false,
      "last_active_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20,
  "total_pages": 1
}
```

---

### 3. Get Team Details

**Endpoint**: `GET /team/{team_id}`

**Description**: Get detailed information about a specific team

**Path Parameters**:
- `team_id`: Team identifier

**Query Parameters**:
- `include_stats` (optional): Include detailed statistics (default: true)
- `include_budgets` (optional): Include budget information (default: false)

**Response** (200 OK):
```json
{
  "team_id": "team_abc123def456",
  "name": "Engineering Team",
  "slug": "engineering-team",
  "description": "Main engineering team",
  "owner_user_id": "user_123",
  "admin_user_ids": ["user_123", "user_456"],
  "manager_user_ids": ["user_789"],
  "member_count": 25,
  "active_member_count": 23,
  "team_type": "department",
  "visibility": "private",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "is_active": true,
  "is_archived": false,
  "user_role": "admin",
  "is_owner": false,
  "is_admin": true,
  "user_permissions": {
    "can_invite_members": true,
    "can_manage_budgets": true,
    "can_approve_tokens": true
  },
  "sbd_account": {
    "account_username": "team_engineering",
    "balance": 50000,
    "is_frozen": false
  },
  "budgets": {
    "total_budget": 100000,
    "allocated_budget": 75000,
    "spent_budget": 25000,
    "available_budget": 50000
  },
  "stats": {
    "total_transactions": 150,
    "total_projects": 8,
    "active_projects": 5,
    "pending_token_requests": 3
  },
  "settings": {
    "max_members": 100,
    "allow_member_invites": false
  }
}
```

**Errors**:
- `404 NOT_FOUND`: Team not found or no access
- `403 FORBIDDEN`: Insufficient permissions

---

### 4. Update Team

**Endpoint**: `PUT /team/{team_id}`

**Description**: Update team information

**Required Role**: Admin or Owner

**Request Body**:
```json
{
  "name": "Senior Engineering Team",
  "description": "Updated description",
  "settings": {
    "max_members": 75,
    "allow_member_invites": true
  }
}
```

**Response** (200 OK): Same as Get Team Details

**Errors**:
- `400 BAD_REQUEST`: Invalid input
- `403 FORBIDDEN`: Insufficient permissions
- `404 NOT_FOUND`: Team not found

---

### 5. Delete/Archive Team

**Endpoint**: `DELETE /team/{team_id}`

**Description**: Archive a team (soft delete)

**Required Role**: Owner only

**Query Parameters**:
- `permanent` (optional): Permanently delete (default: false)

**Request Body**:
```json
{
  "reason": "Team disbanded",
  "transfer_resources_to": "team_xyz789"
}
```

**Response** (200 OK):
```json
{
  "message": "Team archived successfully",
  "team_id": "team_abc123",
  "archived_at": "2024-01-15T10:30:00Z",
  "data_retention_until": "2024-04-15T10:30:00Z"
}
```

---

## Member Management

### 6. Get Team Members

**Endpoint**: `GET /team/{team_id}/members`

**Description**: List all team members

**Query Parameters**:
- `role` (optional): Filter by role
- `department` (optional): Filter by department
- `status` (optional): Filter by status (active, inactive)
- `include_inactive` (optional): Include inactive members
- `page` (optional): Page number
- `per_page` (optional): Items per page (max: 100)

**Response** (200 OK):
```json
{
  "members": [
    {
      "membership_id": "mem_abc123",
      "user_id": "user_456",
      "username": "john_doe",
      "email": "john@company.com",
      "role": "member",
      "department": "engineering",
      "title": "Senior Software Engineer",
      "joined_at": "2024-01-01T00:00:00Z",
      "last_active_at": "2024-01-15T09:00:00Z",
      "status": "active",
      "permissions": {
        "can_invite_members": false,
        "can_approve_tokens": false,
        "spending_limit": 1000
      }
    }
  ],
  "total": 25,
  "page": 1,
  "per_page": 20,
  "total_pages": 2
}
```

---

### 7. Remove Team Member

**Endpoint**: `DELETE /team/{team_id}/members/{user_id}`

**Description**: Remove a member from the team

**Required Role**: Admin or Manager (for their department)

**Request Body**:
```json
{
  "reason": "Left company",
  "transfer_tasks_to": "user_xyz789"
}
```

**Response** (200 OK):
```json
{
  "message": "Member removed successfully",
  "user_id": "user_456",
  "removed_at": "2024-01-15T10:30:00Z"
}
```

---

### 8. Update Member Role

**Endpoint**: `PUT /team/{team_id}/members/{user_id}/role`

**Description**: Change a member's role

**Required Role**: Admin or Owner

**Request Body**:
```json
{
  "role": "manager",
  "custom_role_id": null,
  "reason": "Promoted to team lead"
}
```

**Response** (200 OK):
```json
{
  "membership_id": "mem_abc123",
  "user_id": "user_456",
  "previous_role": "member",
  "new_role": "manager",
  "updated_at": "2024-01-15T10:30:00Z",
  "updated_by": "user_123"
}
```

---

### 9. Update Member Permissions

**Endpoint**: `PUT /team/{team_id}/members/{user_id}/permissions`

**Description**: Update member-specific permissions

**Required Role**: Admin or Owner

**Request Body**:
```json
{
  "permissions": {
    "can_invite_members": true,
    "can_approve_tokens": true,
    "spending_limit": 5000,
    "approval_limit": 10000
  }
}
```

**Response** (200 OK):
```json
{
  "user_id": "user_456",
  "permissions": {
    "can_invite_members": true,
    "can_approve_tokens": true,
    "spending_limit": 5000,
    "approval_limit": 10000
  },
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

## Invitation System

### 10. Invite Member

**Endpoint**: `POST /team/{team_id}/invite`

**Description**: Invite a new member to the team

**Required Permission**: `can_invite_members`

**Rate Limit**: 20 requests/hour per user

**Request Body**:
```json
{
  "invitee_email": "newmember@company.com",
  "invited_role": "member",
  "department": "engineering",
  "message": "Welcome to our team!",
  "initial_permissions": {
    "spending_limit": 500
  }
}
```

**Response** (201 Created):
```json
{
  "invitation_id": "inv_abc123",
  "team_id": "team_abc123",
  "invitee_email": "newmember@company.com",
  "invited_role": "member",
  "status": "pending",
  "expires_at": "2024-01-08T00:00:00Z",
  "accept_link": "https://app.example.com/teams/invite/accept/...",
  "email_sent": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### 11. Get Team Invitations

**Endpoint**: `GET /team/{team_id}/invitations`

**Description**: List all pending invitations

**Query Parameters**:
- `status` (optional): Filter by status (pending, accepted, declined, expired)

**Response** (200 OK):
```json
{
  "invitations": [
    {
      "invitation_id": "inv_abc123",
      "invitee_email": "newmember@company.com",
      "invited_role": "member",
      "status": "pending",
      "invited_by": "user_123",
      "created_at": "2024-01-01T00:00:00Z",
      "expires_at": "2024-01-08T00:00:00Z"
    }
  ],
  "total": 1
}
```

---

### 12. Respond to Invitation

**Endpoint**: `POST /team/invitation/{invitation_id}/respond`

**Description**: Accept or decline a team invitation

**Request Body**:
```json
{
  "action": "accept"
}
```

**Response** (200 OK):
```json
{
  "message": "Invitation accepted",
  "team_id": "team_abc123",
  "team_name": "Engineering Team",
  "membership_id": "mem_xyz789",
  "role": "member"
}
```

---

### 13. Cancel Invitation

**Endpoint**: `DELETE /team/{team_id}/invitations/{invitation_id}`

**Description**: Cancel a pending invitation

**Required Role**: Admin or inviter

**Response** (200 OK):
```json
{
  "message": "Invitation cancelled",
  "invitation_id": "inv_abc123"
}
```

---

## Role Management

### 14. List Team Roles

**Endpoint**: `GET /team/{team_id}/roles`

**Description**: Get all roles (system + custom)

**Response** (200 OK):
```json
{
  "roles": [
    {
      "role_id": "role_system_owner",
      "role_name": "Owner",
      "is_system_role": true,
      "member_count": 1,
      "permissions": { /* ... */ }
    },
    {
      "role_id": "role_abc123",
      "role_name": "Project Lead",
      "is_system_role": false,
      "member_count": 5,
      "permissions": { /* ... */ }
    }
  ],
  "total": 6
}
```

---

### 15. Create Custom Role

**Endpoint**: `POST /team/{team_id}/roles`

**Description**: Create a custom role

**Required Role**: Admin or Owner

**Request Body**:
```json
{
  "role_name": "Project Lead",
  "description": "Leads projects and manages budgets",
  "based_on_role": "manager",
  "permissions": {
    "can_create_projects": true,
    "can_approve_tokens": true,
    "approval_limit": 10000
  }
}
```

**Response** (201 Created):
```json
{
  "role_id": "role_abc123",
  "role_name": "Project Lead",
  "role_slug": "project-lead",
  "is_custom": true,
  "permissions": { /* ... */ },
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## Token Request & Approval

### 16. Create Token Request

**Endpoint**: `POST /team/{team_id}/token-requests`

**Description**: Request tokens from team budget

**Request Body**:
```json
{
  "amount": 5000,
  "reason": "Infrastructure costs for Q1",
  "category": "infrastructure",
  "project_id": "proj_abc123",
  "department_id": "dept_backend",
  "attachments": [
    {
      "filename": "quote.pdf",
      "file_data": "base64_encoded_data"
    }
  ]
}
```

**Response** (201 Created):
```json
{
  "request_id": "req_abc123",
  "team_id": "team_abc123",
  "amount": 5000,
  "status": "pending",
  "current_stage": 1,
  "total_stages": 2,
  "approval_chain": [
    {
      "stage": 1,
      "approver_role": "manager",
      "status": "pending"
    },
    {
      "stage": 2,
      "approver_role": "admin",
      "status": "pending"
    }
  ],
  "created_at": "2024-01-01T00:00:00Z",
  "expires_at": "2024-01-08T00:00:00Z"
}
```

---

### 17. Get Pending Token Requests

**Endpoint**: `GET /team/{team_id}/token-requests/pending`

**Description**: List all requests pending approval by current user

**Query Parameters**:
- `project_id` (optional): Filter by project
- `department_id` (optional): Filter by department

**Response** (200 OK):
```json
{
  "requests": [
    {
      "request_id": "req_abc123",
      "requester": {
        "user_id": "user_456",
        "username": "john_doe"
      },
      "amount": 5000,
      "reason": "Infrastructure costs",
      "current_stage": 2,
      "created_at": "2024-01-01T00:00:00Z",
      "expires_at": "2024-01-08T00:00:00Z"
    }
  ],
  "total": 1
}
```

---

### 18. Review Token Request

**Endpoint**: `POST /team/{team_id}/token-requests/{request_id}/review`

**Description**: Approve or deny a token request

**Required Permission**: `can_approve_tokens` with sufficient approval limit

**Request Body**:
```json
{
  "action": "approve",
  "comments": "Approved for Q1 roadmap"
}
```

**Response** (200 OK):
```json
{
  "request_id": "req_abc123",
  "status": "approved",
  "final_approver": "user_789",
  "approved_at": "2024-01-02T10:00:00Z",
  "transaction_id": "tx_xyz789"
}
```

---

## Budget Management

### 19. Get Team Budget

**Endpoint**: `GET /team/{team_id}/budget`

**Description**: View team budget allocation and spending

**Required Permission**: `can_view_budgets`

**Response** (200 OK):
```json
{
  "total_budget": 100000,
  "allocated_budget": 75000,
  "spent_budget": 25000,
  "available_budget": 50000,
  "budget_period": "monthly",
  "budget_reset_date": "2024-02-01T00:00:00Z",
  "departments": {
    "engineering": {
      "allocated": 50000,
      "spent": 18000,
      "available": 32000
    }
  },
  "projects": {
    "project_alpha": {
      "allocated": 30000,
      "spent": 12000,
      "available": 18000
    }
  }
}
```

---

### 20. Allocate Budget

**Endpoint**: `POST /team/{team_id}/budget/allocate`

**Description**: Allocate budget to departments/projects

**Required Permission**: `can_manage_budgets`

**Request Body**:
```json
{
  "allocation_type": "department",
  "target_id": "dept_backend",
  "amount": 30000,
  "reason": "Q1 infrastructure investment"
}
```

**Response** (200 OK):
```json
{
  "allocation_id": "alloc_abc123",
  "allocation_type": "department",
  "target_id": "dept_backend",
  "amount": 30000,
  "allocated_by": "user_123",
  "allocated_at": "2024-01-01T00:00:00Z"
}
```

---

## Project Management

### 21. Create Project

**Endpoint**: `POST /team/{team_id}/projects`

**Description**: Create a new project

**Required Permission**: `can_create_projects`

**Request Body**:
```json
{
  "name": "Project Alpha",
  "description": "Next-gen product feature",
  "priority": "high",
  "start_date": "2024-01-01",
  "target_end_date": "2024-06-30",
  "budget_allocated": 50000,
  "departments": ["backend-engineering", "qa"]
}
```

**Response** (201 Created):
```json
{
  "project_id": "proj_abc123",
  "name": "Project Alpha",
  "slug": "project-alpha",
  "status": "planning",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### 22. List Projects

**Endpoint**: `GET /team/{team_id}/projects`

**Description**: List all team projects

**Query Parameters**:
- `status` (optional): Filter by status
- `priority` (optional): Filter by priority

**Response** (200 OK):
```json
{
  "projects": [
    {
      "project_id": "proj_abc123",
      "name": "Project Alpha",
      "status": "in_progress",
      "priority": "high",
      "progress_percentage": 65,
      "budget_allocated": 50000,
      "budget_spent": 18000
    }
  ],
  "total": 8
}
```

---

## Notifications

### 23. Get Team Notifications

**Endpoint**: `GET /team/{team_id}/notifications`

**Description**: Get team-specific notifications

**Query Parameters**:
- `unread_only` (optional): Only unread notifications
- `type` (optional): Filter by notification type

**Response** (200 OK):
```json
{
  "notifications": [
    {
      "notification_id": "notif_abc123",
      "type": "token_request_pending",
      "title": "New token request",
      "message": "John Doe requested 5000 tokens",
      "priority": "normal",
      "is_read": false,
      "created_at": "2024-01-01T00:00:00Z",
      "action_url": "/teams/team_abc123/requests/req_abc123"
    }
  ],
  "unread_count": 3,
  "total": 15
}
```

---

### 24. Mark Notifications Read

**Endpoint**: `POST /team/{team_id}/notifications/mark-read`

**Description**: Mark notifications as read

**Request Body**:
```json
{
  "notification_ids": ["notif_abc123", "notif_def456"]
}
```

**Response** (200 OK):
```json
{
  "marked_read": 2,
  "remaining_unread": 1
}
```

---

## Audit & Compliance

### 25. Get Audit Trail

**Endpoint**: `GET /team/{team_id}/audit`

**Description**: Access team audit trail

**Required Permission**: `can_view_audit_logs`

**Query Parameters**:
- `event_type` (optional): Filter by event type
- `actor_user_id` (optional): Filter by actor
- `start_date` (optional): Start date
- `end_date` (optional): End date
- `page` (optional): Page number
- `per_page` (optional): Items per page (max: 100)

**Response** (200 OK):
```json
{
  "audit_entries": [
    {
      "audit_id": "audit_abc123",
      "event_type": "member_role_changed",
      "actor": {
        "user_id": "user_123",
        "username": "admin_user"
      },
      "target": {
        "type": "member",
        "user_id": "user_456"
      },
      "description": "User role changed from member to manager",
      "timestamp": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 50
}
```

---

## Webhooks

### 26. Create Webhook

**Endpoint**: `POST /team/{team_id}/webhooks`

**Description**: Register a webhook

**Required Role**: Admin

**Request Body**:
```json
{
  "name": "Slack Integration",
  "url": "https://hooks.slack.com/services/...",
  "secret": "webhook_secret_123",
  "events": [
    "member_added",
    "token_request_approved"
  ]
}
```

**Response** (201 Created):
```json
{
  "webhook_id": "webhook_abc123",
  "name": "Slack Integration",
  "url": "https://hooks.slack.com/services/...",
  "events": ["member_added", "token_request_approved"],
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### 27. List Webhooks

**Endpoint**: `GET /team/{team_id}/webhooks`

**Description**: List all team webhooks

**Response** (200 OK):
```json
{
  "webhooks": [
    {
      "webhook_id": "webhook_abc123",
      "name": "Slack Integration",
      "url": "https://hooks.slack.com/services/...",
      "events": ["member_added"],
      "is_active": true,
      "health_status": "healthy",
      "total_deliveries": 150,
      "successful_deliveries": 148
    }
  ],
  "total": 1
}
```

---

## Administrative

### 28. Get Team Limits

**Endpoint**: `GET /team/limits`

**Description**: Get current user's team limits

**Response** (200 OK):
```json
{
  "max_teams_allowed": 5,
  "max_members_per_team": 100,
  "current_teams": 2,
  "teams": [
    {
      "team_id": "team_abc123",
      "name": "Engineering Team",
      "member_count": 25,
      "user_role": "admin"
    }
  ],
  "can_create_team": true,
  "upgrade_required": false
}
```

---

## Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "TEAM_NOT_FOUND",
    "message": "Team not found or you don't have access",
    "details": {
      "team_id": "team_abc123"
    },
    "suggested_actions": [
      "Verify team ID",
      "Check your permissions",
      "Contact team admin"
    ]
  }
}
```

---

## Rate Limiting

| Endpoint Category | Limit | Period |
|------------------|-------|---------|
| Create Team | 5 | hour |
| Invite Member | 20 | hour |
| Token Request | 10 | hour |
| General Read | 1000 | hour |
| General Write | 100 | hour |

**Rate Limit Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

---

## Pagination

All list endpoints support pagination:

**Query Parameters**:
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)

**Response Headers**:
```
X-Total-Count: 150
X-Page: 1
X-Per-Page: 20
X-Total-Pages: 8
```

---

## Filtering & Sorting

**Common Query Parameters**:
- `sort_by`: Field to sort by
- `order`: `asc` or `desc` (default: `desc`)
- `filter[field]`: Filter by field value

**Example**:
```
GET /team/{team_id}/members?sort_by=joined_at&order=desc&filter[role]=admin
```

---

## API Versioning

- Current version: `v1`
- Version specified in URL: `/api/v1/team`
- Backward compatibility for 12 months after new version release

---

**Document Version**: 1.0  
**Last Updated**: October 18, 2025  
**Status**: Design Phase
