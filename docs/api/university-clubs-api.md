# University Clubs API Documentation

Complete API reference for the University Clubs Platform.

## Base URL

```
https://api.secondbraindatabase.com/api/v1
```

## Authentication

All endpoints require authentication via JWT token:

```http
Authorization: Bearer <your_jwt_token>
```

## HTTP Status Codes

- `200` - Success
- `201` - Created
- `204` - No Content (successful deletion)
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error

## Rate Limiting

- **Limit**: 1000 requests per hour per user
- **Headers**: 
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`

---

## Clubs Endpoints

### List All Clubs

```http
GET /clubs
```

**Query Parameters**:
- `category` (optional) - Filter by category
- `search` (optional) - Search club names
- `page` (optional, default: 1) - Page number
- `limit` (optional, default: 20) - Items per page

**Response** (`200 OK`):
```json
{
  "clubs": [
    {
      "club_id": "club_123",
      "name": "Robotics Club",
      "description": "Building and programming robots",
      "category": "Technology",
      "member_count": 45,
      "president_name": "John Doe",
      "is_member": false,
      "privacy": "public",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "pages": 8
}
```

### Get Club Details

```http
GET /clubs/{club_id}
```

**Response** (`200 OK`):
```json
{
  "club_id": "club_123",
  "name": "Robotics Club",
  "description": "Building and programming robots",
  "category": "Technology",
  "member_count": 45,
  "president": {
    "user_id": "user_456",
    "name": "John Doe",
    "email": "john@university.edu"
  },
  "officers": [
    {
      "user_id": "user_789",
      "name": "Jane Smith",
      "role": "Vice President"
    }
  ],
  "created_at": "2024-01-15T10:00:00Z",
  "meeting_schedule": "Every Friday 4-6 PM"
}
```

###Create Club

```http
POST /clubs
```

**Request Body**:
```json
{
  "name": "Photography Club",
  "description": "Exploring the art of photography",
  "category": "Arts",
  "privacy": "public",
  "meeting_schedule": "Every Wednesday 3-5 PM"
}
```

**Response** (`201 Created`):
```json
{
  "club_id": "club_new123",
  "name": "Photography Club",
  "status": "pending_approval",
  "message": "Club created successfully. Awaiting admin approval."
}
```

### Update Club

```http
PUT /clubs/{club_id}
```

**Permissions**: President or VP only

**Request Body**:
```json
{
  "description": "Updated description",
  "meeting_schedule": "Every Monday 4-6 PM"
}
```

**Response** (`200 OK`):
```json
{
  "club_id": "club_123",
  "message": "Club updated successfully"
}
```

---

## Members Endpoints

### List Club Members

```http
GET /clubs/{club_id}/members
```

**Response** (`200 OK`):
```json
{
  "members": [
    {
      "user_id": "user_123",
      "name": "Alice Johnson",
      "email": "alice@university.edu",
      "role": "President",
      "join_date": "2024-01-15T10:00:00Z",
      "attendance_rate": 0.85,
      "contribution_score": 120
    }
  ],
  "total": 45
}
```

### Join Club

```http
POST /clubs/{club_id}/join
```

**Response** (`200 OK`):
```json
{
  "message": "Successfully joined Robotics Club",
  "membership_id": "member_789"
}
```

### Assign Role

```http
PUT /clubs/{club_id}/members/{user_id}/role
```

**Permissions**: President only

**Request Body**:
```json
{
  "role": "Treasurer"
}
```

**Response** (`200 OK`):
```json
{
  "message": "Role assigned successfully"
}
```

### Award Badge

```http
POST /clubs/{club_id}/members/{user_id}/badges
```

**Request Body**:
```json
{
  "badge_type": "Event Champion",
  "note": "Attended 15 events this semester"
}
```

**Response** (`201 Created`):
```json
{
  "badge_id": "badge_456",
  "message": "Badge awarded successfully"
}
```

---

## Events Endpoints

### List Club Events

```http
GET /clubs/{club_id}/events
```

**Query Parameters**:
- `upcoming_only` (optional) - Only future events
- `start_date` (optional) - Filter from date
- `end_date` (optional) - Filter to date

**Response** (`200 OK`):
```json
{
  "events": [
    {
      "event_id": "event_123",
      "title": "Robot Building Workshop",
      "description": "Hands-on robot construction",
      "start_time": "2024-12-01T14:00:00Z",
      "end_time": "2024-12-01T17:00:00Z",
      "location": "Engineering Lab 101",
      "capacity": 30,
      "rsvp_count": 18,
      "is_rsvped": false
    }
  ]
}
```

### Create Event

```http
POST /clubs/{club_id}/events
```

**Request Body**:
```json
{
  "title": "Photography Contest",
  "description": "Submit your best photos",
  "start_time": "2024-12-15T10:00:00Z",
  "end_time": "2024-12-15T16:00:00Z",
  "location": "Art Building A",
  "capacity": 50,
  "is_recurring": false
}
```

**Response** (`201 Created`):
```json
{
  "event_id": "event_new456",
  "message": "Event created successfully"
}
```

### RSVP to Event

```http
POST /clubs/{club_id}/events/{event_id}/rsvp
```

**Response** (`200 OK`):
```json
{
  "message": "RSVP confirmed",
  "rsvp_id": "rsvp_789"
}
```

### Record Attendance

```http
POST /clubs/{club_id}/events/{event_id}/attendance
```

**Permissions**: Officers only

**Request Body**:
```json
{
  "attendees": ["user_123", "user_456", "user_789"]
}
```

**Response** (`200 OK`):
```json
{
  "message": "Attendance recorded for 3 members",
  "attendance_ids": ["att_1", "att_2", "att_3"]
}
```

---

## Analytics Endpoints

### Get Club Analytics

```http
GET /clubs/{club_id}/analytics
```

**Query Parameters**:
- `period` (optional) - `week`, `month`, `semester`, `year`

**Response** (`200 OK`):
```json
{
  "period": "month",
  "member_growth": {
    "new_members": 12,
    "total_members": 45,
    "growth_rate": 36.4
  },
  "event_metrics": {
    "total_events": 8,
    "average_attendance": 22.5,
    "rsvp_rate": 0.75,
    "no_show_rate": 0.15
  },
  "engagement_score": 87.3,
  "top_contributors": [
    {
      "user_id": "user_123",
      "name": "Alice Johnson",
      "score": 150
    }
  ]
}
```

### Get Member Analytics

```http
GET /clubs/{club_id}/members/{user_id}/analytics
```

**Response** (`200 OK`):
```json
{
  "user_id": "user_123",
  "attendance_rate": 0.92,
  "events_attended": 23,
  "contribution_score": 150,
  "badges_earned": 5,
  "join_date": "2024-01-15T10:00:00Z",
  "rank": "Top 10%"
}
```

---

## Communication Endpoints

### Send Announcement

```http
POST /clubs/{club_id}/announcements
```

**Permissions**: Officers only

**Request Body**:
```json
{
  "title": "Important Meeting",
  "message": "Emergency meeting tomorrow at 5 PM",
  "recipients": "all",  // "all", "officers", "members"
  "priority": "high"
}
```

**Response** (`201 Created`):
```json
{
  "announcement_id": "ann_456",
  "message": "Announcement sent to 45 members"
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Validation Error",
  "details": {
    "name": "Club name is required",
    "category": "Invalid category"
  }
}
```

### 401 Unauthorized
```json
{
  "error": "Authentication required",
  "message": "Please log in to access this resource"
}
```

### 403 Forbidden
```json
{
  "error": "Permission denied",
  "message": "Only club presidents can perform this action"
}
```

### 404 Not Found
```json
{
  "error": "Resource not found",
  "message": "Club with ID 'club_999' does not exist"
}
```

---

## SDK Examples

### Python

```python
from sbd_client import UniversityClubsAPI

api = UniversityClubsAPI(api_key="your_api_key")

# List clubs
clubs = api.clubs.list(category="Technology")

# Create event
event = api.events.create(
    club_id="club_123",
    title="Workshop",
    start_time="2024-12-01T14:00:00Z",
    capacity=30
)

# Record attendance
api.events.record_attendance(
    club_id="club_123",
    event_id="event_456",
    attendees=["user_1", "user_2"]
)
```

### TypeScript

```typescript
import { UniversityClubsClient } from '@sbd/clubs-sdk';

const client = new UniversityClubsClient({
  apiKey: 'your_api_key',
});

// List clubs
const clubs = await client.clubs.list({
  category: 'Technology',
});

// RSVP to event
await client.events.rsvp({
  clubId: 'club_123',
  eventId: 'event_456',
});

// Get analytics
const analytics = await client.analytics.getClubAnalytics({
  clubId: 'club_123',
  period: 'month',
});
```

---

## Webhooks

Subscribe to events:

### Available Events
- `club.created`
- `club.member.joined`
- `event.created`
- `event.rsvp.submitted`
- `announcement.sent`

### Webhook Payload Example

```json
{
  "event": "event.rsvp.submitted",
  "timestamp": "2024-11-20T14:30:00Z",
  "data": {
    "club_id": "club_123",
    "event_id": "event_456",
    "user_id": "user_789",
    "rsvp_id": "rsvp_999"
  }
}
```

---

**Last Updated**: November 2024  
**API Version**: 1.0  
**Support**: api-support@secondbraindatabase.com
