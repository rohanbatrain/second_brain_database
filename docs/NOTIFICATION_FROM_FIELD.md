# Notification "From" Field — Contract & Frontend Guidance

This document explains why the UI showed a blank "From:" value, what changed on the backend, and how the frontend should read and render the canonical "From" information for family notifications.

Location (backend change)
- File updated: `src/second_brain_database/managers/family_manager.py`
- Helpers updated to include canonical from fields for new notifications:
  - `_notify_admins_token_request`
  - `_send_token_request_notification`
  - `_send_token_transfer_notification`

Summary of the problem
- The app UI expects a canonical "From" value in notification payloads (e.g., `data.from_username` or similar).
- Older server code included requester/approver details only in ad-hoc nested keys (for example `data.requester_username`) but not a consistent `from_user_id` / `from_username` pair.
- The UI shows "From:" with no value when the expected canonical field is absent.

What we changed (server)
- All newly created family notification payloads now include a canonical pair in the `data` object:
  - `from_user_id` (nullable string) — the user id who initiated the action, or `null` for system
  - `from_username` (string) — the display name or "System" when applicable

- Additionally, token-request notifications include the requester fields for redundancy:
  - `requester_user_id`
  - `requester_username`

These fields are placed under `notification.data` (not at top-level) to maintain backwards-compatibility with existing UI logic that reads `data`.

Data contract (canonical)
- Collection: `family_notifications`
- Document (relevant fields):

```json
{
  "notification_id": "not_...",
  "family_id": "fam_...",
  "recipient_user_ids": ["user1", "user2"],
  "type": "token_request_created",
  "title": "New Token Request",
  "message": "alice requested 500 tokens",
  "data": {
    "request_id": "req_...",
    "requester_user_id": "alice_id",
    "requester_username": "alice",
    "from_user_id": "alice_id",        // canonical
    "from_username": "alice",         // canonical
    "amount": 500,
    "reason": "need new",
    "expires_at": "2025-10-24T12:34:56Z"
  },
  "status": "sent",
  "created_at": "2025-10-23T12:00:00Z"
}
```

Example: approved token request -> token_transfer_completed

```json
{
  "type": "token_transfer_completed",
  "title": "Tokens Transferred",
  "message": "500 tokens have been transferred to your account by bob",
  "data": {
    "amount": 500,
    "approved_by": "bob_id",
    "request_id": "req_...",
    "transfer_completed": true,
    "from_user_id": "bob_id",
    "from_username": "bob"
  }
}
```

Frontend guidance (how to render "From:")
- Preferred canonical path: `notification.data.from_username`
- Fallbacks (in order):
  1. `notification.data.from_username`
  2. `notification.data.requester_username` (older notifications)
  3. `notification.data.approver_username` or `notification.data.approved_by_username` (if you use that naming)
  4. literal `"System"` or `"Unknown"`

Small Flutter snippet (example) — adapt to your codebase:

```dart
String renderFrom(Map<String, dynamic> notification) {
  final data = notification['data'] ?? {};
  return (data['from_username'] as String?)
      ?? (data['requester_username'] as String?)
      ?? (data['approver_username'] as String?)
      ?? 'System';
}

// Usage in widget
Text('From: ${renderFrom(notification)}');
```

Notes:
- The new canonical fields will be present on notifications created after the backend update. Old notifications will not be updated automatically unless you run a backfill.

Backfill (optional but recommended)
- To update older `family_notifications` documents with missing canonical fields, run a safe idempotent script that:
  1. Finds notifications missing `data.from_username`.
  2. Checks existing `data` fields (`requester_user_id`, `requester_username`, `approved_by`, etc.) to populate `from_user_id`/`from_username`.
  3. Writes the fields back only when missing (i.e., `setOnInsert` or `$set` only for absent keys).

Safe backfill pseudo-script (Python outline)

```python
# Run in dev/maintenance window. Test first on a few docs.
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')
db = client['<your_db>']
coll = db['family_notifications']

query = {'$or': [{'data.from_username': {'$exists': False}}, {'data.from_user_id': {'$exists': False}}]}
for doc in coll.find(query).limit(500):
    data = doc.get('data', {})
    update = {}
    # Try to infer
    if 'from_username' not in data:
        if 'requester_username' in data:
            update['data.from_username'] = data['requester_username']
        elif 'requester_user_id' in data:
            # optionally resolve username from users collection
            user = db['users'].find_one({'_id': data['requester_user_id']}, {'username': 1})
            if user:
                update['data.from_username'] = user['username']
            else:
                update['data.from_username'] = 'Unknown'
    if 'from_user_id' not in data:
        if 'requester_user_id' in data:
            update['data.from_user_id'] = data['requester_user_id']
        elif 'approved_by' in data:
            update['data.from_user_id'] = data['approved_by']

    if update:
        coll.update_one({'_id': doc['_id']}, {'$set': update})
```

Verification steps (manual)
1. Restart backend service (if you haven't already).
2. In dev environment, create a token request from User A (via API or frontend).
3. Approve the request as admin (User B).
4. Inspect DB: `db.family_notifications.find({ 'data.request_id': '<req id>' }).pretty()` — verify `data.from_username` exists and equals the expected username.
5. Open the app and refresh the notifications page. The card should show "From: <username>".

What frontend needs to change
- Minimal change: change the UI code that renders "From:" to use the canonical path with fallbacks above. This is a small, low-risk change and will make all notifications (old and new) display sensibly.

Suggested commit message for frontend change
- `notifications: use canonical notification.data.from_username with fallbacks to requester_username/approved_by`.

Contact / questions
- If you want, I can provide the backfill script as a runnable script and run it (dev only). I can also create a tiny PR with the frontend fallback snippet if you point me at the UI file to modify.


---
Generated: 2025-10-23
