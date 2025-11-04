# Team System Architecture Diagrams

## Overview

This document provides visual representations of the Team Management system architecture using ASCII diagrams and structured layouts.

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND APPLICATIONS                       │
│  (Web App, Mobile App, Third-party Integrations via API)       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ HTTPS/REST API
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                      API GATEWAY / FASTAPI                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Authentication Middleware (JWT)                         │   │
│  │  Rate Limiting Middleware                                │   │
│  │  Request Logging Middleware                              │   │
│  │  Permission Checking Middleware                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              TEAM API ROUTES (/api/v1/team)              │  │
│  │                                                            │  │
│  │  • Core Team Management (create, list, get, update, del) │  │
│  │  • Member Management (add, remove, update role)          │  │
│  │  • Invitation System (invite, respond, cancel)           │  │
│  │  • Role Management (list, create, update custom roles)   │  │
│  │  • Token Requests (create, review, approve)              │  │
│  │  • Budget Management (allocate, track)                   │  │
│  │  • Project Management (create, track, assign)            │  │
│  │  • Department Management (create, manage hierarchy)      │  │
│  │  • Notifications (list, mark read)                       │  │
│  │  • Audit Trail (view, export)                            │  │
│  │  • Webhooks (register, manage)                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     BUSINESS LOGIC LAYER                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    TeamManager                             │  │
│  │  • Core team operations                                    │  │
│  │  • Member lifecycle management                             │  │
│  │  • Invitation workflow                                     │  │
│  │  • SBD account integration                                 │  │
│  │  • Token request processing                                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  TeamRBACManager                           │  │
│  │  • Permission checking                                     │  │
│  │  • Role management                                         │  │
│  │  • Custom role creation                                    │  │
│  │  • Permission inheritance                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  TeamAuditManager                          │  │
│  │  • Audit trail logging                                     │  │
│  │  • Compliance reporting                                    │  │
│  │  • Data retention management                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 TeamMonitoring                             │  │
│  │  • Operation tracking                                      │  │
│  │  • Performance metrics                                     │  │
│  │  • Error monitoring                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               TeamWebhookManager                           │  │
│  │  • Webhook registration                                    │  │
│  │  • Event delivery                                          │  │
│  │  • Retry logic                                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
┌───────────────────┐ ┌──────────┐ ┌──────────────┐
│   MongoDB         │ │  Redis   │ │ External     │
│   (10 Collections)│ │  Cache   │ │ Services     │
│                   │ │          │ │              │
│  • teams          │ │ • Perms  │ │ • Email      │
│  • team_members   │ │ • Sessions│ │ • Slack      │
│  • team_roles     │ │ • Rate   │ │ • MS Teams   │
│  • team_projects  │ │   Limits │ │ • Webhooks   │
│  • team_budgets   │ │          │ │              │
│  • ...            │ │          │ │              │
└───────────────────┘ └──────────┘ └──────────────┘
```

---

## Data Flow: Team Creation

```
┌──────────┐
│  User    │
└────┬─────┘
     │ 1. POST /team/create
     │    {name: "Engineering Team"}
     │
┌────▼─────────────────────────────┐
│  API Routes                      │
│  • Authenticate user             │
│  • Check rate limit              │
│  • Validate request              │
└────┬─────────────────────────────┘
     │ 2. Call TeamManager.create_team()
     │
┌────▼─────────────────────────────┐
│  TeamManager                     │
│  • Check user team limits        │
│  • Generate team_id              │
│  • Create team document          │
│  • Create SBD account            │
│  • Add user as owner             │
│  • Log audit event               │
└────┬─────────────────────────────┘
     │ 3. Database operations
     │
┌────▼─────────────────────────────┐
│  MongoDB                         │
│  • Insert into teams collection  │
│  • Insert into team_members      │
│  • Update users collection       │
│  • Insert into audit_trail       │
└────┬─────────────────────────────┘
     │ 4. Return team data
     │
