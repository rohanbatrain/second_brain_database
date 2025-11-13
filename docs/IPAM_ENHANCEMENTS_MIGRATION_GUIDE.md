# IPAM Backend Enhancements Migration Guide

## Overview

This guide helps you migrate your IPAM system to include the new backend enhancements: reservations, shareable links, user preferences, notifications, capacity forecasting, webhooks, and bulk operations.

**Migration Type**: Additive (backward compatible)  
**Downtime Required**: None  
**Estimated Time**: 15-30 minutes

## What's New

The IPAM backend enhancements add 8 new collections and 31 new API endpoints:

- **Reservations**: Pre-allocate IP addresses for future use
- **Shareable Links**: Generate public read-only links to IPAM resources
- **User Preferences**: Store user settings and saved filters
- **Notifications**: Alert system with customizable rules
- **Dashboard Statistics**: Aggregated metrics with caching
- **Capacity Forecasting**: Predictive analytics for IP exhaustion
- **Webhooks**: Event-driven integrations with external systems
- **Bulk Operations**: Enhanced batch processing for large-scale changes

## Prerequisites

Before starting the migration:

1. **Backup your database**
   ```bash
   mongodump --uri="mongodb://localhost:27017" --db=your_database --out=backup_$(date +%Y%m%d)
   ```

2. **Verify system requirements**
   - Python 3.11+
   - MongoDB 4.4+
   - Redis 6.0+ (for caching)
   - Existing IPAM system operational

3. **Check current IPAM status**
   ```bash
   # Verify existing collections
   mongosh your_database --eval "db.getCollectionNames()"
   ```


## For Backend Developers

### Step 1: Run the Database Migration

The migration creates 8 new collections with proper indexes and schema validation.

**Check migration status first:**
```bash
uv run python scripts/run_ipam_enhancements_migration.py --status
```

**Run the migration:**
```bash
uv run python scripts/run_ipam_enhancements_migration.py
```

**Expected output:**
```
================================================================================
Starting IPAM Backend Enhancements Migration
================================================================================
Connecting to database...
Database connection successful
Migration Details:
  Name: create_ipam_enhancements_collections
  Version: 1.0.0
  Description: Create IPAM backend enhancements collections with proper indexes and constraints

Validating migration...
Migration validation passed

Executing migration...

================================================================================
Migration Results:
================================================================================
Status: completed
Duration: 2.34 seconds
Collections affected: ipam_reservations, ipam_shares, ipam_user_preferences, ipam_notifications, ipam_notification_rules, ipam_webhooks, ipam_webhook_deliveries, ipam_bulk_jobs
Records processed: 0

✅ IPAM backend enhancements migration completed successfully!

Created collections:
  - ipam_reservations
  - ipam_shares
  - ipam_user_preferences
  - ipam_notifications
  - ipam_notification_rules
  - ipam_webhooks
  - ipam_webhook_deliveries
  - ipam_bulk_jobs
```


### Step 2: Verify Database Indexes

Run the index verification script to ensure all indexes were created correctly:

```bash
uv run python scripts/verify_ipam_indexes.py
```

**Expected output:**
```
================================================================================
IPAM Backend Enhancements - Index Verification
================================================================================
✓ Connected to database
✓ Database health check passed

✓ ipam_reservations: All indexes present
✓ ipam_shares: All indexes present
✓ ipam_user_preferences: All indexes present
✓ ipam_notifications: All indexes present
✓ ipam_notification_rules: All indexes present
✓ ipam_webhooks: All indexes present
✓ ipam_webhook_deliveries: All indexes present
✓ ipam_bulk_jobs: All indexes present

================================================================================
Verification Summary
================================================================================
✓ All indexes verified successfully!
  Collections checked: 8
  Total expected indexes: 45
================================================================================
```

### Step 3: Restart the Application

The new endpoints are automatically registered. Simply restart your application:

```bash
# Stop the current server (Ctrl+C)

# Restart with uvicorn
uv run uvicorn src.second_brain_database.main:app --reload
```

### Step 4: Verify New Endpoints

Check that new endpoints are available in the OpenAPI documentation:

```bash
# Open in browser
open http://localhost:8000/docs

# Or check via curl
curl http://localhost:8000/openapi.json | jq '.paths | keys | .[] | select(contains("ipam"))'
```

**Expected new endpoints:**
- `/ipam/reservations` (POST, GET)
- `/ipam/reservations/{id}` (GET, DELETE)
- `/ipam/reservations/{id}/convert` (POST)
- `/ipam/shares` (POST, GET)
- `/ipam/shares/{token}` (GET)
- `/ipam/shares/{id}` (DELETE)
- `/ipam/preferences` (GET, PUT)
- `/ipam/preferences/filters` (POST, GET)
- `/ipam/preferences/filters/{id}` (DELETE)
- `/ipam/notifications` (GET)
- `/ipam/notifications/unread` (GET)
- `/ipam/notifications/{id}` (PATCH, DELETE)
- `/ipam/notifications/rules` (POST, GET)
- `/ipam/notifications/rules/{id}` (PATCH, DELETE)
- `/ipam/statistics/dashboard` (GET)
- `/ipam/statistics/forecast/{type}/{id}` (GET)
- `/ipam/statistics/trends` (GET)
- `/ipam/webhooks` (POST, GET)
- `/ipam/webhooks/{id}` (DELETE)
- `/ipam/webhooks/{id}/deliveries` (GET)
- `/ipam/bulk/tags` (POST)
- `/ipam/bulk/jobs/{job_id}` (GET)


