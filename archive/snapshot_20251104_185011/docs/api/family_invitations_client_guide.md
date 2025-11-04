# Family Invitations API - Client Handling Guide

## GET /family/{family_id}/invitations

### Response Behavior

**For Family Administrators:**
- Returns a list of invitation objects with full details
- Status: 200 OK

**For Non-Admin Family Members:**
- Returns an empty list `[]`
- Status: 200 OK
- No error is thrown

### Flutter Implementation

```dart
Future<List<Invitation>> getFamilyInvitations(String familyId) async {
  try {
    final response = await http.get(
      Uri.parse('$baseUrl/family/$familyId/invitations'),
      headers: {'Authorization': 'Bearer $token'},
    );

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);

      // Handle both admin (with data) and non-admin (empty list) cases
      if (data.isEmpty) {
        // User is not an admin, show appropriate UI
        return [];
      } else {
        // User is admin, parse the invitations
        return data.map((json) => Invitation.fromJson(json)).toList();
      }
    } else {
      throw Exception('Failed to load invitations');
    }
  } catch (e) {
    // Handle network errors, etc.
    rethrow;
  }
}
```

### UI Handling

```dart
class FamilyInvitationsScreen extends StatelessWidget {
  final List<Invitation> invitations;

  @override
  Widget build(BuildContext context) {
    if (invitations.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.lock_outline, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text(
              'Only family administrators can view invitations',
              style: TextStyle(fontSize: 16, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      itemCount: invitations.length,
      itemBuilder: (context, index) {
        return InvitationCard(invitation: invitations[index]);
      },
    );
  }
}
```

### Key Points

1. **No 403 Error**: The API never returns 403 for permission issues on this endpoint
2. **Empty List Means No Access**: An empty list indicates the user lacks admin permissions
3. **Graceful Degradation**: UI can show appropriate messaging for non-admin users
4. **Consistent Response Format**: Always returns a JSON array, never an error object