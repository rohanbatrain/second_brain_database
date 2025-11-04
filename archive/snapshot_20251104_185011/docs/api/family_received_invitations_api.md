# Family Received Invitations API - Complete Guide

## Overview

The **Received Invitations API** allows authenticated users to retrieve family invitations sent **TO them**. This is essential for implementing an in-app "Received Invitations" screen where users can view pending family invitations and respond to them directly within your mobile application.

**Endpoint:** `GET /family/my-invitations`

**Added:** October 2025  
**Status:** Production Ready ✅

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [Request Details](#request-details)
4. [Response Format](#response-format)
5. [Error Handling](#error-handling)
6. [Usage Examples](#usage-examples)
7. [Rate Limits](#rate-limits)
8. [Security Considerations](#security-considerations)
9. [Mobile App Integration](#mobile-app-integration)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Minimal Example

```bash
curl -X GET "https://your-api.com/family/my-invitations" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Accept: application/json"
```

### Expected Response

```json
[
  {
    "invitation_id": "inv_abc123xyz789",
    "family_id": "fam_def456uvw012",
    "family_name": "Johnson Family",
    "inviter_user_id": "user_123abc",
    "inviter_username": "john_johnson",
    "relationship_type": "child",
    "status": "pending",
    "expires_at": "2025-10-28T14:30:00Z",
    "created_at": "2025-10-21T14:30:00Z",
    "invitation_token": "tok_xyz789abc123"
  }
]
```

---

## Authentication

### Required Headers

```http
Authorization: Bearer YOUR_ACCESS_TOKEN
Accept: application/json
User-Agent: YourApp/1.0 (optional but recommended)
```

### Getting an Access Token

1. **Login to obtain token:**

```bash
curl -X POST "https://your-api.com/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password"
  }'
```

2. **Response contains access token:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_at": 1729612800
}
```

3. **Use the token in Authorization header:**

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Token Requirements

- ✅ Token must be valid (not expired)
- ✅ Token must not be blacklisted
- ✅ User must be verified
- ✅ Token version must match user's current version
- ✅ IP lockdown (if enabled) must pass
- ✅ User-Agent lockdown (if enabled) must pass

---

## Request Details

### Endpoint

```
GET /family/my-invitations
```

### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `status` | string | No | Filter invitations by status | `pending` |

#### Valid Status Values

- `pending` - Invitations awaiting response
- `accepted` - Invitations already accepted
- `declined` - Invitations that were declined
- `expired` - Invitations that expired before response
- `cancelled` - Invitations that were cancelled by the inviter

### Request Examples

#### Get All Invitations

```bash
curl -X GET "https://your-api.com/family/my-invitations" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Only Pending Invitations

```bash
curl -X GET "https://your-api.com/family/my-invitations?status=pending" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Accepted Invitations (History)

```bash
curl -X GET "https://your-api.com/family/my-invitations?status=accepted" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Response Format

### Success Response (200 OK)

Returns an array of invitation objects, sorted by creation date (newest first).

#### Response Schema

```json
[
  {
    "invitation_id": "string",
    "family_id": "string",
    "family_name": "string",
    "inviter_user_id": "string",
    "inviter_username": "string",
    "relationship_type": "string",
    "status": "string",
    "expires_at": "datetime",
    "created_at": "datetime",
    "invitation_token": "string | null"
  }
]
```

#### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `invitation_id` | string | Unique invitation identifier. Use this to accept/decline. |
| `family_id` | string | ID of the family you're invited to join |
| `family_name` | string | Human-readable name of the family |
| `inviter_user_id` | string | User ID of the person who sent the invitation |
| `inviter_username` | string | Username of the inviter (for display) |
| `relationship_type` | string | Proposed role: `parent`, `child`, `sibling`, etc. |
| `status` | string | Current state: `pending`, `accepted`, `declined`, `expired`, `cancelled` |
| `expires_at` | datetime | ISO 8601 timestamp when invitation becomes invalid |
| `created_at` | datetime | ISO 8601 timestamp when invitation was created |
| `invitation_token` | string\|null | Optional token for email-based acceptance |

#### Empty Response

When user has no invitations:

```json
[]
```

### Relationship Types

The `relationship_type` field indicates your proposed role in the family:

- `parent` - You'll be a parent in the family
- `child` - You'll be a child in the family
- `sibling` - You'll be a sibling
- `grandparent` - Grandparent role
- `grandchild` - Grandchild role
- `spouse` - Spouse/partner role
- `other` - Other family relationship

---

## Error Handling

### Error Response Format

All errors follow this structure:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message"
}
```

### Common Errors

#### 400 Bad Request - Invalid Status Filter

```json
{
  "error": "INVALID_STATUS_FILTER",
  "message": "Invalid status 'invalid'. Must be one of: pending, accepted, declined, expired, cancelled"
}
```

**Cause:** Provided status parameter is not valid.  
**Solution:** Use only: `pending`, `accepted`, `declined`, `expired`, or `cancelled`.

#### 401 Unauthorized - Missing or Invalid Token

```json
{
  "detail": "Could not validate credentials"
}
```

**Cause:** No Authorization header or invalid/expired token.  
**Solution:** Login to obtain a fresh access token.

#### 401 Unauthorized - Token Expired

```json
{
  "detail": "Token has expired"
}
```

**Cause:** Access token has exceeded its expiration time.  
**Solution:** Login again to get a new token.

#### 403 Forbidden - IP Lockdown

```json
{
  "detail": "IP address not in trusted list"
}
```

**Cause:** User has IP lockdown enabled and request IP is not trusted.  
**Solution:** Add your IP to trusted IPs or disable IP lockdown.

#### 403 Forbidden - User-Agent Lockdown

```json
{
  "detail": "User-Agent not in trusted list"
}
```

**Cause:** User has User-Agent lockdown enabled and request UA is not trusted.  
**Solution:** Add your User-Agent to trusted list or disable UA lockdown.

#### 429 Too Many Requests - Rate Limit

```json
{
  "detail": "Rate limit exceeded"
}
```

**Cause:** Exceeded 20 requests per hour limit.  
**Solution:** Wait before retrying. Rate limit resets hourly.

#### 500 Internal Server Error - Database Error

```json
{
  "error": "FAILED_TO_FETCH_INVITATIONS",
  "message": "Unable to retrieve family invitations. Please try again later."
}
```

**Cause:** Database connection issue or internal error.  
**Solution:** Retry after a few seconds. Contact support if persists.

---

## Usage Examples

### Example 1: Display Pending Invitations in Mobile App

```dart
// Flutter/Dart Example
import 'package:http/http.dart' as http;
import 'dart:convert';

Future<List<Invitation>> fetchPendingInvitations(String token) async {
  final response = await http.get(
    Uri.parse('https://your-api.com/family/my-invitations?status=pending'),
    headers: {
      'Authorization': 'Bearer $token',
      'Accept': 'application/json',
    },
  );

  if (response.statusCode == 200) {
    List<dynamic> jsonList = json.decode(response.body);
    return jsonList.map((json) => Invitation.fromJson(json)).toList();
  } else if (response.statusCode == 401) {
    throw Exception('Please login again');
  } else {
    throw Exception('Failed to load invitations');
  }
}

class Invitation {
  final String invitationId;
  final String familyName;
  final String inviterUsername;
  final String relationshipType;
  final DateTime expiresAt;

  Invitation({
    required this.invitationId,
    required this.familyName,
    required this.inviterUsername,
    required this.relationshipType,
    required this.expiresAt,
  });

  factory Invitation.fromJson(Map<String, dynamic> json) {
    return Invitation(
      invitationId: json['invitation_id'],
      familyName: json['family_name'],
      inviterUsername: json['inviter_username'],
      relationshipType: json['relationship_type'],
      expiresAt: DateTime.parse(json['expires_at']),
    );
  }
}
```

### Example 2: Python Script to Check Invitations

```python
import requests
from datetime import datetime

def get_my_invitations(token, status=None):
    """Fetch received family invitations."""
    url = "https://your-api.com/family/my-invitations"
    params = {"status": status} if status else {}
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        raise Exception("Authentication failed - please login again")
    elif response.status_code == 429:
        raise Exception("Rate limit exceeded - wait before retrying")
    else:
        raise Exception(f"Error {response.status_code}: {response.text}")

# Usage
token = "your_access_token_here"
pending_invitations = get_my_invitations(token, status="pending")

for inv in pending_invitations:
    print(f"Invitation from {inv['inviter_username']} to join {inv['family_name']}")
    print(f"  Role: {inv['relationship_type']}")
    print(f"  Expires: {inv['expires_at']}")
    print(f"  Invitation ID: {inv['invitation_id']}")
    print()
```

### Example 3: JavaScript/React Integration

```javascript
// React hook for fetching invitations
import { useState, useEffect } from 'react';

export const useReceivedInvitations = (token, status = null) => {
  const [invitations, setInvitations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchInvitations = async () => {
      try {
        const params = new URLSearchParams();
        if (status) params.append('status', status);
        
        const response = await fetch(
          `https://your-api.com/family/my-invitations?${params}`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Accept': 'application/json',
            },
          }
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        setInvitations(data);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchInvitations();
  }, [token, status]);

  return { invitations, loading, error };
};

// Usage in component
function InvitationsScreen() {
  const { invitations, loading, error } = useReceivedInvitations(
    localStorage.getItem('token'),
    'pending'
  );

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h2>Family Invitations</h2>
      {invitations.length === 0 ? (
        <p>No pending invitations</p>
      ) : (
        <ul>
          {invitations.map(inv => (
            <li key={inv.invitation_id}>
              <strong>{inv.family_name}</strong> - from {inv.inviter_username}
              <br />
              Role: {inv.relationship_type}
              <br />
              <button onClick={() => acceptInvitation(inv.invitation_id)}>
                Accept
              </button>
              <button onClick={() => declineInvitation(inv.invitation_id)}>
                Decline
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

---

## Rate Limits

### Limits

- **Rate:** 20 requests per hour per user
- **Window:** Rolling 3600-second window
- **Scope:** Per authenticated user (identified by user_id)

### Rate Limit Headers

The response includes rate limit information (implementation-dependent):

```http
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 1729612800
```

### Handling Rate Limits

```python
import time

def fetch_with_retry(token, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(
            "https://your-api.com/family/my-invitations",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            if attempt < max_retries - 1:
                wait_time = 60 * (attempt + 1)  # exponential backoff
                print(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception("Rate limit exceeded after retries")
        else:
            response.raise_for_status()
```

---

## Security Considerations

### Best Practices

1. **Never expose tokens in URLs**
   - ❌ Bad: `GET /family/my-invitations?token=abc123`
   - ✅ Good: Use Authorization header

2. **Store tokens securely**
   ```dart
   // Flutter: Use flutter_secure_storage
   final storage = FlutterSecureStorage();
   await storage.write(key: 'access_token', value: token);
   ```

3. **Handle token expiration**
   ```python
   def api_call_with_refresh(token, refresh_token):
       try:
           return get_my_invitations(token)
       except AuthenticationError:
           new_token = refresh_access_token(refresh_token)
           return get_my_invitations(new_token)
   ```

4. **Validate invitation data before display**
   ```javascript
   const isValidInvitation = (inv) => {
     return inv.invitation_id &&
            inv.family_name &&
            inv.status &&
            new Date(inv.expires_at) > new Date();
   };
   ```

5. **Use HTTPS only**
   - Never make requests over HTTP
   - Validate SSL certificates

### Data Privacy

- This endpoint only returns invitations where YOU are the invitee
- You cannot see invitations sent to other users
- Family admins use `/family/{familyId}/invitations` to see invitations they sent

---

## Mobile App Integration

### Complete Flutter Example

```dart
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ReceivedInvitationsScreen extends StatefulWidget {
  @override
  _ReceivedInvitationsScreenState createState() => 
      _ReceivedInvitationsScreenState();
}

class _ReceivedInvitationsScreenState 
    extends State<ReceivedInvitationsScreen> {
  final storage = FlutterSecureStorage();
  List<Invitation> invitations = [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    loadInvitations();
  }

  Future<void> loadInvitations() async {
    setState(() {
      loading = true;
      error = null;
    });

    try {
      final token = await storage.read(key: 'access_token');
      if (token == null) {
        throw Exception('Not logged in');
      }

      final response = await http.get(
        Uri.parse('https://your-api.com/family/my-invitations?status=pending'),
        headers: {
          'Authorization': 'Bearer $token',
          'Accept': 'application/json',
        },
      );

      if (response.statusCode == 200) {
        List<dynamic> jsonList = json.decode(response.body);
        setState(() {
          invitations = jsonList
              .map((json) => Invitation.fromJson(json))
              .toList();
          loading = false;
        });
      } else if (response.statusCode == 401) {
        setState(() {
          error = 'Please login again';
          loading = false;
        });
        // Navigate to login
      } else {
        throw Exception('Failed to load invitations');
      }
    } catch (e) {
      setState(() {
        error = e.toString();
        loading = false;
      });
    }
  }

  Future<void> respondToInvitation(String invitationId, String action) async {
    try {
      final token = await storage.read(key: 'access_token');
      final response = await http.post(
        Uri.parse('https://your-api.com/family/invitations/$invitationId/respond'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: json.encode({'action': action}),
      );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Invitation ${action}ed successfully')),
        );
        loadInvitations(); // Reload list
      } else {
        throw Exception('Failed to respond to invitation');
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return Scaffold(
        appBar: AppBar(title: Text('Family Invitations')),
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (error != null) {
      return Scaffold(
        appBar: AppBar(title: Text('Family Invitations')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error, size: 64, color: Colors.red),
              SizedBox(height: 16),
              Text(error!),
              ElevatedButton(
                onPressed: loadInvitations,
                child: Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (invitations.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: Text('Family Invitations')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.inbox, size: 64, color: Colors.grey),
              SizedBox(height: 16),
              Text('No pending invitations'),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: Text('Family Invitations')),
      body: RefreshIndicator(
        onRefresh: loadInvitations,
        child: ListView.builder(
          itemCount: invitations.length,
          itemBuilder: (context, index) {
            final inv = invitations[index];
            return Card(
              margin: EdgeInsets.all(8),
              child: ListTile(
                leading: Icon(Icons.family_restroom, size: 40),
                title: Text(inv.familyName,
                    style: TextStyle(fontWeight: FontWeight.bold)),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('From: ${inv.inviterUsername}'),
                    Text('Role: ${inv.relationshipType}'),
                    Text('Expires: ${inv.expiresAt.toLocal()}'),
                  ],
                ),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: Icon(Icons.check, color: Colors.green),
                      onPressed: () => respondToInvitation(
                          inv.invitationId, 'accept'),
                    ),
                    IconButton(
                      icon: Icon(Icons.close, color: Colors.red),
                      onPressed: () => respondToInvitation(
                          inv.invitationId, 'decline'),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class Invitation {
  final String invitationId;
  final String familyId;
  final String familyName;
  final String inviterUsername;
  final String relationshipType;
  final DateTime expiresAt;

  Invitation({
    required this.invitationId,
    required this.familyId,
    required this.familyName,
    required this.inviterUsername,
    required this.relationshipType,
    required this.expiresAt,
  });

  factory Invitation.fromJson(Map<String, dynamic> json) {
    return Invitation(
      invitationId: json['invitation_id'],
      familyId: json['family_id'],
      familyName: json['family_name'],
      inviterUsername: json['inviter_username'],
      relationshipType: json['relationship_type'],
      expiresAt: DateTime.parse(json['expires_at']),
    );
  }
}
```

---

## Troubleshooting

### Problem: Always returns empty array

**Symptoms:** API returns `[]` even though you expect invitations.

**Possible causes:**
1. No invitations have been sent to your account
2. All invitations have expired
3. Using wrong user account
4. Invitations were sent to a different email

**Solution:**
```bash
# Check if invitations exist (including expired)
curl -X GET "https://your-api.com/family/my-invitations" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check with explicit status
curl -X GET "https://your-api.com/family/my-invitations?status=expired" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Problem: 401 Unauthorized

**Symptoms:** Request returns 401 even with token.

**Possible causes:**
1. Token expired
2. Token blacklisted (password changed)
3. User not verified
4. Token format incorrect

**Solution:**
```python
# Verify token format
def validate_token_format(token):
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    return True

# Get fresh token
def login_and_retry():
    token_response = requests.post(
        "https://your-api.com/auth/login",
        json={"username": "...", "password": "..."}
    )
    new_token = token_response.json()['access_token']
    return get_my_invitations(new_token)
```

### Problem: 403 Forbidden with lockdown message

**Symptoms:** `"IP address not in trusted list"` or similar.

**Possible causes:**
1. IP lockdown enabled and your IP not trusted
2. User-Agent lockdown enabled and your UA not trusted

**Solution:**
1. Disable lockdowns temporarily via settings API
2. Add your IP/UA to trusted lists
3. Contact admin to whitelist your IP

### Problem: Missing family_name in response

**Symptoms:** Some invitations have `"family_name": "Unknown Family"`.

**Possible causes:**
1. Family was deleted after invitation sent
2. Database inconsistency

**Solution:**
- Filter out invitations with "Unknown Family" in your app
- These invitations are likely invalid and can be ignored

---

## Next Steps After Fetching Invitations

### Accepting an Invitation

```bash
curl -X POST "https://your-api.com/family/invitations/{invitation_id}/respond" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "accept"
  }'
```

### Declining an Invitation

```bash
curl -X POST "https://your-api.com/family/invitations/{invitation_id}/respond" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "decline"
  }'
```

### Checking Family Details

After accepting, get family details:

```bash
curl -X GET "https://your-api.com/family/my-families" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## API Changelog

### v1.0 (October 2025)
- ✅ Initial release
- ✅ Production-ready implementation
- ✅ Comprehensive error handling
- ✅ Rate limiting (20/hour)
- ✅ Status filtering support
- ✅ Full OpenAPI documentation

---

## Support

### Related Endpoints

- `GET /family/my-families` - List families you belong to
- `POST /family/invitations/{id}/respond` - Accept/decline invitation
- `GET /family/{familyId}/invitations` - Invitations sent by a family (admin only)

### Contact

For issues or questions:
- GitHub Issues: https://github.com/rohanbatrain/second_brain_database/issues
- API Documentation: https://your-api.com/docs

---

**Last Updated:** October 21, 2025  
**API Version:** v1.0  
**Status:** Production Ready ✅