### Step 5: Configure Background Tasks (Optional)

The system includes 4 background tasks that run automatically:

1. **Reservation Expiration Checker** (hourly)
   - Marks expired reservations as "expired"
   - Automatically enabled

2. **Share Expiration Checker** (hourly)
   - Marks expired shares as inactive
   - Automatically enabled

3. **Notification Cleanup** (daily)
   - Deletes notifications older than 90 days
   - Automatically enabled

4. **Webhook Delivery Processor** (on-demand)
   - Processes webhook deliveries with retry logic
   - Triggered by events

**No configuration needed** - these tasks are automatically registered and run in the background.

To verify background tasks are running, check the logs:

```bash
# Check for background task logs
tail -f logs/app.log | grep -E "(reservation_expiration|share_expiration|notification_cleanup|webhook_delivery)"
```

### Step 6: Test the Migration

Run a quick smoke test to verify everything works:

```bash
# Test creating a reservation
curl -X POST http://localhost:8000/ipam/reservations \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "region",
    "x_octet": 99,
    "y_octet": 99,
    "reason": "Migration test",
    "expires_in_days": 1
  }'

# Expected: 201 Created with reservation details

# Test getting dashboard statistics
curl http://localhost:8000/ipam/statistics/dashboard \
  -H "Authorization: Bearer <your_token>"

# Expected: 200 OK with dashboard stats

# Test getting user preferences
curl http://localhost:8000/ipam/preferences \
  -H "Authorization: Bearer <your_token>"

# Expected: 200 OK with empty preferences object
```


## For Frontend Developers

### Step 1: Update API Client

Add new endpoint methods to your API client:

```javascript
// api/ipam.js

// Reservations
export async function createReservation(data) {
  return apiCall('/ipam/reservations', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export async function getReservations(filters = {}) {
  const params = new URLSearchParams(filters);
  return apiCall(`/ipam/reservations?${params}`);
}

export async function convertReservation(reservationId, data) {
  return apiCall(`/ipam/reservations/${reservationId}/convert`, {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

// Shareable Links
export async function createShare(data) {
  return apiCall('/ipam/shares', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export async function getSharedResource(token) {
  // No auth required for accessing shares
  return fetch(`/ipam/shares/${token}`).then(r => r.json());
}

// User Preferences
export async function getPreferences() {
  return apiCall('/ipam/preferences');
}

export async function updatePreferences(data) {
  return apiCall('/ipam/preferences', {
    method: 'PUT',
    body: JSON.stringify(data)
  });
}

// Notifications
export async function getNotifications(filters = {}) {
  const params = new URLSearchParams(filters);
  return apiCall(`/ipam/notifications?${params}`);
}

export async function getUnreadNotifications() {
  return apiCall('/ipam/notifications/unread');
}

export async function markNotificationRead(notificationId) {
  return apiCall(`/ipam/notifications/${notificationId}`, {
    method: 'PATCH',
    body: JSON.stringify({ is_read: true })
  });
}

// Dashboard Statistics
export async function getDashboardStats() {
  return apiCall('/ipam/statistics/dashboard');
}

// Capacity Forecasting
export async function getCapacityForecast(resourceType, resourceId) {
  return apiCall(`/ipam/statistics/forecast/${resourceType}/${resourceId}`);
}

// Webhooks
export async function createWebhook(data) {
  return apiCall('/ipam/webhooks', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export async function getWebhooks() {
  return apiCall('/ipam/webhooks');
}
```


### Step 2: Implement New Features

#### Reservation Management UI

```javascript
// components/ReservationManager.jsx
import { useState } from 'react';
import { createReservation, getReservations, convertReservation } from '../api/ipam';

export function ReservationManager() {
  const [reservations, setReservations] = useState([]);
  
  const handleCreateReservation = async (data) => {
    try {
      const result = await createReservation(data);
      setReservations([...reservations, result]);
      alert('Reservation created successfully!');
    } catch (error) {
      alert(`Failed to create reservation: ${error.message}`);
    }
  };
  
  const handleConvertReservation = async (reservationId, conversionData) => {
    try {
      const result = await convertReservation(reservationId, conversionData);
      // Remove from reservations list
      setReservations(reservations.filter(r => r.reservation_id !== reservationId));
      alert('Reservation converted to allocation!');
      return result;
    } catch (error) {
      alert(`Failed to convert reservation: ${error.message}`);
    }
  };
  
  // ... UI implementation
}
```

#### Notification Bell Component

