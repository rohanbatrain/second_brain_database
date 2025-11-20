# Flutter Family Invitations - Complete Integration Guide

**Last Updated:** October 21, 2025  
**API Version:** v1.0  
**Status:** Production Ready ✅

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Edge Cases & Validations](#edge-cases--validations)
3. [API Endpoints](#api-endpoints)
4. [Data Models](#data-models)
5. [Complete Flutter Implementation](#complete-flutter-implementation)
6. [Error Handling](#error-handling)
7. [Best Practices](#best-practices)
8. [Testing Checklist](#testing-checklist)

---

## Overview

This guide covers the complete family invitation system with all production-ready edge case handling. The system prevents duplicate invitations, spam, self-invites, and handles race conditions gracefully.

### Key Features

✅ **Send Invitations** - Invite users by email or username  
✅ **View Received Invitations** - See all invitations sent TO you  
✅ **Accept/Decline** - Respond to invitations  
✅ **Cancel Invitations** - Admins can cancel pending invitations  
✅ **Auto-Expiry** - Invitations expire after 7 days  
✅ **Anti-Spam** - 24-hour cooldown after declining  
✅ **Duplicate Prevention** - Cannot send duplicate pending invitations  

---

## Edge Cases & Validations

### 🚫 Prevented Edge Cases

The backend now handles these scenarios automatically:

| Edge Case | Backend Behavior | User Experience |
|-----------|------------------|-----------------|
| **Self-Invite** | Blocks invitation | Error: "You cannot invite yourself" |
| **Already Member** | Blocks invitation | Error: "User is already a member" |
| **Pending Invitation Exists** | Blocks duplicate | Error: "User already has a pending invitation (expires in X days)" |
| **Recently Declined** | Blocks re-invite for 24h | Error: "Please wait X hours before sending another" |
| **Expired Invitations** | Auto-cleanup to "expired" status | Old invitations automatically marked expired |
| **Concurrent Invites** | First wins, others blocked | Prevents race conditions |
| **Invalid Email/Username** | Blocks invitation | Error: "User not found" |
| **Non-Admin Sending** | Blocks invitation | Error: "Only family admins can invite" |
| **Family Member Limit** | Blocks invitation | Error: "Maximum family members limit reached (X/Y)" |
| **Invalid Relationship** | Blocks invitation | Error: "Invalid relationship type" |

### ⏱️ Time-Based Rules

- **Invitation Expiry:** 7 days from creation
- **Decline Cooldown:** 24 hours before re-inviting
- **Rate Limiting:** 20 invitations per hour per user

### 🔄 Status Lifecycle

```
pending → accepted (user accepts)
        → declined (user declines)
        → expired (7 days pass without response)
        → cancelled (admin cancels)
```

---

## API Endpoints

### 1. Send Family Invitation

**POST** `/family/{family_id}/invite`

```dart
// Request Body
{
  "identifier": "user@example.com",  // Email or username
  "relationship_type": "child",      // parent, child, sibling, etc.
  "identifier_type": "email"         // "email" or "username"
}
```

**Possible Errors:**
- `400` - Self-invite, duplicate invitation, recently declined
- `403` - Not admin
- `404` - User not found, family not found
- `429` - Rate limit exceeded (20/hour)

---

### 2. Get Received Invitations

**GET** `/family/my-invitations?status=pending`

Returns invitations sent **TO** the authenticated user.

**Query Parameters:**
- `status` (optional): `pending`, `accepted`, `declined`, `expired`, `cancelled`

**Response:**
```json
[
  {
    "invitation_id": "inv_abc123",
    "family_id": "fam_def456",
    "family_name": "Smith Family",
    "inviter_user_id": "user_789",
    "inviter_username": "john_smith",
    "relationship_type": "child",
    "status": "pending",
    "expires_at": "2025-10-28T10:00:00Z",
    "created_at": "2025-10-21T10:00:00Z",
    "invitation_token": "tok_xyz789"
  }
]
```

---

### 3. Accept/Decline Invitation

**POST** `/family/invitation/{invitation_id}/respond`

```dart
// Accept
{
  "action": "accept"
}

// Decline
{
  "action": "decline"
}
```

**Note:** Declining triggers a 24-hour cooldown before the same family can re-invite you.

---

### 4. Cancel Invitation (Admin Only)

**DELETE** `/family/{family_id}/invitations/{invitation_id}`

Cancels a pending invitation. Only admins can cancel invitations they sent.

---

### 5. View Sent Invitations (Admin View)

**GET** `/family/{family_id}/invitations`

Returns all invitations sent **BY** the family (admin view).

---

## Data Models

### Dart Models

```dart
// ReceivedInvitation.dart
class ReceivedInvitation {
  final String invitationId;
  final String familyId;
  final String familyName;
  final String inviterUserId;
  final String inviterUsername;
  final String relationshipType;
  final InvitationStatus status;
  final DateTime expiresAt;
  final DateTime createdAt;
  final String? invitationToken;

  ReceivedInvitation({
    required this.invitationId,
    required this.familyId,
    required this.familyName,
    required this.inviterUserId,
    required this.inviterUsername,
    required this.relationshipType,
    required this.status,
    required this.expiresAt,
    required this.createdAt,
    this.invitationToken,
  });

  factory ReceivedInvitation.fromJson(Map<String, dynamic> json) {
    return ReceivedInvitation(
      invitationId: json['invitation_id'] as String,
      familyId: json['family_id'] as String,
      familyName: json['family_name'] as String,
      inviterUserId: json['inviter_user_id'] as String,
      inviterUsername: json['inviter_username'] as String,
      relationshipType: json['relationship_type'] as String,
      status: InvitationStatus.fromString(json['status'] as String),
      expiresAt: DateTime.parse(json['expires_at'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      invitationToken: json['invitation_token'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'invitation_id': invitationId,
      'family_id': familyId,
      'family_name': familyName,
      'inviter_user_id': inviterUserId,
      'inviter_username': inviterUsername,
      'relationship_type': relationshipType,
      'status': status.value,
      'expires_at': expiresAt.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
      'invitation_token': invitationToken,
    };
  }

  // Helper: Check if invitation is expired
  bool get isExpired => DateTime.now().isAfter(expiresAt);

  // Helper: Days until expiry
  int get daysUntilExpiry => expiresAt.difference(DateTime.now()).inDays;

  // Helper: Can respond (pending and not expired)
  bool get canRespond => status == InvitationStatus.pending && !isExpired;
}

enum InvitationStatus {
  pending('pending'),
  accepted('accepted'),
  declined('declined'),
  expired('expired'),
  cancelled('cancelled');

  final String value;
  const InvitationStatus(this.value);

  static InvitationStatus fromString(String value) {
    return InvitationStatus.values.firstWhere(
      (e) => e.value == value,
      orElse: () => InvitationStatus.pending,
    );
  }
}

enum RelationshipType {
  parent('parent'),
  child('child'),
  sibling('sibling'),
  spouse('spouse'),
  grandparent('grandparent'),
  grandchild('grandchild'),
  uncle('uncle'),
  aunt('aunt'),
  nephew('nephew'),
  niece('niece'),
  cousin('cousin');

  final String value;
  const RelationshipType(this.value);

  static RelationshipType fromString(String value) {
    return RelationshipType.values.firstWhere(
      (e) => e.value == value,
      orElse: () => RelationshipType.child,
    );
  }

  String get displayName {
    switch (this) {
      case RelationshipType.parent:
        return 'Parent';
      case RelationshipType.child:
        return 'Child';
      case RelationshipType.sibling:
        return 'Sibling';
      case RelationshipType.spouse:
        return 'Spouse';
      case RelationshipType.grandparent:
        return 'Grandparent';
      case RelationshipType.grandchild:
        return 'Grandchild';
      case RelationshipType.uncle:
        return 'Uncle';
      case RelationshipType.aunt:
        return 'Aunt';
      case RelationshipType.nephew:
        return 'Nephew';
      case RelationshipType.niece:
        return 'Niece';
      case RelationshipType.cousin:
        return 'Cousin';
    }
  }
}
```

---

## Complete Flutter Implementation

### API Service

```dart
// family_invitation_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class FamilyInvitationService {
  final String baseUrl;
  final String Function() getToken; // Function to get current auth token

  FamilyInvitationService({
    required this.baseUrl,
    required this.getToken,
  });

  Map<String, String> get _headers => {
        'Authorization': 'Bearer ${getToken()}',
        'Content-Type': 'application/json',
      };

  /// Get invitations received by the current user
  Future<List<ReceivedInvitation>> getMyInvitations({
    InvitationStatus? status,
  }) async {
    try {
      final queryParams = status != null ? '?status=${status.value}' : '';
      final response = await http.get(
        Uri.parse('$baseUrl/family/my-invitations$queryParams'),
        headers: _headers,
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.map((json) => ReceivedInvitation.fromJson(json)).toList();
      } else if (response.statusCode == 401) {
        throw UnauthorizedException('Session expired. Please login again.');
      } else if (response.statusCode == 429) {
        throw RateLimitException('Too many requests. Please try again later.');
      } else {
        final error = json.decode(response.body);
        throw ApiException(
          error['message'] ?? 'Failed to fetch invitations',
          statusCode: response.statusCode,
        );
      }
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  /// Send a family invitation
  Future<void> sendInvitation({
    required String familyId,
    required String identifier,
    required String identifierType, // "email" or "username"
    required RelationshipType relationshipType,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/family/$familyId/invite'),
        headers: _headers,
        body: json.encode({
          'identifier': identifier,
          'identifier_type': identifierType,
          'relationship_type': relationshipType.value,
        }),
      );

      if (response.statusCode == 201) {
        // Success
        return;
      } else if (response.statusCode == 400) {
        final error = json.decode(response.body);
        final message = error['message'] ?? 'Invalid invitation';
        
        // Handle specific edge cases with user-friendly messages
        if (message.contains('already has a pending invitation')) {
          throw DuplicateInvitationException(message);
        } else if (message.contains('recently declined')) {
          throw RecentlyDeclinedException(message);
        } else if (message.contains('already a member')) {
          throw AlreadyMemberException(message);
        } else if (message.contains('cannot invite yourself')) {
          throw SelfInviteException('You cannot invite yourself to a family');
        } else {
          throw ValidationException(message);
        }
      } else if (response.statusCode == 403) {
        throw PermissionDeniedException('Only family admins can send invitations');
      } else if (response.statusCode == 404) {
        final error = json.decode(response.body);
        throw NotFoundException(error['message'] ?? 'User or family not found');
      } else if (response.statusCode == 429) {
        throw RateLimitException('Too many invitations sent. Limit: 20 per hour.');
      } else {
        final error = json.decode(response.body);
        throw ApiException(
          error['message'] ?? 'Failed to send invitation',
          statusCode: response.statusCode,
        );
      }
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  /// Accept an invitation
  Future<void> acceptInvitation(String invitationId) async {
    return _respondToInvitation(invitationId, 'accept');
  }

  /// Decline an invitation
  Future<void> declineInvitation(String invitationId) async {
    return _respondToInvitation(invitationId, 'decline');
  }

  Future<void> _respondToInvitation(String invitationId, String action) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/family/invitation/$invitationId/respond'),
        headers: _headers,
        body: json.encode({'action': action}),
      );

      if (response.statusCode == 200) {
        return;
      } else if (response.statusCode == 404) {
        throw NotFoundException('Invitation not found or expired');
      } else if (response.statusCode == 400) {
        final error = json.decode(response.body);
        throw ValidationException(error['message'] ?? 'Invalid response');
      } else {
        final error = json.decode(response.body);
        throw ApiException(
          error['message'] ?? 'Failed to respond to invitation',
          statusCode: response.statusCode,
        );
      }
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  /// Cancel an invitation (admin only)
  Future<void> cancelInvitation({
    required String familyId,
    required String invitationId,
  }) async {
    try {
      final response = await http.delete(
        Uri.parse('$baseUrl/family/$familyId/invitations/$invitationId'),
        headers: _headers,
      );

      if (response.statusCode == 200) {
        return;
      } else if (response.statusCode == 403) {
        throw PermissionDeniedException('Only admins can cancel invitations');
      } else if (response.statusCode == 404) {
        throw NotFoundException('Invitation not found');
      } else {
        final error = json.decode(response.body);
        throw ApiException(
          error['message'] ?? 'Failed to cancel invitation',
          statusCode: response.statusCode,
        );
      }
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }
}

// Custom Exceptions
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  ApiException(this.message, {this.statusCode});
  @override
  String toString() => message;
}

class UnauthorizedException extends ApiException {
  UnauthorizedException(String message) : super(message, statusCode: 401);
}

class PermissionDeniedException extends ApiException {
  PermissionDeniedException(String message) : super(message, statusCode: 403);
}

class NotFoundException extends ApiException {
  NotFoundException(String message) : super(message, statusCode: 404);
}

class RateLimitException extends ApiException {
  RateLimitException(String message) : super(message, statusCode: 429);
}

class ValidationException extends ApiException {
  ValidationException(String message) : super(message, statusCode: 400);
}

class DuplicateInvitationException extends ValidationException {
  DuplicateInvitationException(String message) : super(message);
}

class RecentlyDeclinedException extends ValidationException {
  RecentlyDeclinedException(String message) : super(message);
}

class AlreadyMemberException extends ValidationException {
  AlreadyMemberException(String message) : super(message);
}

class SelfInviteException extends ValidationException {
  SelfInviteException(String message) : super(message);
}
```

---

### UI Widget - Received Invitations Screen

```dart
// received_invitations_screen.dart
import 'package:flutter/material.dart';

class ReceivedInvitationsScreen extends StatefulWidget {
  const ReceivedInvitationsScreen({Key? key}) : super(key: key);

  @override
  State<ReceivedInvitationsScreen> createState() =>
      _ReceivedInvitationsScreenState();
}

class _ReceivedInvitationsScreenState extends State<ReceivedInvitationsScreen> {
  final FamilyInvitationService _service = FamilyInvitationService(
    baseUrl: 'https://your-api.com',
    getToken: () => 'YOUR_TOKEN', // Get from auth service
  );

  List<ReceivedInvitation> _invitations = [];
  bool _loading = true;
  String? _error;
  InvitationStatus _selectedStatus = InvitationStatus.pending;

  @override
  void initState() {
    super.initState();
    _loadInvitations();
  }

  Future<void> _loadInvitations() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final invitations = await _service.getMyInvitations(
        status: _selectedStatus,
      );
      setState(() {
        _invitations = invitations;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _acceptInvitation(ReceivedInvitation invitation) async {
    try {
      await _service.acceptInvitation(invitation.invitationId);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Joined ${invitation.familyName}!'),
          backgroundColor: Colors.green,
        ),
      );
      _loadInvitations();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to accept: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _declineInvitation(ReceivedInvitation invitation) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Decline Invitation'),
        content: Text(
          'Are you sure you want to decline the invitation to ${invitation.familyName}?\n\n'
          'Note: They cannot send you another invitation for 24 hours.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('CANCEL'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('DECLINE'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        await _service.declineInvitation(invitation.invitationId);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Invitation declined'),
            backgroundColor: Colors.orange,
          ),
        );
        _loadInvitations();
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to decline: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Family Invitations'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadInvitations,
          ),
        ],
      ),
      body: Column(
        children: [
          // Status Filter
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.all(8),
            child: Row(
              children: InvitationStatus.values.map((status) {
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: ChoiceChip(
                    label: Text(_getStatusLabel(status)),
                    selected: _selectedStatus == status,
                    onSelected: (selected) {
                      if (selected) {
                        setState(() => _selectedStatus = status);
                        _loadInvitations();
                      }
                    },
                  ),
                );
              }).toList(),
            ),
          ),

          // Content
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.error_outline,
                                size: 48, color: Colors.red),
                            const SizedBox(height: 16),
                            Text(_error!,
                                style: const TextStyle(color: Colors.red)),
                            const SizedBox(height: 16),
                            ElevatedButton(
                              onPressed: _loadInvitations,
                              child: const Text('Retry'),
                            ),
                          ],
                        ),
                      )
                    : _invitations.isEmpty
                        ? Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.mail_outline, size: 64),
                                const SizedBox(height: 16),
                                Text(
                                  'No ${_selectedStatus.value} invitations',
                                  style: Theme.of(context).textTheme.titleLarge,
                                ),
                              ],
                            ),
                          )
                        : RefreshIndicator(
                            onRefresh: _loadInvitations,
                            child: ListView.builder(
                              itemCount: _invitations.length,
                              itemBuilder: (context, index) {
                                final invitation = _invitations[index];
                                return InvitationCard(
                                  invitation: invitation,
                                  onAccept: () => _acceptInvitation(invitation),
                                  onDecline: () =>
                                      _declineInvitation(invitation),
                                );
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }

  String _getStatusLabel(InvitationStatus status) {
    switch (status) {
      case InvitationStatus.pending:
        return 'Pending';
      case InvitationStatus.accepted:
        return 'Accepted';
      case InvitationStatus.declined:
        return 'Declined';
      case InvitationStatus.expired:
        return 'Expired';
      case InvitationStatus.cancelled:
        return 'Cancelled';
    }
  }
}

class InvitationCard extends StatelessWidget {
  final ReceivedInvitation invitation;
  final VoidCallback onAccept;
  final VoidCallback onDecline;

  const InvitationCard({
    Key? key,
    required this.invitation,
    required this.onAccept,
    required this.onDecline,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final isPending = invitation.status == InvitationStatus.pending;
    final isExpired = invitation.isExpired;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                CircleAvatar(
                  child: Text(invitation.familyName[0].toUpperCase()),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        invitation.familyName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        'from @${invitation.inviterUsername}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                _buildStatusChip(invitation.status),
              ],
            ),

            const SizedBox(height: 12),

            // Details
            Row(
              children: [
                const Icon(Icons.people, size: 16),
                const SizedBox(width: 8),
                Text('Role: ${_capitalize(invitation.relationshipType)}'),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(Icons.schedule, size: 16),
                const SizedBox(width: 8),
                Text(_getExpiryText()),
              ],
            ),

            // Actions (only for pending invitations)
            if (isPending && !isExpired) ...[
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: onDecline,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.red,
                      ),
                      child: const Text('Decline'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: onAccept,
                      child: const Text('Accept'),
                    ),
                  ),
                ],
              ),
            ],

            // Expired warning
            if (isPending && isExpired) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.orange.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Row(
                  children: const [
                    Icon(Icons.warning, size: 16, color: Colors.orange),
                    SizedBox(width: 8),
                    Text('This invitation has expired'),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildStatusChip(InvitationStatus status) {
    Color color;
    String label;

    switch (status) {
      case InvitationStatus.pending:
        color = Colors.blue;
        label = 'Pending';
        break;
      case InvitationStatus.accepted:
        color = Colors.green;
        label = 'Accepted';
        break;
      case InvitationStatus.declined:
        color = Colors.orange;
        label = 'Declined';
        break;
      case InvitationStatus.expired:
        color = Colors.grey;
        label = 'Expired';
        break;
      case InvitationStatus.cancelled:
        color = Colors.red;
        label = 'Cancelled';
        break;
    }

    return Chip(
      label: Text(label, style: TextStyle(color: color, fontSize: 12)),
      backgroundColor: color.withOpacity(0.1),
      padding: EdgeInsets.zero,
    );
  }

  String _getExpiryText() {
    if (invitation.status != InvitationStatus.pending) {
      return 'Received ${_formatDate(invitation.createdAt)}';
    }

    final days = invitation.daysUntilExpiry;
    if (days < 0) {
      return 'Expired';
    } else if (days == 0) {
      return 'Expires today';
    } else if (days == 1) {
      return 'Expires tomorrow';
    } else {
      return 'Expires in $days days';
    }
  }

  String _formatDate(DateTime date) {
    return '${date.day}/${date.month}/${date.year}';
  }

  String _capitalize(String text) {
    if (text.isEmpty) return text;
    return text[0].toUpperCase() + text.substring(1);
  }
}
```

---

## Error Handling

### Error Response Format

All API errors follow this structure:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message"
}
```

### Error Code Reference

| HTTP Status | Error Code | Meaning | User Action |
|-------------|-----------|---------|-------------|
| 400 | `INVALID_STATUS_FILTER` | Invalid status parameter | Fix query param |
| 400 | `VALIDATION_ERROR` | Duplicate invite, self-invite, etc. | Show error, prevent retry |
| 401 | `UNAUTHORIZED` | Invalid/expired token | Redirect to login |
| 403 | `INSUFFICIENT_PERMISSIONS` | Not admin | Show "Admin only" message |
| 404 | `NOT_FOUND` | User/family/invitation not found | Show "Not found" message |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests (20/hour) | Show "Try again later" |
| 500 | `INTERNAL_SERVER_ERROR` | Server error | Show generic error, retry later |

### User-Friendly Error Messages

Map backend errors to user-friendly messages:

```dart
String getUserFriendlyError(ApiException e) {
  if (e is DuplicateInvitationException) {
    return 'This person already has a pending invitation. Please wait for them to respond.';
  } else if (e is RecentlyDeclinedException) {
    return 'This person recently declined. Please wait 24 hours before inviting again.';
  } else if (e is AlreadyMemberException) {
    return 'This person is already a member of your family.';
  } else if (e is SelfInviteException) {
    return 'You cannot invite yourself to a family.';
  } else if (e is RateLimitException) {
    return 'You\'ve sent too many invitations. Please try again in an hour.';
  } else if (e is PermissionDeniedException) {
    return 'Only family admins can send invitations.';
  } else if (e is NotFoundException) {
    return 'User not found. Please check the email/username.';
  } else if (e is UnauthorizedException) {
    return 'Your session has expired. Please login again.';
  } else {
    return 'Something went wrong. Please try again.';
  }
}
```

---

## Best Practices

### 1. **Refresh After Actions**

Always refresh the invitation list after accept/decline/cancel:

```dart
await _service.acceptInvitation(invitationId);
await _loadInvitations(); // Refresh list
```

### 2. **Show Confirmation Dialogs**

For destructive actions (decline, cancel), show confirmation:

```dart
final confirmed = await showDialog<bool>(
  context: context,
  builder: (context) => AlertDialog(
    title: const Text('Decline Invitation'),
    content: const Text('Are you sure? They cannot re-invite you for 24 hours.'),
    actions: [
      TextButton(child: const Text('CANCEL'), onPressed: () => Navigator.pop(context, false)),
      TextButton(child: const Text('DECLINE'), onPressed: () => Navigator.pop(context, true)),
    ],
  ),
);
```

### 3. **Handle Expired Invitations**

Check `invitation.isExpired` before showing accept/decline buttons:

```dart
if (invitation.status == InvitationStatus.pending && !invitation.isExpired) {
  // Show action buttons
}
```

### 4. **Offline Support**

Cache invitations locally for offline viewing:

```dart
// Save to local storage after fetching
await _storage.saveInvitations(_invitations);

// Load from cache first, then refresh
_invitations = await _storage.getInvitations();
setState(() {});
_loadInvitations(); // Refresh from server
```

### 5. **Badge Notifications**

Show badge count for pending invitations:

```dart
Future<int> getPendingInvitationCount() async {
  final invitations = await _service.getMyInvitations(
    status: InvitationStatus.pending,
  );
  return invitations.where((inv) => !inv.isExpired).length;
}
```

### 6. **Error Retry with Exponential Backoff**

For network errors, implement retry logic:

```dart
Future<List<ReceivedInvitation>> _loadWithRetry({int maxRetries = 3}) async {
  int attempt = 0;
  while (attempt < maxRetries) {
    try {
      return await _service.getMyInvitations();
    } catch (e) {
      attempt++;
      if (attempt >= maxRetries) rethrow;
      await Future.delayed(Duration(seconds: 2 * attempt)); // Exponential backoff
    }
  }
  throw Exception('Max retries exceeded');
}
```

---

## Testing Checklist

### ✅ Functional Tests

- [ ] **Send invitation with valid email** → Success
- [ ] **Send invitation with invalid email** → 404 error
- [ ] **Send duplicate invitation** → 400 error with clear message
- [ ] **Invite yourself** → 400 error "cannot invite yourself"
- [ ] **Invite existing member** → 400 error "already a member"
- [ ] **Send 21 invitations in 1 hour** → 429 rate limit error on 21st
- [ ] **Accept invitation** → Joins family successfully
- [ ] **Decline invitation** → Cannot be re-invited for 24h
- [ ] **Try to re-invite after decline within 24h** → 400 error
- [ ] **Re-invite after 24h cooldown** → Success
- [ ] **Cancel pending invitation (admin)** → Success
- [ ] **Cancel invitation (non-admin)** → 403 error
- [ ] **Respond to expired invitation** → 404 or 400 error
- [ ] **Filter by status (pending, accepted, declined, expired, cancelled)** → Correct results

### ✅ UI Tests

- [ ] Invitation list loads correctly
- [ ] Empty state shows when no invitations
- [ ] Loading state shows during fetch
- [ ] Error state shows with retry button
- [ ] Status filter chips work
- [ ] Accept button joins family and refreshes list
- [ ] Decline button shows confirmation dialog
- [ ] Expired invitations show warning message
- [ ] Pull-to-refresh works
- [ ] Badge count updates after actions

### ✅ Edge Case Tests

- [ ] Concurrent invitations to same user (first wins)
- [ ] Invitation expires while user is viewing
- [ ] Network error during accept/decline
- [ ] Token expires during operation
- [ ] Multiple admins sending invitations
- [ ] Deleting family while invitation pending

---

## API Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /family/{family_id}/invite` | 20 requests | 1 hour |
| `GET /family/my-invitations` | 20 requests | 1 hour |
| `POST /family/invitation/{id}/respond` | No limit | - |
| `DELETE /family/{family_id}/invitations/{id}` | No limit | - |

---

## Support & Questions

For questions or issues:
- **Backend Repo:** [second_brain_database](https://github.com/rohanbatrain/second_brain_database)
- **API Documentation:** `/docs/api/family_received_invitations_api.md`
- **Contact:** rohan@example.com

---

**End of Guide** 🎉
