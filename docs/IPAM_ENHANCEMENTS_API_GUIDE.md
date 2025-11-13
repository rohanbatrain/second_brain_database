# IPAM Backend Enhancements - API Usage Guide

## Overview

This guide provides practical examples for using the IPAM backend enhancement APIs. All endpoints require authentication via JWT token or permanent API token.

**Base URL**: `https://api.example.com/ipam`

**Authentication**: Include JWT token in Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

---

## Table of Contents

1. [Reservation Management](#1-reservation-management)
2. [Shareable Links](#2-shareable-links)
3. [User Preferences](#3-user-preferences)
4. [Saved Filters](#4-saved-filters)
5. [Notifications](#5-notifications)
6. [Notification Rules](#6-notification-rules)
7. [Dashboard Statistics](#7-dashboard-statistics)
8. [Capacity Forecasting](#8-capacity-forecasting)
9. [Allocation Trends](#9-allocation-trends)
10. [Webhooks](#10-webhooks)
11. [Bulk Operations](#11-bulk-operations)
12. [Error Handling](#12-error-handling)

---

## 1. Reservation Management

### 1.1 Create a Region Reservation

Reserve a region (10.X.Y.0/24) for future use.

**Endpoint**: `POST /ipam/reservations`

**Request**:
```bash
curl -X POST https://api.example.com/ipam/reservations \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "region",
    "x_octet": 5,
    "y_octet": 23,
    "reason": "Reserved for Q1 2026 expansion",
    "expires_in_days": 30
  }'
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
  "created_by": "john.doe",
  "metadata": {}
}
```

### 1.2 Create a Host Reservation

Reserve a specific host IP (10.X.Y.Z).

**Endpoint**: `POST /ipam/reservations`

**Request**:
```bash
curl -X POST https://api.example.com/ipam/reservations \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "host",
    "x_octet": 5,
    "y_octet": 23,
    "z_octet": 100,
    "reason": "Reserved for production database server",
    "expires_in_days": 7
  }'
```

**Response** (201 Created):
```json
{
  "reservation_id": "660e8400-e29b-41d4-a716-446655440001",
  "resource_type": "host",
  "reserved_address": "10.5.23.100",
  "status": "active",
  "expires_at": "2025-11-19T10:00:00Z"
}
```

### 1.3 List Reservations

Get all your reservations with optional filtering.

**Endpoint**: `GET /ipam/reservations`

**Query Parameters**:
- `status`: Filter by status (active, expired, converted)
- `resource_type`: Filter by type (region, host)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 50, max: 100)

**Request**:
```bash
curl -X GET "https://api.example.com/ipam/reservations?status=active&page=1&page_size=20" \
  -H "Authorization: Bearer <token>"
```

**Response** (200 OK):
```json
{
  "results": [
    {
      "reservation_id": "550e8400-e29b-41d4-a716-446655440000",
      "resource_type": "region",
      "reserved_address": "10.5.23.0/24",
      "status": "active",
      "expires_at": "2025-12-12T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_count": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

### 1.4 Convert Reservation to Allocation

Convert a reservation into an actual region or host allocation.

**Endpoint**: `POST /ipam/reservations/{reservation_id}/convert`

**Request** (Region):
```bash
curl -X POST https://api.example.com/ipam/reservations/550e8400-e29b-41d4-a716-446655440000/convert \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "region_name": "Production Network",
    "description": "Primary production environment",
    "owner": "DevOps Team",
    "tags": {
      "environment": "production",
      "department": "engineering"
    }
  }'
```

**Response** (201 Created):
```json
{
  "resource_id": "770e8400-e29b-41d4-a716-446655440002",
  "resource_type": "region",
  "allocation": {
    "region_id": "770e8400-e29b-41d4-a716-446655440002",
    "region_name": "Production Network",
    "x_octet": 5,
    "y_octet": 23,
    "cidr": "10.5.23.0/24",
    "status": "Active",
    "created_at": "2025-11-12T11:00:00Z"
  }
}
```

### 1.5 Delete Reservation

Cancel a reservation before it expires.

**Endpoint**: `DELETE /ipam/reservations/{reservation_id}`

**Request**:
```bash
curl -X DELETE https://api.example.com/ipam/reservations/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <token>"
```

**Response** (204 No Content)

---

## 2. Shareable Links

### 2.1 Create a Shareable Link

Generate a public link to share IPAM resources (read-only, no auth required).

**Endpoint**: `POST /ipam/shares`

**Request**:
```bash
curl -X POST https://api.example.com/ipam/shares \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "region",
    "resource_id": "770e8400-e29b-41d4-a716-446655440002",
    "expires_in_days": 30,
    "description": "Sharing production network overview"
  }'
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

### 2.2 Access a Shared Resource

Access a shared resource using the share token (no authentication required).

**Endpoint**: `GET /ipam/shares/{share_token}`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/shares/abc123def456ghi789
```

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

### 2.3 List Your Shares

Get all shareable links you've created.

**Endpoint**: `GET /ipam/shares`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/shares \
  -H "Authorization: Bearer <token>"
```

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

### 2.4 Revoke a Share

Immediately invalidate a shareable link.

**Endpoint**: `DELETE /ipam/shares/{share_id}`

**Request**:
```bash
curl -X DELETE https://api.example.com/ipam/shares/880e8400-e29b-41d4-a716-446655440003 \
  -H "Authorization: Bearer <token>"
```

**Response** (204 No Content)

---

## 3. User Preferences

### 3.1 Get User Preferences

Retrieve your stored preferences.

**Endpoint**: `GET /ipam/preferences`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/preferences \
  -H "Authorization: Bearer <token>"
```

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

### 3.2 Update User Preferences

Update preferences (merges with existing values).

**Endpoint**: `PUT /ipam/preferences`

**Request**:
```bash
curl -X PUT https://api.example.com/ipam/preferences \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "dashboard_layout": {
      "widgets": ["utilization", "forecast", "notifications"],
      "refresh_interval": 600
    },
    "theme_preference": "ocean-depths"
  }'
```

**Response** (200 OK):
```json
{
  "success": true,
  "updated_at": "2025-11-12T10:30:00Z"
}
```

---

## 4. Saved Filters

### 4.1 Save a Search Filter

Save frequently used search criteria.

**Endpoint**: `POST /ipam/preferences/filters`

**Request**:
```bash
curl -X POST https://api.example.com/ipam/preferences/filters \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Utilization Regions",
    "criteria": {
      "resource_type": "region",
      "utilization_min": 80,
      "status": "Active",
      "tags": {
        "environment": "production"
      }
    }
  }'
```

**Response** (201 Created):
```json
{
  "filter_id": "filter_990e8400-e29b-41d4-a716-446655440004",
  "name": "High Utilization Regions",
  "created_at": "2025-11-12T10:00:00Z"
}
```

### 4.2 List Saved Filters

Get all your saved filters.

**Endpoint**: `GET /ipam/preferences/filters`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/preferences/filters \
  -H "Authorization: Bearer <token>"
```

**Response** (200 OK):
```json
{
  "filters": [
    {
      "filter_id": "filter_990e8400-e29b-41d4-a716-446655440004",
      "name": "High Utilization Regions",
      "criteria": {
        "resource_type": "region",
        "utilization_min": 80,
        "status": "Active"
      },
      "created_at": "2025-11-12T10:00:00Z"
    }
  ]
}
```

### 4.3 Delete a Saved Filter

Remove a saved filter.

**Endpoint**: `DELETE /ipam/preferences/filters/{filter_id}`

**Request**:
```bash
curl -X DELETE https://api.example.com/ipam/preferences/filters/filter_990e8400-e29b-41d4-a716-446655440004 \
  -H "Authorization: Bearer <token>"
```

**Response** (204 No Content)

---

## 5. Notifications

### 5.1 List Notifications

Get your notifications with optional filtering.

**Endpoint**: `GET /ipam/notifications`

**Query Parameters**:
- `is_read`: Filter by read status (true/false)
- `severity`: Filter by severity (info, warning, critical)
- `page`: Page number
- `page_size`: Items per page

**Request**:
```bash
curl -X GET "https://api.example.com/ipam/notifications?is_read=false&severity=warning" \
  -H "Authorization: Bearer <token>"
```

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
    "total_count": 3,
    "total_pages": 1
  }
}
```

### 5.2 Get Unread Notifications

Quick endpoint to check unread count and recent notifications.

**Endpoint**: `GET /ipam/notifications/unread`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/notifications/unread \
  -H "Authorization: Bearer <token>"
```

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

### 5.3 Mark Notification as Read

Mark a notification as read.

**Endpoint**: `PATCH /ipam/notifications/{notification_id}`

**Request**:
```bash
curl -X PATCH https://api.example.com/ipam/notifications/aa0e8400-e29b-41d4-a716-446655440005 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "is_read": true
  }'
```

**Response** (200 OK):
```json
{
  "success": true,
  "read_at": "2025-11-12T10:00:00Z"
}
```

### 5.4 Dismiss Notification

Delete a notification.

**Endpoint**: `DELETE /ipam/notifications/{notification_id}`

**Request**:
```bash
curl -X DELETE https://api.example.com/ipam/notifications/aa0e8400-e29b-41d4-a716-446655440005 \
  -H "Authorization: Bearer <token>"
```

**Response** (204 No Content)

---

## 6. Notification Rules

### 6.1 Create Notification Rule

Set up automatic notifications based on conditions.

**Endpoint**: `POST /ipam/notifications/rules`

**Request**:
```bash
curl -X POST https://api.example.com/ipam/notifications/rules \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "High Utilization Alert",
    "conditions": {
      "utilization_threshold": 80,
      "resource_type": "region",
      "resource_ids": ["770e8400-e29b-41d4-a716-446655440002"]
    },
    "notification_channels": ["in_app"],
    "severity": "warning"
  }'
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

### 6.2 List Notification Rules

Get all your notification rules.

**Endpoint**: `GET /ipam/notifications/rules`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/notifications/rules \
  -H "Authorization: Bearer <token>"
```

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

### 6.3 Update Notification Rule

Modify an existing rule.

**Endpoint**: `PATCH /ipam/notifications/rules/{rule_id}`

**Request**:
```bash
curl -X PATCH https://api.example.com/ipam/notifications/rules/bb0e8400-e29b-41d4-a716-446655440006 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "is_active": false
  }'
```

**Response** (200 OK):
```json
{
  "success": true,
  "updated_at": "2025-11-12T10:30:00Z"
}
```

### 6.4 Delete Notification Rule

Remove a notification rule.

**Endpoint**: `DELETE /ipam/notifications/rules/{rule_id}`

**Request**:
```bash
curl -X DELETE https://api.example.com/ipam/notifications/rules/bb0e8400-e29b-41d4-a716-446655440006 \
  -H "Authorization: Bearer <token>"
```

**Response** (204 No Content)

---

## 7. Dashboard Statistics

### 7.1 Get Dashboard Overview

Get comprehensive dashboard statistics (cached for 5 minutes).

**Endpoint**: `GET /ipam/statistics/dashboard`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/statistics/dashboard \
  -H "Authorization: Bearer <token>"
```

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

## 8. Capacity Forecasting

### 8.1 Get Capacity Forecast

Get predictive capacity forecast for a resource (cached for 24 hours).

**Endpoint**: `GET /ipam/statistics/forecast/{resource_type}/{resource_id}`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/statistics/forecast/region/770e8400-e29b-41d4-a716-446655440002 \
  -H "Authorization: Bearer <token>"
```

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

---

## 9. Allocation Trends

### 9.1 Get Allocation Trends

Get time-series data for allocation trends.

**Endpoint**: `GET /ipam/statistics/trends`

**Query Parameters**:
- `group_by`: Grouping interval (day, week, month)
- `start_date`: Start date (ISO 8601)
- `end_date`: End date (ISO 8601)
- `resource_type`: Filter by type (country, region, host)
- `country_code`: Filter by country

**Request**:
```bash
curl -X GET "https://api.example.com/ipam/statistics/trends?group_by=day&start_date=2025-11-01&end_date=2025-11-12" \
  -H "Authorization: Bearer <token>"
```

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

## 10. Webhooks

### 10.1 Create Webhook

Register a webhook to receive event notifications.

**Endpoint**: `POST /ipam/webhooks`

**Request**:
```bash
curl -X POST https://api.example.com/ipam/webhooks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_url": "https://your-app.com/webhooks/ipam",
    "events": ["region.created", "host.allocated", "capacity.warning"],
    "description": "Production monitoring webhook"
  }'
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

### 10.2 Webhook Payload Example

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

### 10.3 Verify Webhook Signature

Verify the webhook signature to ensure authenticity:

**Python Example**:
```python
import hmac
import hashlib

def verify_webhook_signature(payload_body, signature_header, secret_key):
    """Verify IPAM webhook signature."""
    expected_signature = hmac.new(
        secret_key.encode(),
        payload_body.encode(),
        hashlib.sha256
    ).hexdigest()
    
    received_signature = signature_header.replace('sha256=', '')
    
    return hmac.compare_digest(expected_signature, received_signature)

# Usage
is_valid = verify_webhook_signature(
    payload_body=request.body,
    signature_header=request.headers['X-IPAM-Signature'],
    secret_key='whsec_abc123def456ghi789jkl012'
)
```

**Node.js Example**:
```javascript
const crypto = require('crypto');

function verifyWebhookSignature(payloadBody, signatureHeader, secretKey) {
  const expectedSignature = crypto
    .createHmac('sha256', secretKey)
    .update(payloadBody)
    .digest('hex');
  
  const receivedSignature = signatureHeader.replace('sha256=', '');
  
  return crypto.timingSafeEqual(
    Buffer.from(expectedSignature),
    Buffer.from(receivedSignature)
  );
}
```

### 10.4 List Webhooks

Get all your registered webhooks.

**Endpoint**: `GET /ipam/webhooks`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/webhooks \
  -H "Authorization: Bearer <token>"
```

**Response** (200 OK):
```json
{
  "webhooks": [
    {
      "webhook_id": "cc0e8400-e29b-41d4-a716-446655440007",
      "webhook_url": "https://your-app.com/webhooks/ipam",
      "events": ["region.created", "host.allocated", "capacity.warning"],
      "is_active": true,
      "last_delivery": "2025-11-12T10:30:00Z",
      "failure_count": 0,
      "created_at": "2025-11-12T10:00:00Z"
    }
  ]
}
```

### 10.5 Get Webhook Delivery History

View delivery attempts and their results.

**Endpoint**: `GET /ipam/webhooks/{webhook_id}/deliveries`

**Query Parameters**:
- `page`: Page number
- `page_size`: Items per page (default: 50)

**Request**:
```bash
curl -X GET "https://api.example.com/ipam/webhooks/cc0e8400-e29b-41d4-a716-446655440007/deliveries?page=1" \
  -H "Authorization: Bearer <token>"
```

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
    "total_count": 2,
    "total_pages": 1
  }
}
```

### 10.6 Delete Webhook

Remove a webhook registration.

**Endpoint**: `DELETE /ipam/webhooks/{webhook_id}`

**Request**:
```bash
curl -X DELETE https://api.example.com/ipam/webhooks/cc0e8400-e29b-41d4-a716-446655440007 \
  -H "Authorization: Bearer <token>"
```

**Response** (204 No Content)

---

## 11. Bulk Operations

### 11.1 Bulk Tag Update

Update tags for multiple resources at once (up to 500 items).

**Endpoint**: `POST /ipam/bulk/tags`

**Request**:
```bash
curl -X POST https://api.example.com/ipam/bulk/tags \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "region",
    "resource_ids": [
      "770e8400-e29b-41d4-a716-446655440002",
      "880e8400-e29b-41d4-a716-446655440003",
      "990e8400-e29b-41d4-a716-446655440004"
    ],
    "operation": "add",
    "tags": {
      "environment": "production",
      "managed_by": "terraform"
    }
  }'
```

**Response** (200 OK - Synchronous for ≤100 items):
```json
{
  "job_id": null,
  "total_requested": 3,
  "successful": 3,
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
    },
    {
      "resource_id": "990e8400-e29b-41d4-a716-446655440004",
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

### 11.2 Tag Operations

Supported operations:
- `add`: Add tags (merge with existing)
- `remove`: Remove specific tags
- `replace`: Replace all tags

**Add Tags Example**:
```json
{
  "operation": "add",
  "tags": {
    "new_tag": "value"
  }
}
```

**Remove Tags Example**:
```json
{
  "operation": "remove",
  "tags": {
    "old_tag": "value"
  }
}
```

**Replace Tags Example**:
```json
{
  "operation": "replace",
  "tags": {
    "environment": "staging",
    "version": "2.0"
  }
}
```

### 11.3 Get Bulk Job Status

Check the status of an asynchronous bulk operation.

**Endpoint**: `GET /ipam/bulk/jobs/{job_id}`

**Request**:
```bash
curl -X GET https://api.example.com/ipam/bulk/jobs/ff0e8400-e29b-41d4-a716-446655440010 \
  -H "Authorization: Bearer <token>"
```

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

---

## 12. Error Handling

### 12.1 Standard Error Response Format

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

### 12.2 Common HTTP Status Codes

| Status Code | Meaning | Example |
|-------------|---------|---------|
| 200 | Success | Resource retrieved successfully |
| 201 | Created | Resource created successfully |
| 204 | No Content | Resource deleted successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists or conflict |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

### 12.3 Common Error Codes

**Authentication Errors**:
```json
{
  "success": false,
  "error": "unauthorized",
  "message": "Authentication required"
}
```

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

### 12.4 Error Handling Best Practices

**1. Always Check Status Codes**:
```python
response = requests.post(url, json=data, headers=headers)

if response.status_code == 201:
    result = response.json()
    print(f"Created: {result['reservation_id']}")
elif response.status_code == 409:
    error = response.json()
    print(f"Conflict: {error['message']}")
else:
    print(f"Error {response.status_code}: {response.text}")
```

**2. Handle Rate Limits with Retry**:
```python
import time

def make_request_with_retry(url, data, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 429:
            retry_after = response.json().get('details', {}).get('retry_after', 60)
            print(f"Rate limited. Retrying after {retry_after}s...")
            time.sleep(retry_after)
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

**3. Validate Before Sending**:
```python
def validate_reservation(data):
    """Validate reservation data before sending."""
    if data['resource_type'] == 'host' and 'z_octet' not in data:
        raise ValueError("z_octet required for host reservations")
    
    if data.get('expires_in_days', 0) > 90:
        raise ValueError("expires_in_days cannot exceed 90")
    
    return True
```

---

## 13. Complete Workflow Examples

### 13.1 Reservation to Allocation Workflow

Complete workflow from creating a reservation to converting it to an allocation.

```python
import requests
from datetime import datetime

BASE_URL = "https://api.example.com/ipam"
headers = {"Authorization": "Bearer <your_token>"}

# Step 1: Create a reservation
reservation_data = {
    "resource_type": "region",
    "x_octet": 5,
    "y_octet": 23,
    "reason": "Reserved for Q1 expansion",
    "expires_in_days": 30
}

response = requests.post(
    f"{BASE_URL}/reservations",
    json=reservation_data,
    headers=headers
)

if response.status_code == 201:
    reservation = response.json()
    reservation_id = reservation['reservation_id']
    print(f"✓ Reservation created: {reservation['reserved_address']}")
else:
    print(f"✗ Failed to create reservation: {response.json()}")
    exit(1)

# Step 2: List reservations to verify
response = requests.get(
    f"{BASE_URL}/reservations?status=active",
    headers=headers
)

if response.status_code == 200:
    reservations = response.json()
    print(f"✓ Active reservations: {len(reservations['results'])}")

# Step 3: Convert reservation to allocation
convert_data = {
    "region_name": "Production Network",
    "description": "Primary production environment",
    "owner": "DevOps Team",
    "tags": {
        "environment": "production",
        "department": "engineering"
    }
}

response = requests.post(
    f"{BASE_URL}/reservations/{reservation_id}/convert",
    json=convert_data,
    headers=headers
)

if response.status_code == 201:
    allocation = response.json()
    print(f"✓ Converted to allocation: {allocation['resource_id']}")
    print(f"  Region: {allocation['allocation']['region_name']}")
    print(f"  CIDR: {allocation['allocation']['cidr']}")
else:
    print(f"✗ Failed to convert: {response.json()}")
```

### 13.2 Notification Setup Workflow

Set up notification rules and monitor alerts.

```python
import requests

BASE_URL = "https://api.example.com/ipam"
headers = {"Authorization": "Bearer <your_token>"}

# Step 1: Create notification rule
rule_data = {
    "rule_name": "High Utilization Alert",
    "conditions": {
        "utilization_threshold": 80,
        "resource_type": "region"
    },
    "notification_channels": ["in_app"],
    "severity": "warning"
}

response = requests.post(
    f"{BASE_URL}/notifications/rules",
    json=rule_data,
    headers=headers
)

if response.status_code == 201:
    rule = response.json()
    print(f"✓ Notification rule created: {rule['rule_name']}")
else:
    print(f"✗ Failed to create rule: {response.json()}")
    exit(1)

# Step 2: Check for unread notifications
response = requests.get(
    f"{BASE_URL}/notifications/unread",
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    print(f"✓ Unread notifications: {data['unread_count']}")
    
    for notification in data['recent']:
        print(f"  - [{notification['severity']}] {notification['message']}")

# Step 3: Mark notifications as read
if data['unread_count'] > 0:
    for notification in data['recent']:
        response = requests.patch(
            f"{BASE_URL}/notifications/{notification['notification_id']}",
            json={"is_read": True},
            headers=headers
        )
        
        if response.status_code == 200:
            print(f"✓ Marked notification as read")
```

### 13.3 Capacity Monitoring Workflow

Monitor capacity and set up forecasting.

```python
import requests

BASE_URL = "https://api.example.com/ipam"
headers = {"Authorization": "Bearer <your_token>"}

# Step 1: Get dashboard overview
response = requests.get(
    f"{BASE_URL}/statistics/dashboard",
    headers=headers
)

if response.status_code == 200:
    dashboard = response.json()
    print(f"✓ Dashboard Statistics:")
    print(f"  Total Regions: {dashboard['total_regions']}")
    print(f"  Total Hosts: {dashboard['total_hosts']}")
    print(f"  Overall Utilization: {dashboard['overall_utilization']}%")
    print(f"  Capacity Warnings: {dashboard['capacity_warnings']}")

# Step 2: Check forecast for high-utilization regions
for country in dashboard['top_countries']:
    if country['utilization'] > 70:
        # Get regions for this country
        response = requests.get(
            f"{BASE_URL}/regions?country_code={country['country_code']}",
            headers=headers
        )
        
        if response.status_code == 200:
            regions = response.json()
            
            for region in regions['results']:
                if region['utilization'] > 70:
                    # Get forecast
                    response = requests.get(
                        f"{BASE_URL}/statistics/forecast/region/{region['region_id']}",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        forecast = response.json()
                        
                        if forecast.get('estimated_exhaustion_date'):
                            print(f"\n⚠ Warning: {region['region_name']}")
                            print(f"  Current: {forecast['current_utilization']}%")
                            print(f"  Exhaustion: {forecast['days_until_exhaustion']} days")
                            print(f"  Recommendation: {forecast['recommendation']}")

# Step 3: Get allocation trends
response = requests.get(
    f"{BASE_URL}/statistics/trends?group_by=day&start_date=2025-11-01&end_date=2025-11-12",
    headers=headers
)

if response.status_code == 200:
    trends = response.json()
    print(f"\n✓ Allocation Trends:")
    print(f"  Total Allocations: {trends['summary']['total_allocations']}")
    print(f"  Average Daily Rate: {trends['summary']['average_daily_rate']}")
```

### 13.4 Webhook Integration Workflow

Set up and test webhook integration.

```python
import requests
import hmac
import hashlib
from flask import Flask, request, jsonify

BASE_URL = "https://api.example.com/ipam"
headers = {"Authorization": "Bearer <your_token>"}

# Step 1: Create webhook
webhook_data = {
    "webhook_url": "https://your-app.com/webhooks/ipam",
    "events": ["region.created", "host.allocated", "capacity.warning"],
    "description": "Production monitoring"
}

response = requests.post(
    f"{BASE_URL}/webhooks",
    json=webhook_data,
    headers=headers
)

if response.status_code == 201:
    webhook = response.json()
    secret_key = webhook['secret_key']
    print(f"✓ Webhook created: {webhook['webhook_id']}")
    print(f"  Secret: {secret_key}")
    print(f"  IMPORTANT: Save this secret key!")
else:
    print(f"✗ Failed to create webhook: {response.json()}")
    exit(1)

# Step 2: Set up Flask endpoint to receive webhooks
app = Flask(__name__)

@app.route('/webhooks/ipam', methods=['POST'])
def handle_ipam_webhook():
    # Verify signature
    signature = request.headers.get('X-IPAM-Signature', '')
    payload = request.get_data(as_text=True)
    
    expected_signature = hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(f"sha256={expected_signature}", signature):
        return jsonify({"error": "Invalid signature"}), 401
    
    # Process event
    event = request.json
    event_type = request.headers.get('X-IPAM-Event')
    
    print(f"Received event: {event_type}")
    print(f"Data: {event['data']}")
    
    # Handle different event types
    if event_type == "region.created":
        handle_region_created(event['data'])
    elif event_type == "host.allocated":
        handle_host_allocated(event['data'])
    elif event_type == "capacity.warning":
        handle_capacity_warning(event['data'])
    
    return jsonify({"success": True}), 200

def handle_region_created(data):
    print(f"New region created: {data['region_name']} ({data['cidr']})")

def handle_host_allocated(data):
    print(f"New host allocated: {data['hostname']} ({data['ip_address']})")

def handle_capacity_warning(data):
    print(f"⚠ Capacity warning: {data['message']}")

if __name__ == '__main__':
    app.run(port=5000)
```

---

## 14. SDK Examples

### 14.1 Python SDK Example

```python
"""
IPAM Enhancement API Client
A simple Python client for IPAM backend enhancements.
"""

import requests
from typing import Dict, List, Optional, Any
from datetime import datetime


class IPAMClient:
    """Client for IPAM Enhancement APIs."""
    
    def __init__(self, base_url: str, token: str):
        """
        Initialize IPAM client.
        
        Args:
            base_url: Base API URL (e.g., https://api.example.com/ipam)
            token: JWT authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    # Reservations
    def create_reservation(
        self,
        resource_type: str,
        x_octet: int,
        y_octet: int,
        reason: str,
        z_octet: Optional[int] = None,
        expires_in_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new reservation."""
        data = {
            "resource_type": resource_type,
            "x_octet": x_octet,
            "y_octet": y_octet,
            "reason": reason
        }
        
        if z_octet is not None:
            data["z_octet"] = z_octet
        if expires_in_days is not None:
            data["expires_in_days"] = expires_in_days
        
        response = requests.post(
            f"{self.base_url}/reservations",
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def list_reservations(
        self,
        status: Optional[str] = None,
        resource_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """List reservations with optional filtering."""
        params = {"page": page, "page_size": page_size}
        
        if status:
            params["status"] = status
        if resource_type:
            params["resource_type"] = resource_type
        
        response = requests.get(
            f"{self.base_url}/reservations",
            params=params,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def convert_reservation(
        self,
        reservation_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Convert reservation to allocation."""
        response = requests.post(
            f"{self.base_url}/reservations/{reservation_id}/convert",
            json=kwargs,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    # Shares
    def create_share(
        self,
        resource_type: str,
        resource_id: str,
        expires_in_days: int,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a shareable link."""
        data = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "expires_in_days": expires_in_days
        }
        
        if description:
            data["description"] = description
        
        response = requests.post(
            f"{self.base_url}/shares",
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def list_shares(self) -> Dict[str, Any]:
        """List all your shares."""
        response = requests.get(
            f"{self.base_url}/shares",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    # Notifications
    def list_notifications(
        self,
        is_read: Optional[bool] = None,
        severity: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """List notifications."""
        params = {"page": page, "page_size": page_size}
        
        if is_read is not None:
            params["is_read"] = str(is_read).lower()
        if severity:
            params["severity"] = severity
        
        response = requests.get(
            f"{self.base_url}/notifications",
            params=params,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_unread_notifications(self) -> Dict[str, Any]:
        """Get unread notification count and recent items."""
        response = requests.get(
            f"{self.base_url}/notifications/unread",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def mark_notification_read(self, notification_id: str) -> Dict[str, Any]:
        """Mark a notification as read."""
        response = requests.patch(
            f"{self.base_url}/notifications/{notification_id}",
            json={"is_read": True},
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    # Statistics
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics."""
        response = requests.get(
            f"{self.base_url}/statistics/dashboard",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_forecast(
        self,
        resource_type: str,
        resource_id: str
    ) -> Dict[str, Any]:
        """Get capacity forecast for a resource."""
        response = requests.get(
            f"{self.base_url}/statistics/forecast/{resource_type}/{resource_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_trends(
        self,
        group_by: str = "day",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get allocation trends."""
        params = {"group_by": group_by}
        
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        params.update(kwargs)
        
        response = requests.get(
            f"{self.base_url}/statistics/trends",
            params=params,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    # Webhooks
    def create_webhook(
        self,
        webhook_url: str,
        events: List[str],
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a webhook."""
        data = {
            "webhook_url": webhook_url,
            "events": events
        }
        
        if description:
            data["description"] = description
        
        response = requests.post(
            f"{self.base_url}/webhooks",
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def list_webhooks(self) -> Dict[str, Any]:
        """List all webhooks."""
        response = requests.get(
            f"{self.base_url}/webhooks",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()


# Usage Example
if __name__ == "__main__":
    client = IPAMClient(
        base_url="https://api.example.com/ipam",
        token="your_jwt_token_here"
    )
    
    # Create a reservation
    reservation = client.create_reservation(
        resource_type="region",
        x_octet=5,
        y_octet=23,
        reason="Reserved for Q1 expansion",
        expires_in_days=30
    )
    print(f"Created reservation: {reservation['reserved_address']}")
    
    # Get dashboard stats
    stats = client.get_dashboard_stats()
    print(f"Total regions: {stats['total_regions']}")
    
    # Check notifications
    unread = client.get_unread_notifications()
    print(f"Unread notifications: {unread['unread_count']}")
```

---

## 15. Rate Limits

### 15.1 Rate Limit Policy

All IPAM enhancement endpoints are subject to rate limiting to ensure fair usage and system stability.

**Default Limits**:
- **Standard Endpoints**: 100 requests per minute per user
- **Bulk Operations**: 10 requests per hour per user
- **Webhook Deliveries**: 1000 deliveries per hour per webhook
- **Dashboard Statistics**: 20 requests per minute (cached responses)

### 15.2 Rate Limit Headers

All responses include rate limit information in headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699876543
```

### 15.3 Handling Rate Limits

When you exceed the rate limit, you'll receive a 429 response:

```json
{
  "success": false,
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "details": {
    "retry_after": 60,
    "limit": "100 requests per minute"
  }
}
```

**Best Practice - Exponential Backoff**:
```python
import time
import requests

def make_request_with_backoff(url, max_retries=5):
    """Make request with exponential backoff on rate limit."""
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
            wait_time = max(retry_after - time.time(), 0)
            
            print(f"Rate limited. Waiting {wait_time}s...")
            time.sleep(wait_time)
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

---

## 16. Best Practices

### 16.1 Authentication

**Use Environment Variables**:
```python
import os

TOKEN = os.getenv('IPAM_API_TOKEN')
if not TOKEN:
    raise ValueError("IPAM_API_TOKEN environment variable not set")
```

**Refresh Tokens Proactively**:
```python
from datetime import datetime, timedelta

class TokenManager:
    def __init__(self, refresh_url, credentials):
        self.refresh_url = refresh_url
        self.credentials = credentials
        self.token = None
        self.expires_at = None
    
    def get_token(self):
        """Get valid token, refreshing if necessary."""
        if not self.token or datetime.now() >= self.expires_at:
            self.refresh_token()
        return self.token
    
    def refresh_token(self):
        """Refresh the authentication token."""
        response = requests.post(self.refresh_url, json=self.credentials)
        data = response.json()
        
        self.token = data['access_token']
        self.expires_at = datetime.now() + timedelta(minutes=14)  # Refresh before 15min expiry
```

### 16.2 Error Handling

**Always Handle Errors Gracefully**:
```python
def safe_api_call(func, *args, **kwargs):
    """Wrapper for safe API calls with error handling."""
    try:
        response = func(*args, **kwargs)
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print("Resource not found")
        elif e.response.status_code == 409:
            print(f"Conflict: {e.response.json()['message']}")
        elif e.response.status_code == 429:
            print("Rate limited - please retry later")
        else:
            print(f"HTTP error: {e}")
        return None
    
    except requests.exceptions.ConnectionError:
        print("Connection error - check network")
        return None
    
    except requests.exceptions.Timeout:
        print("Request timeout")
        return None
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
```

### 16.3 Performance Optimization

**Use Caching for Dashboard Stats**:
```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedIPAMClient:
    def __init__(self, client):
        self.client = client
        self._dashboard_cache = None
        self._dashboard_cache_time = None
    
    def get_dashboard_stats(self, cache_ttl=300):
        """Get dashboard stats with client-side caching."""
        now = datetime.now()
        
        if (self._dashboard_cache is None or 
            self._dashboard_cache_time is None or
            (now - self._dashboard_cache_time).seconds > cache_ttl):
            
            self._dashboard_cache = self.client.get_dashboard_stats()
            self._dashboard_cache_time = now
        
        return self._dashboard_cache
```

**Batch Operations**:
```python
def batch_tag_updates(client, updates, batch_size=100):
    """Process tag updates in batches."""
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i + batch_size]
        
        resource_ids = [u['resource_id'] for u in batch]
        tags = batch[0]['tags']  # Assuming same tags for batch
        
        result = client.bulk_tag_update(
            resource_type="region",
            resource_ids=resource_ids,
            operation="add",
            tags=tags
        )
        
        print(f"Batch {i//batch_size + 1}: {result['successful']} successful")
```

### 16.4 Security

**Verify Webhook Signatures**:
```python
import hmac
import hashlib

def verify_webhook(request, secret_key):
    """Verify webhook signature before processing."""
    signature = request.headers.get('X-IPAM-Signature', '')
    payload = request.get_data(as_text=True)
    
    expected = hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(f"sha256={expected}", signature):
        raise ValueError("Invalid webhook signature")
    
    return True
```

**Never Log Sensitive Data**:
```python
import logging

# Bad - logs token
logging.info(f"Making request with token: {token}")

# Good - logs without sensitive data
logging.info("Making authenticated request")
```

---

## 17. Support & Resources

### 17.1 API Documentation

- **OpenAPI Spec**: `https://api.example.com/docs`
- **Interactive Docs**: `https://api.example.com/redoc`

### 17.2 Common Issues

**Issue: 401 Unauthorized**
- Check token is valid and not expired
- Ensure Authorization header is properly formatted
- Verify token has required permissions

**Issue: 409 Conflict on Reservation**
- IP address may already be allocated
- Check existing allocations before reserving
- Use list endpoints to verify availability

**Issue: Webhook Not Receiving Events**
- Verify webhook URL is publicly accessible
- Check webhook is active (`is_active: true`)
- Review delivery history for errors
- Ensure your endpoint returns 200 status

**Issue: Forecast Shows Insufficient Data**
- Need at least 10 allocations over 7+ days
- Wait for more historical data to accumulate
- Check resource has allocation activity

### 17.3 Migration from Legacy APIs

If migrating from older IPAM APIs:

1. **Update Authentication**: Switch to JWT tokens
2. **Update Endpoints**: New endpoints use `/ipam/` prefix
3. **Update Response Handling**: New consistent response format
4. **Add Error Handling**: Handle new error codes
5. **Test Thoroughly**: Verify all integrations work

---

## 18. Changelog

### Version 1.0.0 (2025-11-12)

**Initial Release**:
- Reservation Management (5 endpoints)
- Shareable Links (4 endpoints)
- User Preferences (2 endpoints)
- Saved Filters (3 endpoints)
- Notifications (4 endpoints)
- Notification Rules (4 endpoints)
- Dashboard Statistics (1 endpoint)
- Capacity Forecasting (2 endpoints)
- Webhooks (4 endpoints)
- Bulk Operations (2 endpoints)

**Total**: 31 new endpoints

---

## Appendix: Quick Reference

### Endpoint Summary

| Category | Endpoint | Method | Description |
|----------|----------|--------|-------------|
| **Reservations** | `/ipam/reservations` | POST | Create reservation |
| | `/ipam/reservations` | GET | List reservations |
| | `/ipam/reservations/{id}/convert` | POST | Convert to allocation |
| | `/ipam/reservations/{id}` | DELETE | Delete reservation |
| **Shares** | `/ipam/shares` | POST | Create share |
| | `/ipam/shares/{token}` | GET | Access shared resource |
| | `/ipam/shares` | GET | List shares |
| | `/ipam/shares/{id}` | DELETE | Revoke share |
| **Preferences** | `/ipam/preferences` | GET | Get preferences |
| | `/ipam/preferences` | PUT | Update preferences |
| | `/ipam/preferences/filters` | POST | Save filter |
| | `/ipam/preferences/filters` | GET | List filters |
| | `/ipam/preferences/filters/{id}` | DELETE | Delete filter |
| **Notifications** | `/ipam/notifications` | GET | List notifications |
| | `/ipam/notifications/unread` | GET | Get unread count |
| | `/ipam/notifications/{id}` | PATCH | Mark as read |
| | `/ipam/notifications/{id}` | DELETE | Dismiss notification |
| **Rules** | `/ipam/notifications/rules` | POST | Create rule |
| | `/ipam/notifications/rules` | GET | List rules |
| | `/ipam/notifications/rules/{id}` | PATCH | Update rule |
| | `/ipam/notifications/rules/{id}` | DELETE | Delete rule |
| **Statistics** | `/ipam/statistics/dashboard` | GET | Dashboard stats |
| | `/ipam/statistics/forecast/{type}/{id}` | GET | Capacity forecast |
| | `/ipam/statistics/trends` | GET | Allocation trends |
| **Webhooks** | `/ipam/webhooks` | POST | Create webhook |
| | `/ipam/webhooks` | GET | List webhooks |
| | `/ipam/webhooks/{id}/deliveries` | GET | Delivery history |
| | `/ipam/webhooks/{id}` | DELETE | Delete webhook |
| **Bulk** | `/ipam/bulk/tags` | POST | Bulk tag update |
| | `/ipam/bulk/jobs/{id}` | GET | Job status |

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-12  
**Status**: Production Ready