```javascript
// components/NotificationBell.jsx
import { useState, useEffect } from 'react';
import { getUnreadNotifications, markNotificationRead } from '../api/ipam';

export function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  
  useEffect(() => {
    // Poll for new notifications every 30 seconds
    const interval = setInterval(async () => {
      const data = await getUnreadNotifications();
      setUnreadCount(data.unread_count);
      setNotifications(data.recent);
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);
  
  const handleMarkRead = async (notificationId) => {
    await markNotificationRead(notificationId);
    setUnreadCount(prev => Math.max(0, prev - 1));
    setNotifications(notifications.filter(n => n._id !== notificationId));
  };
  
  // ... UI implementation
}
```

#### Dashboard Statistics Widget

```javascript
// components/DashboardStats.jsx
import { useState, useEffect } from 'react';
import { getDashboardStats } from '../api/ipam';

export function DashboardStats() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    async function loadStats() {
      try {
        const data = await getDashboardStats();
        setStats(data);
      } catch (error) {
        console.error('Failed to load dashboard stats:', error);
      } finally {
        setLoading(false);
      }
    }
    
    loadStats();
    // Refresh every 5 minutes (stats are cached for 5 minutes on backend)
    const interval = setInterval(loadStats, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);
  
  if (loading) return <div>Loading statistics...</div>;
  if (!stats) return <div>Failed to load statistics</div>;
  
  return (
    <div className="dashboard-stats">
      <StatCard title="Total Countries" value={stats.total_countries} />
      <StatCard title="Total Regions" value={stats.total_regions} />
      <StatCard title="Total Hosts" value={stats.total_hosts} />
      <StatCard title="Overall Utilization" value={`${stats.overall_utilization}%`} />
    </div>
  );
}
```


### Step 3: Handle Shareable Links

Shareable links don't require authentication, so handle them separately:

```javascript
// pages/SharedResource.jsx
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getSharedResource } from '../api/ipam';

export function SharedResourcePage() {
  const { token } = useParams();
  const [resource, setResource] = useState(null);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    async function loadSharedResource() {
      try {
        const data = await getSharedResource(token);
        setResource(data);
      } catch (err) {
        if (err.status === 404) {
          setError('This share link has expired or been revoked');
        } else {
          setError('Failed to load shared resource');
        }
      }
    }
    
    loadSharedResource();
  }, [token]);
  
  if (error) return <div className="error">{error}</div>;
  if (!resource) return <div>Loading...</div>;
  
  return (
    <div className="shared-resource">
      <h1>Shared {resource.resource_type}</h1>
      <div className="resource-data">
        {/* Display resource data */}
        <pre>{JSON.stringify(resource.resource_data, null, 2)}</pre>
      </div>
      <div className="share-info">
        <p>Shared by: {resource.shared_by}</p>
        <p>Created: {new Date(resource.created_at).toLocaleDateString()}</p>
      </div>
    </div>
  );
}
```

### Step 4: Implement User Preferences Persistence

```javascript
// hooks/useUserPreferences.js
import { useState, useEffect } from 'react';
import { getPreferences, updatePreferences } from '../api/ipam';

export function useUserPreferences() {
  const [preferences, setPreferences] = useState({
    saved_filters: [],
    dashboard_layout: {},
    notification_settings: {},
    theme_preference: 'default'
  });
  
  useEffect(() => {
    async function loadPreferences() {
      try {
        const data = await getPreferences();
        setPreferences(data);
      } catch (error) {
        console.error('Failed to load preferences:', error);
      }
    }
    
    loadPreferences();
  }, []);
  
  const savePreferences = async (updates) => {
    try {
      await updatePreferences(updates);
      setPreferences({ ...preferences, ...updates });
    } catch (error) {
      console.error('Failed to save preferences:', error);
      throw error;
    }
  };
  
  return { preferences, savePreferences };
}

// Usage in component
function MyComponent() {
  const { preferences, savePreferences } = useUserPreferences();
  
  const handleThemeChange = async (newTheme) => {
    await savePreferences({ theme_preference: newTheme });
  };
  
  // ... rest of component
}
```


## For Mobile App Developers

### React Native Example

