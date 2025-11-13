# IPAM Backend Enhancements - Complete API Reference

## Overview

This document provides complete API documentation for the IPAM backend enhancements, including:
- Reservation Management
- Shareable Links
- User Preferences & Saved Filters
- Notifications & Notification Rules
- Dashboard Statistics
- Capacity Forecasting & Trends
- Webhooks
- Bulk Operations

All endpoints require JWT authentication unless otherwise specified.

**Base URL**: `/api/v1/ipam`

**Authentication**: Include JWT token in Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

---

## Table of Contents

1. [Reservation Management](#reservation-management)
2. [Shareable Links](#shareable-links)
3. [User Preferences](#user-preferences)
4. [Saved Filters](#saved-filters)
5. [Notifications](#notifications)
6. [Notification Rules](#notification-rules)
7. [Dashboard Statistics](#dashboard-statistics)
8. [Capacity Forecasting](#capacity-forecasting)
9. [Allocation Trends](#allocation-trends)
10. [Webhooks](#webhooks)
11. [Bulk Operations](#bulk-operations)
12. [Enhanced Search](#enhanced-search)

---

## Reservation Management

### Create Reservation

Reserve a specific IP address or region for future use.

**Endpoint**: `POST /ipam/reservations`

**Required Permission**: `ipam:allocate`

**Rate Limit**: 100 requests per hour

**Request Body**:
```json
{
  "resource_type": "region",  // "region" or "host"
  "x_octet": 5,
  "y_octet": 23,
  "z_octet": 100,  // Required for host reservations, null for region
  "reason": "Reserved for Q1 2026 expansion",
  "expires_in_days": 30  // Optional, max 90 days
}
```

**Response** (201 Created):
```json
{
  "reservation_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "resource_type": "region",
  "x_octet": 5,
  "y_octet": 23,
  "z_octet": null,
  "reserved_address": "10.5.23.0/24",
  "reason": "Reserved for Q1 2026 expansion",
  "status": "active",
  "expires_at": "2025-12-12T10:00:00Z",
  "created_at": "2025-11-12T10:00:00Z",
  "created_by": "john.doe"
}
```

**Error Responses**:
- **400 Bad Request**: Invalid parameters or validation error
- **409 Conflict**: IP address already allocated or reserved
- **429 Too Many Requests**: Rate limit exceeded

### List Reservations

Get all your reservations with optional filtering.

**Endpoint**: `GET /ipam/reservations`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `status` (optional): Filter by status (active, expired, converted)
- `resource_type` (optional): Filter by type (region, host)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 100)

**Response** (200 OK):
```json
{
  "results": [
    {
      "reservation_id": "550e8400-e29b-41d4-a716-446655440000",
      "resource_type": "region",
      "reserved_address": "10.5.23.0/24",
      "status": "active",
      "expires_at": "2025-12-12T10:00:00Z",
      "created_at": "2025-11-12T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 1,
    "total_pages": 1
  }
}
```

### Get Reservation Details

Get detailed information about a specific reservation.

**Endpoint**: `GET /ipam/reservations/{reservation_id}`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "reservation_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "resource_type": "region",
  "reserved_address": "10.5.23.0/24",
  "reason": "Reserved for Q1 2026 expansion",
  "status": "active",
  "expires_at": "2025-12-12T10:00:00Z",
  "created_at": "2025-11-12T10:00:00Z",
  "metadata": {}
}
```

### Convert Reservation to Allocation

Convert a reservation into an actual region or host allocation.

**Endpoint**: `POST /ipam/reservations/{reservation_id}/convert`

**Required Permission**: `ipam:allocate`

**Request Body** (for region):
```json
{
  "region_name": "Production Network",
  "description": "Primary production environment",
  "owner": "DevOps Team",
  "tags": {
    "environment": "production",
    "department": "engineering"
  }
}
```

**Request Body** (for host):
```json
{
  "hostname": "db-server-01",
  "device_type": "VM",
  "os_type": "Ubuntu 22.04",
  "application": "PostgreSQL",
  "owner": "Database Team"
}
```

**Response** (201 Created):
```json
{
  "resource_id": "770e8400-e29b-41d4-a716-446655440002",
  "resource_type": "region",
  "allocation": {
    "region_id": "770e8400-e29b-41d4-a716-446655440002",
    "region_name": "Production Network",
    "cidr": "10.5.23.0/24",
    "status": "Active",
    "created_at": "2025-11-12T11:00:00Z"
  }
}
```

### Delete Reservation

Cancel a reservation before it expires.

**Endpoint**: `DELETE /ipam/reservations/{reservation_id}`

**Required Permission**: `ipam:release`

**Response** (204 No Content)

---

## Shareable Links

### Create Shareable Link

Generate a public link to share IPAM resources (read-only, no auth required).

**Endpoint**: `POST /ipam/shares`

**Required Permission**: `ipam:read`

**Request Body**:
```json
{
  "resource_type": "region",  // "country", "region", or "host"
  "resource_id": "770e8400-e29b-41d4-a716-446655440002",
  "expires_in_days": 30,  // Max 90 days
  "description": "Sharing production network overview"
}
```

**Response** (201 Created):
```json
{
  "share_id": "880e8400-e29b-41d4-a716-446655440003",
  "share_token": "abc123def456ghi789",
  "share_url": "https://api.example.com/ipam/shares/abc123def456ghi789",
  "resource_type": "region",
  "resource_id": "770e8400-e29b-41d4-a716-446655440002",
  "view_count": 0,
  "expires_at": "2025-12-12T10:00:00Z",
  "created_at": "2025-11-12T10:00:00Z",
  "is_active": true
}
```

### Access Shared Resource

Access a shared resource using the share token (no authentication required).

**Endpoint**: `GET /ipam/shares/{share_token}`

**Authentication**: Not required

**Response** (200 OK):
```json
{
  "resource_type": "region",
  "resource_data": {
    "region_name": "Production Network",
    "cidr": "10.5.23.0/24",
    "status": "Active",
    "utilization": 45.2,
    "host_count": 115,
    "tags": {
      "environment": "production"
    }
  },
  "shared_by": "john.doe",
  "created_at": "2025-11-12T10:00:00Z"
}
```

**Note**: Sensitive information (owner details, internal IDs, comments) is excluded from shared views.

### List Your Shares

Get all shareable links you've created.

**Endpoint**: `GET /ipam/shares`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "shares": [
    {
      "share_id": "880e8400-e29b-41d4-a716-446655440003",
      "resource_type": "region",
      "resource_id": "770e8400-e29b-41d4-a716-446655440002",
      "share_url": "https://api.example.com/ipam/shares/abc123def456ghi789",
      "view_count": 12,
      "last_accessed": "2025-11-12T15:30:00Z",
      "expires_at": "2025-12-12T10:00:00Z",
      "is_active": true
    }
  ]
}
```

### Revoke Share

Immediately invalidate a shareable link.

**Endpoint**: `DELETE /ipam/shares/{share_id}`

**Required Permission**: `ipam:release`

**Response** (204 No Content)

---

## User Preferences

### Get User Preferences

Retrieve your stored preferences.

**Endpoint**: `GET /ipam/preferences`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "saved_filters": [],
  "dashboard_layout": {
    "widgets": ["utilization", "recent_activity", "top_countries"],
    "refresh_interval": 300
  },
  "notification_settings": {
    "email_enabled": false,
    "in_app_enabled": true,
    "severity_threshold": "warning"
  },
  "theme_preference": "pacific-blue"
}
```

### Update User Preferences

Update preferences (merges with existing values).

**Endpoint**: `PUT /ipam/preferences`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "dashboard_layout": {
    "widgets": ["utilization", "forecast", "notifications"],
    "refresh_interval": 600
  },
  "theme_preference": "ocean-depths"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "updated_at": "2025-11-12T10:30:00Z"
}
```

**Note**: Maximum preference data size is 50KB.

---

## Saved Filters

### Save Search Filter

Save frequently used search criteria (max 50 filters per user).

**Endpoint**: `POST /ipam/preferences/filters`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "name": "High Utilization Regions",
  "criteria": {
    "resource_type": "region",
    "utilization_min": 80,
    "status": "Active",
    "tags": {
      "environment": "production"
    }
  }
}
```

**Response** (201 Created):
```json
{
  "filter_id": "filter_990e8400-e29b-41d4-a716-446655440004",
  "name": "High Utilization Regions",
  "created_at": "2025-11-12T10:00:00Z"
}
```

### List Saved Filters

Get all your saved filters.

**Endpoint**: `GET /ipam/preferences/filters`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "filters": [
    {
      "filter_id": "filter_990e8400-e29b-41d4-a716-446655440004",
      "name": "High Utilization Regions",
      "criteria": {
        "resource_type": "region",
        "utilization_min": 80
      },
      "created_at": "2025-11-12T10:00:00Z"
    }
  ]
}
```

### Delete Saved Filter

Remove a saved filter.

**Endpoint**: `DELETE /ipam/preferences/filters/{filter_id}`

**Required Permission**: `ipam:update`

**Response** (204 No Content)

---

## Notifications

### List Notifications

Get your notifications with optional filtering.

**Endpoint**: `GET /ipam/notifications`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `is_read` (optional): Filter by read status (true/false)
- `severity` (optional): Filter by severity (info, warning, critical)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 100)

**Response** (200 OK):
```json
{
  "notifications": [
    {
      "notification_id": "aa0e8400-e29b-41d4-a716-446655440005",
      "notification_type": "capacity_warning",
      "severity": "warning",
      "message": "Region 10.5.23.0/24 is at 85% capacity",
      "resource_type": "region",
      "resource_id": "770e8400-e29b-41d4-a716-446655440002",
      "resource_link": "/ipam/regions/770e8400-e29b-41d4-a716-446655440002",
      "is_read": false,
      "created_at": "2025-11-12T09:00:00Z"
    }
  ],
  "unread_count": 3,
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 3
  }
}
```

### Get Unread Notifications

Quick endpoint to check unread count and recent notifications.

**Endpoint**: `GET /ipam/notifications/unread`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "unread_count": 3,
  "recent": [
    {
      "notification_id": "aa0e8400-e29b-41d4-a716-446655440005",
      "severity": "warning",
      "message": "Region 10.5.23.0/24 is at 85% capacity",
      "created_at": "2025-11-12T09:00:00Z"
    }
  ]
}
```

### Mark Notification as Read

Mark a notification as read.

**Endpoint**: `PATCH /ipam/notifications/{notification_id}`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "is_read": true
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "read_at": "2025-11-12T10:00:00Z"
}
```

### Dismiss Notification

Delete a notification.

**Endpoint**: `DELETE /ipam/notifications/{notification_id}`

**Required Permission**: `ipam:update`

**Response** (204 No Content)

**Note**: Notifications older than 90 days are automatically deleted.

---

## Notification Rules

### Create Notification Rule

Set up automatic notifications based on conditions.

**Endpoint**: `POST /ipam/notifications/rules`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "rule_name": "High Utilization Alert",
  "conditions": {
    "utilization_threshold": 80,
    "resource_type": "region",
    "resource_ids": ["770e8400-e29b-41d4-a716-446655440002"]
  },
  "notification_channels": ["in_app"],
  "severity": "warning"
}
```

**Response** (201 Created):
```json
{
  "rule_id": "bb0e8400-e29b-41d4-a716-446655440006",
  "rule_name": "High Utilization Alert",
  "is_active": true,
  "created_at": "2025-11-12T10:00:00Z"
}
```

### List Notification Rules

Get all your notification rules.

**Endpoint**: `GET /ipam/notifications/rules`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "rules": [
    {
      "rule_id": "bb0e8400-e29b-41d4-a716-446655440006",
      "rule_name": "High Utilization Alert",
      "conditions": {
        "utilization_threshold": 80,
        "resource_type": "region"
      },
      "notification_channels": ["in_app"],
      "is_active": true,
      "last_triggered": "2025-11-12T09:00:00Z",
      "created_at": "2025-11-12T08:00:00Z"
    }
  ]
}
```

### Update Notification Rule

Modify an existing rule.

**Endpoint**: `PATCH /ipam/notifications/rules/{rule_id}`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "is_active": false,
  "conditions": {
    "utilization_threshold": 90
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "updated_at": "2025-11-12T10:30:00Z"
}
```

### Delete Notification Rule

Remove a notification rule.

**Endpoint**: `DELETE /ipam/notifications/rules/{rule_id}`

**Required Permission**: `ipam:update`

**Response** (204 No Content)

---

## Dashboard Statistics

### Get Dashboard Overview

Get comprehensive dashboard statistics (cached for 5 minutes).

**Endpoint**: `GET /ipam/statistics/dashboard`

**Required Permission**: `ipam:read`

**Response Time**: < 500ms

**Response** (200 OK):
```json
{
  "total_countries": 15,
  "total_regions": 234,
  "total_hosts": 5678,
  "overall_utilization": 62.5,
  "top_countries": [
    {
      "country_code": "US",
      "country_name": "United States",
      "region_count": 45,
      "host_count": 1234,
      "utilization": 75.2
    },
    {
      "country_code": "GB",
      "country_name": "United Kingdom",
      "region_count": 32,
      "host_count": 890,
      "utilization": 68.5
    }
  ],
  "recent_activity_count": 127,
  "capacity_warnings": 3,
  "generated_at": "2025-11-12T10:00:00Z"
}
```

---

## Capacity Forecasting

### Get Capacity Forecast

Get predictive capacity forecast for a resource (cached for 24 hours).

**Endpoint**: `GET /ipam/statistics/forecast/{resource_type}/{resource_id}`

**Required Permission**: `ipam:read`

**Response Time**: < 1s

**Path Parameters**:
- `resource_type`: "country", "region", or "host"
- `resource_id`: Resource identifier

**Response** (200 OK):
```json
{
  "resource_type": "region",
  "resource_id": "770e8400-e29b-41d4-a716-446655440002",
  "current_utilization": 85.2,
  "daily_allocation_rate": 2.3,
  "estimated_exhaustion_date": "2025-12-15T00:00:00Z",
  "days_until_exhaustion": 33,
  "confidence_level": "high",
  "recommendation": "Consider expanding capacity within 2 weeks",
  "historical_data_points": 87,
  "forecast_generated_at": "2025-11-12T10:00:00Z"
}
```

**Response** (Insufficient Data):
```json
{
  "resource_type": "region",
  "resource_id": "770e8400-e29b-41d4-a716-446655440002",
  "status": "insufficient_data",
  "message": "Need at least 10 allocations over 7 days for accurate forecast",
  "current_data_points": 3,
  "required_data_points": 10
}
```

**Confidence Levels**:
- `high`: 50+ data points over 90 days
- `medium`: 20-49 data points
- `low`: 10-19 data points

---

## Allocation Trends

### Get Allocation Trends

Get time-series data for allocation trends.

**Endpoint**: `GET /ipam/statistics/trends`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `group_by`: Grouping interval (day, week, month)
- `start_date`: Start date (ISO 8601)
- `end_date`: End date (ISO 8601)
- `resource_type` (optional): Filter by type (country, region, host)
- `country_code` (optional): Filter by country

**Response** (200 OK):
```json
{
  "time_series": [
    {
      "timestamp": "2025-11-01T00:00:00Z",
      "allocations": 23,
      "releases": 5,
      "net_growth": 18
    },
    {
      "timestamp": "2025-11-02T00:00:00Z",
      "allocations": 31,
      "releases": 8,
      "net_growth": 23
    }
  ],
  "summary": {
    "total_allocations": 287,
    "total_releases": 64,
    "net_growth": 223,
    "average_daily_rate": 23.9,
    "period_start": "2025-11-01T00:00:00Z",
    "period_end": "2025-11-12T00:00:00Z"
  }
}
```

---

## Webhooks

### Create Webhook

Register a webhook to receive event notifications.

**Endpoint**: `POST /ipam/webhooks`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "webhook_url": "https://your-app.com/webhooks/ipam",
  "events": ["region.created", "host.allocated", "capacity.warning"],
  "description": "Production monitoring webhook"
}
```

**Response** (201 Created):
```json
{
  "webhook_id": "cc0e8400-e29b-41d4-a716-446655440007",
  "webhook_url": "https://your-app.com/webhooks/ipam",
  "secret_key": "whsec_abc123def456ghi789jkl012",
  "events": ["region.created", "host.allocated", "capacity.warning"],
  "is_active": true,
  "created_at": "2025-11-12T10:00:00Z"
}
```

**Important**: Save the `secret_key` - it's used to verify webhook signatures and won't be shown again.

### Webhook Events

Supported event types:
- `region.created`: New region allocated
- `region.updated`: Region metadata updated
- `region.retired`: Region retired
- `host.allocated`: New host allocated
- `host.updated`: Host metadata updated
- `host.released`: Host released
- `capacity.warning`: Resource approaching capacity (80%+)
- `capacity.critical`: Resource at critical capacity (95%+)

### Webhook Payload Format

When an event occurs, you'll receive a POST request:

**Headers**:
```
Content-Type: application/json
X-IPAM-Signature: sha256=abc123...
X-IPAM-Event: region.created
```

**Payload**:
```json
{
  "event_type": "region.created",
  "timestamp": "2025-11-12T10:30:00Z",
  "user_id": "user_123",
  "data": {
    "region_id": "770e8400-e29b-41d4-a716-446655440002",
    "region_name": "Production Network",
    "cidr": "10.5.23.0/24",
    "country_code": "US",
    "status": "Active"
  }
}
```

### Verify Webhook Signature

Verify the webhook signature to ensure authenticity:

**Python Example**:
```python
import hmac
import hashlib

def verify_webhook_signature(payload_body, signature_header, secret_key):
    expected_signature = hmac.new(
        secret_key.encode(),
        payload_body.encode(),
        hashlib.sha256
    ).hexdigest()
    
    received_signature = signature_header.replace('sha256=', '')
    return hmac.compare_digest(expected_signature, received_signature)
```

### List Webhooks

Get all your registered webhooks.

**Endpoint**: `GET /ipam/webhooks`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "webhooks": [
    {
      "webhook_id": "cc0e8400-e29b-41d4-a716-446655440007",
      "webhook_url": "https://your-app.com/webhooks/ipam",
      "events": ["region.created", "host.allocated"],
      "is_active": true,
      "last_delivery": "2025-11-12T10:30:00Z",
      "failure_count": 0,
      "created_at": "2025-11-12T10:00:00Z"
    }
  ]
}
```

### Get Webhook Delivery History

View delivery attempts and their results.

**Endpoint**: `GET /ipam/webhooks/{webhook_id}/deliveries`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 100)

**Response** (200 OK):
```json
{
  "deliveries": [
    {
      "delivery_id": "dd0e8400-e29b-41d4-a716-446655440008",
      "event_type": "region.created",
      "status_code": 200,
      "response_time_ms": 145,
      "attempt_number": 1,
      "delivered_at": "2025-11-12T10:30:00Z",
      "error_message": null
    },
    {
      "delivery_id": "ee0e8400-e29b-41d4-a716-446655440009",
      "event_type": "host.allocated",
      "status_code": 500,
      "response_time_ms": 2340,
      "attempt_number": 3,
      "delivered_at": "2025-11-12T09:15:00Z",
      "error_message": "Connection timeout after 3 retries"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 2
  }
}
```

### Delete Webhook

Remove a webhook registration.

**Endpoint**: `DELETE /ipam/webhooks/{webhook_id}`

**Required Permission**: `ipam:update`

**Response** (204 No Content)

**Webhook Delivery Behavior**:
- Retries: 3 attempts with exponential backoff (2s, 4s, 8s)
- Timeout: 10 seconds per attempt
- Auto-disable: After 10 consecutive failures
- Signature: HMAC-SHA256 in X-IPAM-Signature header

---

## Bulk Operations

### Bulk Tag Update

Update tags for multiple resources at once (up to 500 items).

**Endpoint**: `POST /ipam/bulk/tags`

**Required Permission**: `ipam:update`

**Rate Limit**: 10 operations per hour per user

**Request Body**:
```json
{
  "resource_type": "region",
  "resource_ids": [
    "770e8400-e29b-41d4-a716-446655440002",
    "880e8400-e29b-41d4-a716-446655440003"
  ],
  "operation": "add",
  "tags": {
    "environment": "production",
    "managed_by": "terraform"
  }
}
```

**Operations**:
- `add`: Add tags (merge with existing)
- `remove`: Remove specific tags
- `replace`: Replace all tags

**Response** (200 OK - Synchronous for ≤100 items):
```json
{
  "job_id": null,
  "total_requested": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "resource_id": "770e8400-e29b-41d4-a716-446655440002",
      "success": true,
      "message": "Tags updated successfully"
    },
    {
      "resource_id": "880e8400-e29b-41d4-a716-446655440003",
      "success": true,
      "message": "Tags updated successfully"
    }
  ]
}
```

**Response** (202 Accepted - Asynchronous for >100 items):
```json
{
  "job_id": "ff0e8400-e29b-41d4-a716-446655440010",
  "status": "pending",
  "total_requested": 250,
  "message": "Bulk operation queued for processing",
  "status_url": "/ipam/bulk/jobs/ff0e8400-e29b-41d4-a716-446655440010"
}
```

### Get Bulk Job Status

Check the status of an asynchronous bulk operation.

**Endpoint**: `GET /ipam/bulk/jobs/{job_id}`

**Required Permission**: `ipam:read`

**Response** (200 OK - In Progress):
```json
{
  "job_id": "ff0e8400-e29b-41d4-a716-446655440010",
  "status": "processing",
  "progress": {
    "total": 250,
    "processed": 127,
    "successful": 125,
    "failed": 2
  },
  "created_at": "2025-11-12T10:00:00Z",
  "completed_at": null
}
```

**Response** (200 OK - Completed):
```json
{
  "job_id": "ff0e8400-e29b-41d4-a716-446655440010",
  "status": "completed",
  "progress": {
    "total": 250,
    "processed": 250,
    "successful": 248,
    "failed": 2
  },
  "results": [
    {
      "resource_id": "770e8400-e29b-41d4-a716-446655440002",
      "success": true
    },
    {
      "resource_id": "invalid_id",
      "success": false,
      "error": "Resource not found"
    }
  ],
  "created_at": "2025-11-12T10:00:00Z",
  "completed_at": "2025-11-12T10:05:23Z"
}
```

**Job Expiration**: Bulk job results are retained for 7 days.

---

## Enhanced Search

### Advanced Search

Search allocations with enhanced capabilities including AND/OR logic, CIDR ranges, and multi-field sorting.

**Endpoint**: `GET /ipam/search`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `ip_address` (optional): Exact or partial IP match
- `cidr` (optional): CIDR range match (e.g., "10.5.0.0/16")
- `ip_range` (optional): IP range query (e.g., "10.5.23.1-10.5.23.50")
- `hostname` (optional): Partial hostname match
- `region_name` (optional): Partial region name match
- `tags` (optional): Tag matching with AND/OR logic (JSON)
- `sort_by` (optional): Multi-field sorting (e.g., "country:asc,utilization:desc")
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 50, max: 100)

**Tag Matching Examples**:

AND logic (all tags must match):
```json
{
  "logic": "AND",
  "tags": {
    "environment": "production",
    "tier": "1"
  }
}
```

OR logic (any tag must match):
```json
{
  "logic": "OR",
  "tags": {
    "environment": "production",
    "environment": "staging"
  }
}
```

**Response** (200 OK):
```json
{
  "results": [
    {
      "type": "region",
      "region_id": "770e8400-e29b-41d4-a716-446655440002",
      "cidr": "10.5.23.0/24",
      "region_name": "Production Network",
      "country": "United States",
      "utilization": 85.2,
      "relevance_score": 0.95
    },
    {
      "type": "host",
      "host_id": "host-123",
      "ip_address": "10.5.23.45",
      "hostname": "web-server-01",
      "region_name": "Production Network",
      "relevance_score": 0.87
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 2
  }
}
```

**Search Result Caching**: Common search queries are cached for 5 minutes.

---

## Error Responses

### Standard Error Format

All errors follow a consistent format:

```json
{
  "success": false,
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional context"
  }
}
```

### Common HTTP Status Codes

| Status Code | Meaning | Example |
|-------------|---------|---------|
| 200 | Success | Resource retrieved successfully |
| 201 | Created | Resource created successfully |
| 202 | Accepted | Async operation queued |
| 204 | No Content | Resource deleted successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict or capacity exhausted |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

### Common Error Codes

**Validation Errors**:
```json
{
  "success": false,
  "error": "validation_error",
  "message": "Invalid request parameters",
  "details": {
    "x_octet": "Must be between 0 and 255",
    "expires_in_days": "Must be between 1 and 90"
  }
}
```

**Resource Not Found**:
```json
{
  "success": false,
  "error": "not_found",
  "message": "Reservation not found"
}
```

**Conflict Errors**:
```json
{
  "success": false,
  "error": "conflict",
  "message": "IP address 10.5.23.100 is already allocated"
}
```

**Rate Limit Errors**:
```json
{
  "success": false,
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "details": {
    "retry_after": 60,
    "limit": "10 requests per hour"
  }
}
```

---

## Best Practices

### 1. Reservation Workflow

Use reservations for planned allocations:
1. Create reservation with expiration date
2. Review and approve allocation plan
3. Convert reservation to allocation when ready
4. Reservation auto-expires if not converted

### 2. Notification Strategy

Set up proactive monitoring:
- Create rules for capacity warnings (80%+ utilization)
- Monitor critical resources with specific rules
- Use severity levels appropriately (info, warning, critical)
- Review and dismiss notifications regularly

### 3. Webhook Integration

Implement robust webhook handling:
- Always verify HMAC signatures
- Implement retry logic for failed deliveries
- Log all webhook events for debugging
- Monitor webhook delivery history
- Handle webhook failures gracefully

### 4. Bulk Operations

Optimize bulk updates:
- Use bulk endpoints for operations on >10 items
- Monitor job status for async operations
- Handle partial failures appropriately
- Respect rate limits (10 operations per hour)

### 5. Caching Strategy

Leverage caching for performance:
- Dashboard stats: 5-minute cache
- Forecasts: 24-hour cache
- Search results: 5-minute cache
- Use cache headers to determine freshness

### 6. Search Optimization

Improve search performance:
- Use specific filters to narrow results
- Leverage saved filters for common queries
- Use CIDR ranges instead of individual IPs
- Sort by relevance score for best matches

### 7. Capacity Planning

Proactive capacity management:
- Monitor forecasts regularly
- Set up notification rules for capacity warnings
- Review trends to identify growth patterns
- Plan expansions before reaching 80% utilization

---

## Rate Limits

| Operation | Limit | Period |
|-----------|-------|--------|
| Reservation creation | 100 | 1 hour |
| Share creation | 100 | 1 hour |
| Notification rule creation | 50 | 1 hour |
| Webhook creation | 20 | 1 hour |
| Bulk operations | 10 | 1 hour |
| Query operations | 500 | 1 hour |

**Rate Limit Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699876543
```

---

## Quotas and Limits

| Resource | Limit | Notes |
|----------|-------|-------|
| Saved filters per user | 50 | Oldest deleted when exceeded |
| Preference data size | 50 KB | Per user |
| Share expiration | 90 days | Maximum |
| Reservation expiration | 90 days | Maximum |
| Notification retention | 90 days | Auto-deleted after |
| Bulk operation items | 500 | Per request |
| Webhook events per hook | 10 | Maximum subscriptions |
| Webhook delivery retries | 3 | With exponential backoff |
| Bulk job retention | 7 days | Results available |

---

## Migration Guide

### Backward Compatibility

All enhancement endpoints are additive and do not break existing functionality:
- Existing endpoints remain unchanged
- No changes to existing data models
- All new features are opt-in
- Existing integrations continue to work

### Adopting New Features

**Phase 1: Read-Only Features**
1. Start with dashboard statistics
2. Explore capacity forecasting
3. Review allocation trends

**Phase 2: User Preferences**
1. Implement saved filters
2. Configure notification preferences
3. Customize dashboard layout

**Phase 3: Notifications**
1. Create notification rules
2. Monitor in-app notifications
3. Integrate with external systems

**Phase 4: Advanced Features**
1. Implement reservation workflow
2. Set up webhooks for automation
3. Use bulk operations for efficiency

---

## Support and Resources

- **API Documentation**: `/docs` (Swagger UI)
- **OpenAPI Schema**: `/openapi.json`
- **GitHub Repository**: https://github.com/rohanbatrain/second_brain_database
- **Issue Tracker**: https://github.com/rohanbatrain/second_brain_database/issues

For questions or support, please open an issue on GitHub.

---

**Document Version**: 1.0  
**Last Updated**: November 13, 2025  
**Status**: Complete