┌────▼─────────────────────────────┐
│  Redis Cache                     │
│  • Cache team data               │
│  • Cache user permissions        │
└────┬─────────────────────────────┘
     │ 5. Return response
     │
┌────▼─────┐
│  User    │
│  Success │
└──────────┘
```

---

## Data Flow: Token Request Approval (Multi-Stage)

```
┌──────────┐
│  Member  │ Request tokens
└────┬─────┘
     │ 1. POST /team/{id}/token-requests
     │    {amount: 5000, reason: "Infrastructure"}
     │
┌────▼──────────────────────────────────────────────┐
│  TeamManager.create_token_request()               │
│  • Validate member permissions                    │
│  • Check budget availability                      │
│  • Determine approval chain                       │
│  • Create token_request document                  │
│  • Notify first approver                          │
└────┬──────────────────────────────────────────────┘
     │ 2. Request created, awaiting approval
     │
┌────▼─────────────┐
│  team_token_     │
│  requests        │
│                  │
│  status: pending │
│  current_stage:1 │
│  approval_chain: │
│    Stage 1:      │
│      Manager     │
│      [PENDING]   │
│    Stage 2:      │
│      Admin       │
│      [PENDING]   │
└──────────────────┘
     │ 3. Manager approves
     │
┌────▼─────────┐
│  Manager     │ Approve Stage 1
└────┬─────────┘
     │ 4. POST /team/{id}/token-requests/{req_id}/review
     │    {action: "approve", comments: "Approved"}
     │
┌────▼──────────────────────────────────────────────┐
│  TeamManager.review_token_request()               │
│  • Validate manager has approval permission       │
│  • Update approval_chain (Stage 1 → APPROVED)     │
│  • Move to next stage                             │
│  • Notify next approver (Admin)                   │
└────┬──────────────────────────────────────────────┘
     │ 5. Stage 1 approved, awaiting Stage 2
     │
┌────▼─────────────┐
│  team_token_     │
│  requests        │
│                  │
│  status: pending │
│  current_stage:2 │
│  approval_chain: │
│    Stage 1:      │
│      Manager     │
│      [APPROVED]  │
│    Stage 2:      │
│      Admin       │
│      [PENDING]   │
└──────────────────┘
     │ 6. Admin approves
     │
┌────▼─────────┐
│  Admin       │ Approve Stage 2 (Final)
└────┬─────────┘
     │ 7. POST /team/{id}/token-requests/{req_id}/review
     │    {action: "approve"}
     │
┌────▼──────────────────────────────────────────────┐
│  TeamManager.review_token_request()               │
│  • Validate admin has approval permission         │
│  • Update approval_chain (Stage 2 → APPROVED)     │
│  • Process token transfer                         │
│  • Update team budget                             │
│  • Notify requester                               │
│  • Log audit event                                │
└────┬──────────────────────────────────────────────┘
     │ 8. Request fully approved
     │
┌────▼─────────────┐
│  team_token_     │
│  requests        │
│                  │
│  status: approved│
│  current_stage:2 │
│  approval_chain: │
│    Stage 1:      │
│      Manager     │
│      [APPROVED]  │
│    Stage 2:      │
│      Admin       │
│      [APPROVED]  │
│  transaction_id: │
│    "tx_abc123"   │
└──────────────────┘
     │ 9. Tokens transferred
     │
┌────▼─────────┐
│  Member      │
│  Tokens      │
│  Received!   │
└──────────────┘
```

---

## RBAC Permission Flow

```
┌──────────────────────────────────────────────┐
│  User attempts action                        │
│  (e.g., invite member to team)               │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│  Permission Middleware                       │
│  @require_team_permission("can_invite")      │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│  TeamRBACManager.check_permission()          │
│  (user_id, team_id, "can_invite_members")   │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│  Check Redis Cache                           │
│  Key: "team_perms:{team_id}:{user_id}"      │
└────┬─────────────────────────┬───────────────┘
     │ Cache HIT               │ Cache MISS
     │                         │
     ▼                         ▼