```javascript
// services/ipamEnhancements.js
import AsyncStorage from '@react-native-async-storage/async-storage';

class IPAMEnhancementsService {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }
  
  async getAuthToken() {
    return await AsyncStorage.getItem('access_token');
  }
  
  async apiCall(endpoint, options = {}) {
    const token = await this.getAuthToken();
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error(`API call failed: ${response.statusText}`);
    }
    
    return response.json();
  }
  
  // Reservations
  async createReservation(data) {
    return this.apiCall('/ipam/reservations', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }
  
  async getReservations(filters = {}) {
    const params = new URLSearchParams(filters).toString();
    return this.apiCall(`/ipam/reservations?${params}`);
  }
  
  // Dashboard Statistics
  async getDashboardStats() {
    return this.apiCall('/ipam/statistics/dashboard');
  }
  
  // Notifications
  async getUnreadNotifications() {
    return this.apiCall('/ipam/notifications/unread');
  }
  
  async markNotificationRead(notificationId) {
    return this.apiCall(`/ipam/notifications/${notificationId}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_read: true })
    });
  }
  
  // User Preferences
  async getPreferences() {
    return this.apiCall('/ipam/preferences');
  }
  
  async updatePreferences(data) {
    return this.apiCall('/ipam/preferences', {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }
}

export default new IPAMEnhancementsService('https://api.example.com');
```

### Flutter Example

```dart
// lib/services/ipam_enhancements_service.dart
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class IPAMEnhancementsService {
  final String baseUrl;
  final storage = FlutterSecureStorage();
  
  IPAMEnhancementsService(this.baseUrl);
  
  Future<String?> getAuthToken() async {
    return await storage.read(key: 'access_token');
  }
  
  Future<Map<String, dynamic>> apiCall(
    String endpoint, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    final token = await getAuthToken();
    final uri = Uri.parse('$baseUrl$endpoint');
    
    http.Response response;
    final headers = {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
    
    switch (method) {
      case 'POST':
        response = await http.post(uri, headers: headers, body: jsonEncode(body));
        break;
      case 'PUT':
        response = await http.put(uri, headers: headers, body: jsonEncode(body));
        break;
      case 'PATCH':
        response = await http.patch(uri, headers: headers, body: jsonEncode(body));
        break;
      case 'DELETE':
        response = await http.delete(uri, headers: headers);
        break;
      default:
        response = await http.get(uri, headers: headers);
    }
    
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body);
    } else {
      throw Exception('API call failed: ${response.statusCode}');
    }
  }
  
  // Reservations
  Future<Map<String, dynamic>> createReservation(Map<String, dynamic> data) async {
    return apiCall('/ipam/reservations', method: 'POST', body: data);
  }
  
  Future<Map<String, dynamic>> getReservations([Map<String, String>? filters]) async {
    String endpoint = '/ipam/reservations';
    if (filters != null && filters.isNotEmpty) {
      final params = filters.entries.map((e) => '${e.key}=${e.value}').join('&');
      endpoint += '?$params';
    }
    return apiCall(endpoint);
  }
  
  // Dashboard Statistics
  Future<Map<String, dynamic>> getDashboardStats() async {
    return apiCall('/ipam/statistics/dashboard');
  }
  
  // Notifications
  Future<Map<String, dynamic>> getUnreadNotifications() async {
    return apiCall('/ipam/notifications/unread');
  }
  
  Future<void> markNotificationRead(String notificationId) async {
    await apiCall(
      '/ipam/notifications/$notificationId',
      method: 'PATCH',
      body: {'is_read': true},
    );
  }
  
  // User Preferences
  Future<Map<String, dynamic>> getPreferences() async {
    return apiCall('/ipam/preferences');
  }
  
  Future<void> updatePreferences(Map<String, dynamic> data) async {
    await apiCall('/ipam/preferences', method: 'PUT', body: data);
  }
}
```


## Database Schema Reference

### New Collections Overview

| Collection | Purpose | Key Indexes |
|------------|---------|-------------|
| `ipam_reservations` | Pre-allocated IP addresses | user_id, status, octets, expires_at |
| `ipam_shares` | Shareable public links | share_token (unique), user_id, expires_at |
| `ipam_user_preferences` | User settings and filters | user_id (unique) |
| `ipam_notifications` | User notifications | user_id, is_read, created_at |
| `ipam_notification_rules` | Notification triggers | user_id, is_active |
| `ipam_webhooks` | Webhook configurations | user_id, is_active |
| `ipam_webhook_deliveries` | Webhook delivery logs | webhook_id, delivered_at |
| `ipam_bulk_jobs` | Async bulk operation jobs | job_id (unique), user_id, status |

### Collection Details

#### ipam_reservations
```javascript
{
  "_id": ObjectId,
  "user_id": "string",
  "resource_type": "region" | "host",
  "x_octet": 0-255,
  "y_octet": 0-255,
  "z_octet": 0-255 | null,  // Only for host reservations
  "reason": "string",
  "status": "active" | "expired" | "converted",
  "expires_at": ISODate | null,
  "created_at": ISODate,
  "created_by": "string",
  "metadata": {}
}
```

#### ipam_shares
```javascript
{
  "_id": ObjectId,
  "share_token": "uuid",  // Unique
  "user_id": "string",
  "resource_type": "country" | "region" | "host",
  "resource_id": "string",
  "expires_at": ISODate,
  "view_count": 0,
  "last_accessed": ISODate | null,
  "created_at": ISODate,
  "created_by": "string",
  "is_active": true
}
```

#### ipam_user_preferences
```javascript
{
  "_id": ObjectId,
  "user_id": "string",  // Unique
  "saved_filters": [
    {
      "filter_id": "string",
      "name": "string",
      "criteria": {},
      "created_at": ISODate
    }
  ],
  "dashboard_layout": {},
  "notification_settings": {},
  "theme_preference": "string",
  "updated_at": ISODate
}
```

#### ipam_notifications
```javascript
{
  "_id": ObjectId,
  "user_id": "string",
  "notification_type": "string",
  "severity": "info" | "warning" | "critical",
  "message": "string",
  "resource_type": "string" | null,
  "resource_id": "string" | null,
  "resource_link": "string" | null,
  "is_read": false,
  "read_at": ISODate | null,
  "created_at": ISODate,
  "expires_at": ISODate  // Auto-delete after 90 days
}
```


## Testing Your Migration

### 1. Backend Health Check

```bash
# Check all collections exist
mongosh your_database --eval "
  const collections = db.getCollectionNames();
  const ipamCollections = [
    'ipam_reservations',
    'ipam_shares',
    'ipam_user_preferences',
    'ipam_notifications',
    'ipam_notification_rules',
    'ipam_webhooks',
    'ipam_webhook_deliveries',
    'ipam_bulk_jobs'
  ];
  
  ipamCollections.forEach(name => {
    if (collections.includes(name)) {
      print('✓ ' + name);
    } else {
      print('✗ ' + name + ' MISSING');
    }
  });
"

# Check indexes
mongosh your_database --eval "
  db.ipam_reservations.getIndexes().forEach(idx => {
    print('Index: ' + JSON.stringify(idx.key));
  });
"
```

### 2. API Endpoint Tests

```bash
# Set your token
export TOKEN="your_jwt_token_here"

# Test 1: Create a reservation
curl -X POST http://localhost:8000/ipam/reservations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "region",
    "x_octet": 99,
    "y_octet": 99,
    "reason": "Migration test",
    "expires_in_days": 1
  }'
# Expected: 201 Created

# Test 2: Get reservations
curl http://localhost:8000/ipam/reservations \
  -H "Authorization: Bearer $TOKEN"
# Expected: 200 OK with list

# Test 3: Get dashboard statistics
curl http://localhost:8000/ipam/statistics/dashboard \
  -H "Authorization: Bearer $TOKEN"
# Expected: 200 OK with stats

# Test 4: Get user preferences
curl http://localhost:8000/ipam/preferences \
  -H "Authorization: Bearer $TOKEN"
# Expected: 200 OK with empty preferences

# Test 5: Create a share
curl -X POST http://localhost:8000/ipam/shares \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "country",
    "resource_id": "USA",
    "expires_in_days": 7
  }'
# Expected: 201 Created with share_token

# Test 6: Get notifications
curl http://localhost:8000/ipam/notifications/unread \
  -H "Authorization: Bearer $TOKEN"
# Expected: 200 OK with unread_count: 0
```

### 3. Performance Tests

```bash
# Test dashboard statistics response time
time curl -s http://localhost:8000/ipam/statistics/dashboard \
  -H "Authorization: Bearer $TOKEN" > /dev/null
# Expected: < 500ms

# Test capacity forecast response time
time curl -s "http://localhost:8000/ipam/statistics/forecast/country/USA" \
  -H "Authorization: Bearer $TOKEN" > /dev/null
# Expected: < 1s
```

### 4. Integration Tests

Run the comprehensive test suite:

```bash
# Run all IPAM enhancement tests
uv run pytest tests/test_ipam_enhancements.py -v

# Run specific test categories
uv run pytest tests/test_ipam_enhancements.py::TestReservations -v
uv run pytest tests/test_ipam_enhancements.py::TestNotifications -v
uv run pytest tests/test_ipam_enhancements.py::TestWebhooks -v

# Run with coverage
uv run pytest tests/test_ipam_enhancements.py --cov=src.second_brain_database.routes.ipam --cov-report=html
```


## Common Issues and Solutions

### Issue 1: Migration Already Applied

**Symptom:**
```
Migration was skipped (already applied)
```

**Cause:** Migration has already been run on this database.

**Solution:**
```bash
# Check migration status
uv run python scripts/run_ipam_enhancements_migration.py --status

# If you need to re-run (WARNING: destroys data):
uv run python scripts/run_ipam_enhancements_migration.py --rollback
uv run python scripts/run_ipam_enhancements_migration.py
```

### Issue 2: Missing Indexes

**Symptom:**
```
✗ ipam_reservations: Issues found
  Missing indexes (1):
    - [('user_id', 1), ('status', 1)] (unique=False)
```

**Cause:** Index creation failed during migration.

**Solution:**
```bash
# Manually create missing indexes
mongosh your_database --eval "
  db.ipam_reservations.createIndex({user_id: 1, status: 1});
"

# Verify
uv run python scripts/verify_ipam_indexes.py
```

### Issue 3: 404 on New Endpoints

**Symptom:**
```
curl: (404) Not Found
```

**Cause:** Application not restarted after migration.

**Solution:**
```bash
# Restart the application
# Stop current server (Ctrl+C)
uv run uvicorn src.second_brain_database.main:app --reload