┌─────────────┐       ┌───────────────────────┐
│Return cached│       │  Query Database       │
│permissions  │       │  • Get team_members   │
└─────┬───────┘       │  • Get user role      │
      │               │  • Get custom_role    │
      │               │  • Get permissions    │
      │               └──────┬────────────────┘
      │                      │
      │                      ▼
      │               ┌──────────────────────┐
      │               │  Merge Permissions   │
      │               │  • Role defaults     │
      │               │  • Custom role perms │
      │               │  • Individual perms  │
      │               │  • Department perms  │
      │               └──────┬───────────────┘
      │                      │
      │                      ▼
      │               ┌──────────────────────┐
      │               │  Cache in Redis      │
      │               │  (TTL: 5 minutes)    │
      │               └──────┬───────────────┘
      │                      │
      └──────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│  Check Permission                            │
│  permissions["can_invite_members"] == true?  │
└────────────────┬─────────────────────────────┘
                 │
         ┌───────┴───────┐
         │               │
         ▼               ▼
    ┌────────┐      ┌──────────┐
    │  YES   │      │   NO     │
    │        │      │          │
    │ Allow  │      │ Deny     │
    │ Action │      │ (403)    │
    └────────┘      └──────────┘
```

---

## Database Collection Relationships

```
┌─────────────────────┐
│       teams         │◄──────────────┐
│  • team_id (PK)     │               │
│  • name             │               │
│  • owner_user_id    │               │
│  • admin_user_ids   │               │
│  • sbd_account      │               │
└─────────┬───────────┘               │
          │                           │
          │ 1:N                       │
          │                           │
          ▼                           │
┌─────────────────────┐               │
│   team_members      │               │
│  • membership_id(PK)│               │
│  • team_id (FK) ────┼───────────────┘
│  • user_id          │
│  • role             │
│  • custom_role_id───┼────┐
│  • department_id────┼──┐ │
│  • permissions      │  │ │
└─────────────────────┘  │ │
                         │ │
                         │ │
    ┌────────────────────┘ │
    │                      │
    ▼                      │
┌─────────────────────┐   │
│  team_departments   │   │
│  • dept_id (PK)     │   │
│  • team_id (FK)     │   │
│  • name             │   │
│  • parent_dept_id   │   │
│  • budget_allocated │   │
└─────────────────────┘   │
                          │
    ┌─────────────────────┘
    │
    ▼
┌─────────────────────┐
│    team_roles       │
│  • role_id (PK)     │
│  • team_id (FK)     │
│  • role_name        │
│  • permissions      │
└─────────────────────┘

┌─────────────────────┐
│ team_invitations    │
│  • invitation_id(PK)│
│  • team_id (FK)     │
│  • inviter_user_id  │
│  • invitee_email    │
│  • invited_role     │
│  • status           │
└─────────────────────┘

┌─────────────────────┐
│  team_projects      │
│  • project_id (PK)  │
│  • team_id (FK)     │
│  • name             │
│  • budget_allocated │
│  • status           │
└─────────────────────┘

┌─────────────────────┐
│team_token_requests  │
│  • request_id (PK)  │
│  • team_id (FK)     │
│  • requester_id     │
│  • amount           │
│  • approval_chain   │
│  • status           │
└─────────────────────┘

┌─────────────────────┐
│ team_notifications  │
│  • notification_id  │
│  • team_id (FK)     │
│  • recipient_ids    │
│  • type             │
│  • message          │
└─────────────────────┘

┌─────────────────────┐
│ team_audit_trail    │
│  • audit_id (PK)    │
│  • team_id (FK)     │
│  • actor_user_id    │
│  • event_type       │
│  • changes          │
│  • timestamp        │
└─────────────────────┘