# Verify endpoints are registered
curl http://localhost:8000/openapi.json | jq '.paths | keys | .[] | select(contains("ipam"))'
```

### Issue 4: Slow Dashboard Statistics

**Symptom:** Dashboard endpoint takes > 500ms to respond.

**Cause:** Redis caching not configured or not working.

**Solution:**
```bash
# Check Redis connection
redis-cli ping
# Expected: PONG

# Check Redis configuration in .env
grep REDIS_URL .env
# Should be: REDIS_URL=redis://localhost:6379

# Restart application to reconnect to Redis
```

### Issue 5: Webhook Deliveries Failing

**Symptom:** Webhooks not being delivered, high failure_count.

**Cause:** Target URL unreachable or returning errors.

**Solution:**
```bash
# Check webhook delivery logs
mongosh your_database --eval "
  db.ipam_webhook_deliveries.find().sort({delivered_at: -1}).limit(5).pretty();
"

# Test webhook URL manually
curl -X POST https://your-webhook-url.com/endpoint \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# If webhook is disabled due to failures, re-enable:
mongosh your_database --eval "
  db.ipam_webhooks.updateOne(
    {_id: ObjectId('your_webhook_id')},
    {\$set: {is_active: true, failure_count: 0}}
  );
"
```

### Issue 6: Background Tasks Not Running

**Symptom:** Expired reservations not being cleaned up.

**Cause:** Background tasks not registered or application not running.

**Solution:**
```bash
# Check application logs for background task registration
tail -f logs/app.log | grep -E "(reservation_expiration|share_expiration|notification_cleanup)"

# Expected output:
# [BackgroundTasks] Registered task: reservation_expiration_checker
# [BackgroundTasks] Registered task: share_expiration_checker
# [BackgroundTasks] Registered task: notification_cleanup

# If not found, restart application
```


## Rollback Plan

If you need to rollback the migration (WARNING: This will delete all data in the new collections):

### Step 1: Backup Current Data

```bash
# Backup all IPAM enhancement collections
mongodump --uri="mongodb://localhost:27017" \
  --db=your_database \
  --collection=ipam_reservations \
  --collection=ipam_shares \
  --collection=ipam_user_preferences \
  --collection=ipam_notifications \
  --collection=ipam_notification_rules \
  --collection=ipam_webhooks \
  --collection=ipam_webhook_deliveries \
  --collection=ipam_bulk_jobs \
  --out=rollback_backup_$(date +%Y%m%d_%H%M%S)
```

### Step 2: Run Rollback Script

```bash
uv run python scripts/run_ipam_enhancements_migration.py --rollback
```

**Confirmation required:**
```
================================================================================
ROLLBACK MODE
================================================================================
This will DROP all IPAM enhancements collections and DELETE all data!
This action CANNOT be undone!

Type 'yes' to confirm rollback: yes
```

**Expected output:**
```
================================================================================
Rolling Back IPAM Backend Enhancements Migration
================================================================================
Connecting to database...
Database connection successful
Found migration to rollback:
  Migration ID: 550e8400-e29b-41d4-a716-446655440000
  Completed at: 2025-11-12T10:00:00Z

Executing rollback...

================================================================================
Rollback Results:
================================================================================
Collections dropped: ipam_reservations, ipam_shares, ipam_user_preferences, ipam_notifications, ipam_notification_rules, ipam_webhooks, ipam_webhook_deliveries, ipam_bulk_jobs

✅ Rollback completed successfully!
```

### Step 3: Verify Rollback

```bash
# Check collections are gone
mongosh your_database --eval "
  const collections = db.getCollectionNames();
  const ipamCollections = [
    'ipam_reservations',
    'ipam_shares',
    'ipam_user_preferences',
    'ipam_notifications',
    'ipam_notification_rules',
    'ipam_webhooks',
    'ipam_webhook_deliveries',
    'ipam_bulk_jobs'
  ];
  
  ipamCollections.forEach(name => {
    if (collections.includes(name)) {
      print('✗ ' + name + ' still exists');
    } else {
      print('✓ ' + name + ' removed');
    }
  });
"
```

### Step 4: Restart Application

```bash
# Restart to remove endpoints
uv run uvicorn src.second_brain_database.main:app --reload
```

**Note:** The existing IPAM system will continue to work normally. Only the enhancement features will be unavailable.


## Performance Optimization

### Redis Caching Configuration

The IPAM enhancements use Redis for caching to improve performance:

**Dashboard Statistics:** 5-minute TTL
```python
# Cached automatically by the backend
# No frontend configuration needed
```

**Capacity Forecasts:** 24-hour TTL
```python
# Cached automatically by the backend
# Forecasts are expensive to calculate
```

**Search Results:** 5-minute TTL
```python
# Common searches are cached
# Reduces database load
```

### Database Query Optimization

All collections have proper indexes for common queries:

```javascript
// Reservations - optimized for user queries
db.ipam_reservations.createIndex({user_id: 1, status: 1});
db.ipam_reservations.createIndex({user_id: 1, created_at: -1});

// Notifications - optimized for unread queries
db.ipam_notifications.createIndex({user_id: 1, is_read: 1, created_at: -1});

// Shares - optimized for token lookup
db.ipam_shares.createIndex({share_token: 1}, {unique: true});
```

### Rate Limiting

All new endpoints have rate limiting applied:

- **Standard endpoints:** 100 requests/minute per user
- **Bulk operations:** 10 requests/hour per user
- **Dashboard statistics:** 60 requests/minute per user (cached)
- **Shareable links:** 1000 requests/minute (no auth, global limit)

### Monitoring Performance

```bash
# Check Redis cache hit rate
redis-cli info stats | grep keyspace_hits

# Check slow queries in MongoDB
mongosh your_database --eval "
  db.setProfilingLevel(1, {slowms: 100});
  db.system.profile.find().sort({ts: -1}).limit(10).pretty();
"

# Monitor endpoint response times
tail -f logs/app.log | grep -E "ipam.*ms"
```


## Security Considerations

### Authentication Requirements

All new endpoints require authentication except:
- `GET /ipam/shares/{token}` - Public access to shared resources

**Ensure your frontend:**
1. Includes JWT token in Authorization header
2. Handles 401 responses with token refresh
3. Redirects to login on authentication failure

### Data Sanitization

Shareable links automatically sanitize data:
- Owner details removed (only username shown)
- Internal IDs excluded
- Comments and metadata stripped
- Sensitive fields filtered

**Example sanitized response:**
```json
{
  "resource_type": "region",
  "resource_data": {
    "x_octet": 10,
    "y_octet": 5,
    "name": "Production Network",
    "status": "Active"
    // No user_id, no internal metadata
  },
  "shared_by": "john.doe",  // Username only
  "created_at": "2025-11-12T10:00:00Z"
}
```

### Webhook Security

Webhooks include HMAC signatures for verification:

**Backend generates:**
```python
signature = hmac.new(
    secret_key.encode(),
    payload_json.encode(),
    hashlib.sha256
).hexdigest()

headers = {
    "X-IPAM-Signature": f"sha256={signature}",
    "X-IPAM-Event": event_type
}
```

**Your webhook endpoint should verify:**
```python
import hmac
import hashlib

def verify_webhook(request, secret_key):
    signature = request.headers.get('X-IPAM-Signature', '')
    if not signature.startswith('sha256='):
        return False
    
    expected_signature = signature[7:]  # Remove 'sha256=' prefix
    payload = request.body
    
    computed_signature = hmac.new(
        secret_key.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_signature, expected_signature)
```

### Permission Checks

All endpoints validate:
1. User is authenticated
2. User has `ipam:read` or `ipam:allocate` permission
3. User can only access their own resources
4. Family members can access shared family resources (if applicable)


## Backward Compatibility

### Existing IPAM Functionality

**All existing IPAM endpoints continue to work unchanged:**
- Country management
- Region allocation
- Host allocation
- Search and filtering
- Audit history
- Metrics and statistics (original)

### No Breaking Changes

The migration is **additive only**:
- No existing collections modified
- No existing indexes changed
- No existing endpoints altered
- No existing data structures changed

### Gradual Adoption

You can adopt new features incrementally:

**Phase 1: Backend Only**
- Run migration
- New endpoints available
- Existing functionality unchanged
- No frontend changes required

**Phase 2: Add Basic Features**
- Implement reservations UI
- Add dashboard statistics widget
- Show notifications bell

**Phase 3: Advanced Features**
- Add shareable links
- Implement webhooks
- Add capacity forecasting charts

**Phase 4: Full Integration**
- User preferences persistence
- Notification rules configuration
- Bulk operations UI


## Monitoring and Maintenance

### Health Checks

Add health checks for new features:

```bash
# Check collection counts
mongosh your_database --eval "
  print('Reservations: ' + db.ipam_reservations.countDocuments());
  print('Shares: ' + db.ipam_shares.countDocuments());
  print('Notifications: ' + db.ipam_notifications.countDocuments());
  print('Webhooks: ' + db.ipam_webhooks.countDocuments());
"

# Check active background tasks
curl http://localhost:8000/health | jq '.background_tasks'
```

### Cleanup Tasks

Background tasks handle automatic cleanup:

**Reservation Expiration** (runs hourly)
```javascript
// Marks expired reservations
db.ipam_reservations.updateMany(
  {
    status: "active",
    expires_at: {$lte: new Date()}
  },
  {
    $set: {status: "expired"}
  }
);
```

**Share Expiration** (runs hourly)
```javascript
// Marks expired shares as inactive
db.ipam_shares.updateMany(
  {
    is_active: true,
    expires_at: {$lte: new Date()}
  },
  {
    $set: {is_active: false}
  }
);
```

**Notification Cleanup** (runs daily)
```javascript
// Deletes notifications older than 90 days
db.ipam_notifications.deleteMany({
  expires_at: {$lte: new Date()}
});
```

### Manual Cleanup (if needed)

```bash
# Clean up old webhook deliveries (keep last 30 days)
mongosh your_database --eval "
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
  db.ipam_webhook_deliveries.deleteMany({
    delivered_at: {\$lt: thirtyDaysAgo}
  });