┌─────────────────────┐
│   team_webhooks     │
│  • webhook_id (PK)  │
│  • team_id (FK)     │
│  • url              │
│  • events           │
│  • is_active        │
└─────────────────────┘
```

---

## Team Lifecycle

```
┌───────────────┐
│  User creates │
│  team         │
└───────┬───────┘
        │
        ▼
┌───────────────────────────┐
│  TEAM CREATED             │
│  • Status: active         │
│  • Owner assigned         │
│  • SBD account created    │
│  • Member count: 1        │
└───────┬───────────────────┘
        │
        ▼
┌───────────────────────────┐
│  INVITE MEMBERS           │
│  • Send invitations       │
│  • Members accept/decline │
│  • Assign roles           │
└───────┬───────────────────┘
        │
        ▼
┌───────────────────────────┐
│  CONFIGURE TEAM           │
│  • Create departments     │
│  • Create projects        │
│  • Set budgets            │
│  • Define custom roles    │
│  • Configure webhooks     │
└───────┬───────────────────┘
        │
        ▼
┌───────────────────────────┐
│  ACTIVE OPERATIONS        │
│  • Members collaborate    │
│  • Request tokens         │
│  • Approve requests       │
│  • Track projects         │
│  • Generate reports       │
└───────┬───────────────────┘
        │
        ▼
┌───────────────────────────┐
│  TEAM LIFECYCLE OPTIONS   │
└───────┬───────────────────┘
        │
        ├─────────────┬─────────────┬─────────────┐
        │             │             │             │
        ▼             ▼             ▼             ▼
┌──────────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
│ Continue     │ │ Archive │ │  Merge  │ │ Delete   │
│ Active       │ │ Team    │ │  Teams  │ │ (Hard)   │
│              │ │         │ │         │ │          │
│ (Ongoing)    │ │ (Soft   │ │ (Combine│ │ (Perm.   │
│              │ │ Delete) │ │ Teams)  │ │ Removal) │
└──────────────┘ └─────────┘ └─────────┘ └──────────┘
```

---

## Comparison: Family vs Team Collections

```
FAMILY SYSTEM                 TEAM SYSTEM
═════════════                 ═══════════

families                      teams
  ├─ family_id                  ├─ team_id
  ├─ name                       ├─ name
  ├─ admin_user_ids             ├─ owner_user_id
  ├─ member_count               ├─ admin_user_ids
  ├─ sbd_account                ├─ manager_user_ids
  └─ settings                   ├─ member_count
                                ├─ team_type (NEW)
family_relationships          ├─ visibility (NEW)
  ├─ relationship_id            ├─ sbd_account
  ├─ family_id                  ├─ budgets (NEW)
  ├─ user_a_id                  └─ integrations (NEW)
  ├─ user_b_id
  ├─ relationship_type        team_members
  └─ status                     ├─ membership_id
                                ├─ team_id
family_invitations            ├─ user_id
  ├─ invitation_id              ├─ role (ENHANCED)
  ├─ family_id                  ├─ custom_role_id (NEW)
  ├─ inviter_user_id            ├─ department (NEW)
  ├─ invitee_email              ├─ title (NEW)
  ├─ relationship_type          └─ permissions (ENHANCED)
  └─ status
                              team_roles (NEW)
family_token_requests           ├─ role_id
  ├─ request_id                 ├─ team_id
  ├─ family_id                  ├─ role_name
  ├─ requester_user_id          ├─ is_custom
  ├─ amount                     └─ permissions
  ├─ reason
  ├─ status                   team_invitations
  └─ reviewed_by                ├─ invitation_id
                                ├─ team_id
family_notifications          ├─ inviter_user_id
  ├─ notification_id            ├─ invitee_email
  ├─ family_id                  ├─ invited_role (ENHANCED)
  ├─ recipient_user_ids         └─ department (NEW)
  ├─ type
  ├─ message                  team_departments (NEW)
  └─ read_by                    ├─ department_id
                                ├─ team_id