"

# Clean up completed bulk jobs (keep last 7 days)
mongosh your_database --eval "
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  db.ipam_bulk_jobs.deleteMany({
    status: 'completed',
    completed_at: {\$lt: sevenDaysAgo}
  });
"
```

### Metrics to Monitor

**Key Performance Indicators:**
- Dashboard statistics response time (target: < 500ms)
- Capacity forecast response time (target: < 1s)
- Webhook delivery success rate (target: > 95%)
- Notification delivery latency (target: < 5s)
- Redis cache hit rate (target: > 80%)

**Alert Thresholds:**
- Webhook failure count > 5 consecutive failures
- Dashboard response time > 1s
- Notification queue depth > 1000
- Expired reservations not cleaned up for > 2 hours


## Additional Resources

### Documentation

- **API Usage Guide:** `docs/IPAM_ENHANCEMENTS_API_GUIDE.md`
  - Complete API reference with examples
  - Request/response formats
  - Error handling patterns
  - Workflow examples

- **Requirements Document:** `.kiro/specs/ipam-backend-enhancements/requirements.md`
  - Detailed feature requirements
  - Acceptance criteria
  - User stories

- **Design Document:** `.kiro/specs/ipam-backend-enhancements/design.md`
  - Architecture overview
  - Data models
  - API endpoint specifications
  - Implementation patterns

- **Implementation Status:** `.kiro/specs/ipam-backend-enhancements/IMPLEMENTATION_STATUS.md`
  - Current implementation status
  - Completed features
  - Test results

### Scripts

- **Migration Script:** `scripts/run_ipam_enhancements_migration.py`
  - Run migration: `uv run python scripts/run_ipam_enhancements_migration.py`
  - Check status: `uv run python scripts/run_ipam_enhancements_migration.py --status`
  - Rollback: `uv run python scripts/run_ipam_enhancements_migration.py --rollback`

- **Index Verification:** `scripts/verify_ipam_indexes.py`
  - Verify all indexes: `uv run python scripts/verify_ipam_indexes.py`

- **Test Suite:** `tests/test_ipam_enhancements.py`
  - Run all tests: `uv run pytest tests/test_ipam_enhancements.py -v`
  - Run specific tests: `uv run pytest tests/test_ipam_enhancements.py::TestReservations -v`

### Support

For issues or questions:

1. **Check the logs:**
   ```bash
   tail -f logs/app.log | grep -i ipam
   ```

2. **Verify database state:**
   ```bash
   uv run python scripts/run_ipam_enhancements_migration.py --status
   uv run python scripts/verify_ipam_indexes.py
   ```

3. **Test endpoints manually:**
   ```bash
   curl http://localhost:8000/docs
   # Use the interactive API documentation
   ```

4. **Review test results:**
   ```bash
   uv run pytest tests/test_ipam_enhancements.py -v --tb=short
   ```

5. **Check MongoDB directly:**
   ```bash
   mongosh your_database
   > db.ipam_reservations.find().limit(5).pretty()
   > db.ipam_notifications.countDocuments()
   ```

### Migration Checklist

Use this checklist to track your migration progress:

**Backend:**
- [ ] Database backup completed
- [ ] Migration script executed successfully
- [ ] All 8 collections created
- [ ] All indexes verified
- [ ] Application restarted
- [ ] New endpoints accessible
- [ ] Background tasks running
- [ ] Smoke tests passed

**Frontend:**
- [ ] API client updated with new methods
- [ ] Reservation management UI implemented
- [ ] Notification bell component added
- [ ] Dashboard statistics widget added
- [ ] User preferences persistence implemented
- [ ] Shareable links UI implemented
- [ ] Error handling updated

**Testing:**
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Performance tests passing
- [ ] Manual testing completed
- [ ] User acceptance testing completed

**Production:**
- [ ] Staging deployment successful
- [ ] Production backup completed
- [ ] Production migration executed
- [ ] Monitoring configured
- [ ] Alerts configured
- [ ] Documentation updated
- [ ] Team trained on new features

---

## Summary

The IPAM backend enhancements migration adds powerful new features while maintaining full backward compatibility. The migration is straightforward and can be completed in 15-30 minutes with zero downtime.

**Key Points:**
- ✅ Backward compatible - existing functionality unchanged
- ✅ Zero downtime - run migration while system is live
- ✅ Incremental adoption - implement features at your own pace
- ✅ Comprehensive testing - 73 test cases included
- ✅ Production ready - used in production environments

**Next Steps:**
1. Run the migration on your development environment
2. Test the new endpoints
3. Implement frontend features incrementally
4. Deploy to staging for user acceptance testing
5. Deploy to production with confidence

For detailed API usage examples, see `docs/IPAM_ENHANCEMENTS_API_GUIDE.md`.

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-13  
**Migration Script Version:** 1.0.0