(Audit trail implicit)        ├─ name
                                ├─ parent_dept_id
                                └─ budget_allocation

                              team_projects (NEW)
                                ├─ project_id
                                ├─ team_id
                                ├─ name
                                ├─ status
                                └─ budget_allocated

                              team_token_requests
                                ├─ request_id
                                ├─ team_id
                                ├─ requester_user_id
                                ├─ amount
                                ├─ reason
                                ├─ category (NEW)
                                ├─ project_id (NEW)
                                ├─ approval_chain (NEW)
                                └─ status

                              team_notifications
                                ├─ notification_id
                                ├─ team_id
                                ├─ recipient_user_ids
                                ├─ recipient_roles (NEW)
                                ├─ type
                                ├─ channels (NEW)
                                └─ read_by

                              team_audit_trail (NEW)
                                ├─ audit_id
                                ├─ team_id
                                ├─ actor_user_id
                                ├─ event_type
                                ├─ changes
                                └─ timestamp

                              team_webhooks (NEW)
                                ├─ webhook_id
                                ├─ team_id
                                ├─ url
                                ├─ events
                                └─ health_status
```

---

## Technology Stack

```
┌─────────────────────────────────────────────────────┐
│                 FRONTEND LAYER                      │
│  • Web App (React/Vue/Angular)                     │
│  • Mobile App (Flutter/React Native)               │
│  • Third-party Integrations                        │
└─────────────────────────────────────────────────────┘
                       │
                       │ HTTPS/REST
                       │
┌─────────────────────────────────────────────────────┐
│                  API LAYER                          │
│  • FastAPI (Python 3.11+)                          │
│  • Pydantic (Data Validation)                      │
│  • JWT Authentication                               │
│  • OpenAPI/Swagger Documentation                   │
└─────────────────────────────────────────────────────┘
                       │
                       │
┌─────────────────────────────────────────────────────┐
│              BUSINESS LOGIC LAYER                   │
│  • Manager Classes (Team, RBAC, Audit, etc.)      │
│  • Service Layer                                    │
│  • Error Handling & Recovery                       │
│  • Monitoring & Observability                      │
└─────────────────────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
┌─────────▼───┐  ┌────▼─────┐  ┌──▼──────────┐
│  MongoDB    │  │  Redis   │  │  External   │
│             │  │          │  │  Services   │
│ • Teams     │  │ • Cache  │  │             │
│ • Members   │  │ • Perms  │  │ • Email     │
│ • Roles     │  │ • Rate   │  │ • Slack     │
│ • Projects  │  │   Limit  │  │ • Webhooks  │
│ • Audit     │  │ • Session│  │             │
└─────────────┘  └──────────┘  └─────────────┘
```

---

## Deployment Architecture (Production)

```
┌─────────────────────────────────────────────────────┐
│                   LOAD BALANCER                     │
│              (Nginx / AWS ALB / GCP LB)             │
└────────────┬────────────────────────┬───────────────┘
             │                        │
    ┌────────▼────────┐      ┌───────▼────────┐
    │  API Server 1   │      │  API Server 2  │
    │  (FastAPI)      │      │  (FastAPI)     │
    └────────┬────────┘      └───────┬────────┘
             │                        │
             └────────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │   MongoDB Cluster     │
              │   (Replica Set)       │
              │                       │
              │  Primary ──┬── Sec.  │
              │            │          │
              │            └── Sec.  │
              └───────────────────────┘
                          │
              ┌───────────▼───────────┐
              │   Redis Cluster       │
              │   (High Availability) │
              │                       │
              │  Primary ─── Replica  │
              └───────────────────────┘
                          │
              ┌───────────▼───────────┐
              │  External Services    │
              │                       │
              │  • Email (SendGrid)   │
              │  • Slack API          │
              │  • Monitoring (DD)    │
              └───────────────────────┘
```

---

**Document Version**: 1.0  
**Last Updated**: October 18, 2025  
**Purpose**: Visual architecture reference
