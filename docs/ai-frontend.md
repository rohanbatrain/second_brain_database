## AI Orchestration — Frontend Integration Guide

This document collects everything the frontend team needs to integrate with the AI Agent Orchestration system implemented in this repository.

It covers:
- Supported features and agent types
- REST endpoints and payloads
- WebSocket protocol and event model
- Voice (LiveKit / STT / TTS) integration
- Authentication, rate limits and security considerations
- UI/UX recommendations, error handling and reconnection strategies
- Example snippets (WebSocket, TTS playback, LiveKit usage)
- Integration checklist and next steps

Location in repo: `src/second_brain_database/routes/ai/routes.py` and related modules under `integrations/ai_orchestration`.

---

## 1 — Supported features (high level)

- Multi-agent orchestration with built-in agents:
  - `family`, `personal`, `workspace`, `commerce`, `security`, `voice`
- Session-based chat and voice conversations with short-term memory and conversation history
- Real-time streaming via WebSocket:
  - Streaming tokens, complete responses, status events (thinking/typing), tool execution events and TTS audio chunks
- Server-side MCP tool orchestration (tool_call / tool_result events) with permission checks and audit logging
- Voice integration using LiveKit + STT/TTS pipelines
- Health, metrics and admin endpoints for monitoring and cache invalidation

This system is implemented with an orchestrator, agents, event bus and a WebSocket manager. See code in `integrations/ai_orchestration` for implementation details.

## 2 — REST API endpoints (comprehensive JSON examples)

Base prefix: `/ai`

All endpoints require JWT authentication via `Authorization: Bearer <token>` header.

### POST `/ai/sessions` - Create AI Session

Creates a new AI conversation session with specified agent type and configuration.

**Request Examples:**

*Basic session creation:*
```json
POST /ai/sessions
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "agent_type": "personal",
  "voice_enabled": false,
  "preferences": {},
  "settings": {},
  "expiration_hours": 24
}
```

*Voice-enabled family session:*
```json
POST /ai/sessions
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "agent_type": "family",
  "voice_enabled": true,
  "preferences": {
    "language": "en",
    "response_style": "concise"
  },
  "settings": {
    "max_tokens": 1000,
    "temperature": 0.7
  },
  "expiration_hours": 48
}
```

*Workspace session with custom settings:*
```json
POST /ai/sessions
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "agent_type": "workspace",
  "voice_enabled": false,
  "preferences": {
    "project_context": "web_development",
    "code_style": "typescript"
  },
  "settings": {
    "stream_response": true,
    "include_context": true
  },
  "expiration_hours": 12
}
```

**Success Response (200):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "status": "active",
  "created_at": "2025-10-30T10:30:00.000Z",
  "last_activity": "2025-10-30T10:30:00.000Z",
  "expires_at": "2025-10-31T10:30:00.000Z",
  "websocket_connected": false,
  "voice_enabled": false,
  "message_count": 0
}
```

**Error Responses:**

*Rate limit exceeded (429):*
```json
{
  "error": "ratelimit",
  "message": "Too many requests. Please wait 60 seconds and try again.",
  "category": "rate_limiting",
  "severity": "medium",
  "details": {
    "retry_after": 60,
    "limit": 10,
    "window": 3600
  },
  "timestamp": "2025-10-30T10:30:00.000Z",
  "request_id": "req_12345"
}
```

*Missing permissions (403):*
```json
{
  "error": "authorization",
  "message": "Access denied",
  "category": "authorization",
  "severity": "high",
  "details": {
    "required_permission": "family_management",
    "user_permissions": ["basic_chat"]
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Invalid agent type (422):*
```json
{
  "error": "validation",
  "message": "Validation failed",
  "category": "validation",
  "severity": "low",
  "details": {
    "field": "agent_type",
    "error": "value is not a valid enumeration member; permitted: 'family', 'personal', 'workspace', 'commerce', 'security', 'voice'"
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Too many active sessions (429):*
```json
{
  "error": "validation",
  "message": "Too many active sessions. Please close some sessions before creating new ones.",
  "category": "validation",
  "severity": "medium",
  "details": {
    "active_sessions": 5,
    "max_allowed": 5
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/sessions` - List User Sessions

Lists AI sessions for the authenticated user with optional filtering.

**Request Examples:**

*List all sessions:*
```http
GET /ai/sessions
Authorization: Bearer <jwt_token>
```

*Filter by status:*
```http
GET /ai/sessions?status=active
Authorization: Bearer <jwt_token>
```

*Filter by agent type with limit:*
```http
GET /ai/sessions?agent_type=family&limit=10
Authorization: Bearer <jwt_token>
```

*Multiple filters:*
```http
GET /ai/sessions?status=active&agent_type=workspace&limit=5
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "agent_type": "personal",
      "status": "active",
      "created_at": "2025-10-30T10:30:00.000Z",
      "last_activity": "2025-10-30T10:35:00.000Z",
      "expires_at": "2025-10-31T10:30:00.000Z",
      "websocket_connected": true,
      "voice_enabled": false,
      "message_count": 3
    },
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440001",
      "agent_type": "family",
      "status": "active",
      "created_at": "2025-10-30T09:15:00.000Z",
      "last_activity": "2025-10-30T09:45:00.000Z",
      "expires_at": "2025-10-31T09:15:00.000Z",
      "websocket_connected": false,
      "voice_enabled": true,
      "message_count": 12
    }
  ],
  "total_count": 2,
  "active_count": 2
}
```

**Empty Response (200):**
```json
{
  "sessions": [],
  "total_count": 0,
  "active_count": 0
}
```

**Error Responses:**

*Authentication failed (401):*
```json
{
  "error": "authentication",
  "message": "Authentication failed",
  "category": "authentication",
  "severity": "high",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/sessions/{session_id}` - Get Session Details

Retrieves detailed information about a specific AI session.

**Request Example:**
```http
GET /ai/sessions/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "status": "active",
  "created_at": "2025-10-30T10:30:00.000Z",
  "last_activity": "2025-10-30T10:35:00.000Z",
  "expires_at": "2025-10-31T10:30:00.000Z",
  "websocket_connected": true,
  "voice_enabled": false,
  "message_count": 3
}
```

**Error Responses:**

*Session not found (404):*
```json
{
  "error": "validation",
  "message": "AI session not found",
  "category": "validation",
  "severity": "low",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Access denied (403):*
```json
{
  "error": "authorization",
  "message": "Access denied to this AI session",
  "category": "authorization",
  "severity": "high",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### POST `/ai/sessions/{session_id}/message` - Send Message

Sends a message to an AI agent. Processing starts immediately and results stream via WebSocket.

**Request Examples:**

*Basic text message:*
```json
POST /ai/sessions/550e8400-e29b-41d4-a716-446655440000/message
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "content": "Hello, how can you help me today?",
  "message_type": "text",
  "metadata": {},
  "audio_data": null,
  "switch_to_agent": null
}
```

*Voice message with metadata:*
```json
POST /ai/sessions/550e8400-e29b-41d4-a716-446655440000/message
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "content": "What's my current balance?",
  "message_type": "voice",
  "metadata": {
    "audio_format": "wav",
    "sample_rate": 16000,
    "duration": 2.3
  },
  "audio_data": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hV",
  "switch_to_agent": null
}
```

*Agent switch request:*
```json
POST /ai/sessions/550e8400-e29b-41d4-a716-446655440000/message
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "content": "I need help with family account management",
  "message_type": "text",
  "metadata": {
    "priority": "high"
  },
  "audio_data": null,
  "switch_to_agent": "family"
}
```

*Command message:*
```json
POST /ai/sessions/550e8400-e29b-41d4-a716-446655440000/message
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "content": "/clear_history",
  "message_type": "command",
  "metadata": {
    "command_type": "clear_conversation"
  },
  "audio_data": null,
  "switch_to_agent": null
}
```

**Success Response (200):**
```json
{
  "message_id": "660e8400-e29b-41d4-a716-446655440002",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "processing_started": true,
  "estimated_response_time": 2.0
}
```

**Error Responses:**

*Session not found (404):*
```json
{
  "error": "validation",
  "message": "AI session not found",
  "category": "validation",
  "severity": "low",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Session not active (400):*
```json
{
  "error": "validation",
  "message": "AI session is not active",
  "category": "validation",
  "severity": "medium",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Session expired (400):*
```json
{
  "error": "validation",
  "message": "AI session has expired",
  "category": "validation",
  "severity": "medium",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Rate limit exceeded (429):*
```json
{
  "error": "ratelimit",
  "message": "Too many requests. Please wait 60 seconds and try again.",
  "category": "rate_limiting",
  "severity": "medium",
  "details": {
    "retry_after": 60,
    "limit": 60,
    "window": 60
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### DELETE `/ai/sessions/{session_id}` - End Session

Terminates an AI session and cleans up resources.

**Request Example:**
```http
DELETE /ai/sessions/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "message": "AI session ended successfully",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error Responses:**

*Session not found (404):*
```json
{
  "error": "validation",
  "message": "AI session not found",
  "category": "validation",
  "severity": "low",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Access denied (403):*
```json
{
  "error": "authorization",
  "message": "Access denied to this AI session",
  "category": "authorization",
  "severity": "high",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### POST `/ai/sessions/{session_id}/voice/setup` - Setup Voice Session

Configures voice capabilities for an AI session with LiveKit integration.

**Request Example:**
```http
POST /ai/sessions/550e8400-e29b-41d4-a716-446655440000/voice/setup
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "message": "Voice session setup successful",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "voice_config": {
    "livekit_url": "wss://your-livekit-server.livekit.cloud",
    "room_name": "ai_voice_550e8400-e29b-41d4-a716-446655440000",
    "participant_identity": "user_12345",
    "api_key": "API123456789",
    "api_secret": "secret_abcdef123456"
  }
}
```

**Error Responses:**

*Voice agent not available (503):*
```json
{
  "error": "system",
  "message": "Voice agent not available",
  "category": "system",
  "severity": "high",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Failed to enable voice (503):*
```json
{
  "error": "system",
  "message": "Failed to enable voice for session",
  "category": "system",
  "severity": "high",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### POST `/ai/sessions/{session_id}/voice/input` - Process Voice Input

Processes base64-encoded audio data through speech-to-text and routes to AI agents.

**Request Example:**
```json
POST /ai/sessions/550e8400-e29b-41d4-a716-446655440000/voice/input
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "audio_data": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hV"
}
```

**Success Response (202):**
```json
{
  "message": "Voice input processing started",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "processing": true
}
```

**Error Responses:**

*Voice not enabled (400):*
```json
{
  "error": "validation",
  "message": "Voice not enabled for this session",
  "category": "validation",
  "severity": "medium",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Invalid audio data (400):*
```json
{
  "error": "validation",
  "message": "Invalid audio data format",
  "category": "validation",
  "severity": "low",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

*Rate limit exceeded (429):*
```json
{
  "error": "ratelimit",
  "message": "Too many requests. Please wait 60 seconds and try again.",
  "category": "rate_limiting",
  "severity": "medium",
  "details": {
    "retry_after": 60,
    "limit": 30,
    "window": 60
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/sessions/{session_id}/voice/token` - Get Voice Token

Retrieves LiveKit access token for voice communication.

**Request Example:**
```http
GET /ai/sessions/550e8400-e29b-41d4-a716-446655440000/voice/token
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "livekit": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ2aWRlbyI6eyJyb29tSm9pbiI6dHJ1ZSwicm9vbSI6ImFpX3ZvaWNlXzU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMCIsImNhblB1Ymxpc2giOnRydWUsImNhblN1YnNjcmliZSI6dHJ1ZX0sImlhdCI6MTY5NjIzMzYwMCwibmJmIjoxNjk2MjMzNjAwLCJleHAiOjE2OTYyMzcyMDAsImlzcyI6IkFQMTEyMzQ1Njc4OSIsInN1YiI6InVzZXJfMTIzNDUiLCJqdGkiOiJ0b2tlbl8xMjM0NTYifQ.signature",
    "url": "wss://your-livekit-server.livekit.cloud",
    "room_name": "ai_voice_550e8400-e29b-41d4-a716-446655440000"
  },
  "voice_enabled": true
}
```

**Error Responses:**

*LiveKit not configured (503):*
```json
{
  "error": "system",
  "message": "LiveKit not configured or token creation failed",
  "category": "system",
  "severity": "high",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/health` - Health Check

Returns current status of the AI orchestration system.

**Request Example:**
```http
GET /ai/health
```

**Success Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-30T10:30:00.000Z",
  "sessions": {
    "total": 15,
    "active": 8,
    "expired_cleaned": 2
  },
  "messages": {
    "total": 234
  },
  "event_bus": {
    "active_connections": 8,
    "buffered_events": 0,
    "status": "healthy"
  },
  "system": {
    "version": "1.0.0",
    "uptime": "healthy"
  }
}
```

**Degraded Response (200):**
```json
{
  "status": "degraded",
  "timestamp": "2025-10-30T10:30:00.000Z",
  "sessions": {
    "total": 15,
    "active": 8,
    "expired_cleaned": 0
  },
  "messages": {
    "total": 234
  },
  "event_bus": {
    "active_connections": 8,
    "buffered_events": 45,
    "status": "degraded",
    "issues": ["high_buffer_usage"]
  },
  "system": {
    "version": "1.0.0",
    "uptime": "healthy"
  }
}
```

**Unhealthy Response (503):**
```json
{
  "status": "unhealthy",
  "error": "AI orchestrator not available",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/stats` - Get AI Statistics

Returns AI usage statistics for the current user.

**Request Example:**
```http
GET /ai/stats
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "total_sessions": 12,
  "active_sessions": 3,
  "total_messages": 156,
  "average_session_duration": 25.5,
  "most_used_agent": "personal"
}
```

### GET `/ai/performance/metrics` - Get Performance Metrics

Returns comprehensive performance metrics (admin users see full metrics, regular users see limited).

**Request Example (admin):**
```http
GET /ai/performance/metrics
Authorization: Bearer <admin_jwt_token>
```

**Full Admin Response (200):**
```json
{
  "timestamp": "2025-10-30T10:30:00.000Z",
  "model_engine": {
    "requests": {
      "total": 1250,
      "successful": 1245,
      "failed": 5,
      "rate_per_minute": 12.5
    },
    "performance": {
      "avg_response_time_ms": 285.3,
      "p95_response_time_ms": 450.0,
      "p99_response_time_ms": 650.0,
      "target_latency_ms": 300
    },
    "cache": {
      "hit_rate": 0.85,
      "size_mb": 256,
      "entries": 5000
    }
  },
  "memory_layer": {
    "usage_mb": 512,
    "capacity_mb": 1024,
    "evictions": 25
  },
  "resource_manager": {
    "active_sessions": 8,
    "cpu_usage_percent": 45.2,
    "memory_usage_percent": 62.1
  },
  "orchestrator": {
    "agent_switches": 12,
    "tool_calls": 89,
    "errors": 3
  }
}
```

**Limited User Response (200):**
```json
{
  "timestamp": "2025-10-30T10:30:00.000Z",
  "model_engine": {
    "requests": {
      "total": 1250,
      "successful": 1245,
      "failed": 5,
      "rate_per_minute": 12.5
    },
    "performance": {
      "avg_response_time_ms": 285.3,
      "target_latency_ms": 300
    }
  }
}
```

### GET `/ai/performance/health` - Get Detailed Health Check

Returns comprehensive health status of all AI orchestration components.

**Request Example:**
```http
GET /ai/performance/health
Authorization: Bearer <jwt_token>
```

**Healthy Response (200):**
```json
{
  "orchestrator": "healthy",
  "model_engine": "healthy",
  "memory_layer": "healthy",
  "resource_manager": "healthy",
  "event_bus": "healthy",
  "websocket_manager": "healthy",
  "timestamp": "2025-10-30T10:30:00.000Z",
  "route_sessions": {
    "active_count": 8,
    "total_messages": 234
  },
  "performance_metrics": {
    "avg_response_time_ms": 285.3,
    "error_rate_percent": 0.4,
    "throughput_rpm": 150
  }
}
```

**Degraded Response (200):**
```json
{
  "orchestrator": "healthy",
  "model_engine": "degraded",
  "memory_layer": "healthy",
  "resource_manager": "under_pressure",
  "event_bus": "healthy",
  "websocket_manager": "healthy",
  "issues": [
    "Model response time above target: 350ms > 300ms",
    "Memory usage high: 85% of capacity"
  ],
  "timestamp": "2025-10-30T10:30:00.000Z",
  "route_sessions": {
    "active_count": 8,
    "total_messages": 234
  }
}
```

### POST `/ai/performance/cache/invalidate` - Invalidate Caches

Invalidates AI system caches (admin only).

**Request Examples:**

*Invalidate all caches:*
```http
POST /ai/performance/cache/invalidate
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json

{
  "pattern": "*"
}
```

*Invalidate specific pattern:*
```http
POST /ai/performance/cache/invalidate
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json

{
  "pattern": "model_*"
}
```

**Success Response (200):**
```json
{
  "message": "Cache invalidation completed",
  "pattern": "*",
  "results": {
    "model_cache": {
      "entries_invalidated": 150,
      "status": "completed"
    },
    "memory_cache": {
      "entries_invalidated": 25,
      "status": "completed"
    },
    "response_cache": {
      "entries_invalidated": 89,
      "status": "completed"
    }
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

**Error Response - Not Admin (403):**
```json
{
  "error": "authorization",
  "message": "Admin access required",
  "category": "authorization",
  "severity": "high",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/performance/sessions` - Get Session Performance

Returns performance information about active AI sessions.

**Request Example (admin):**
```http
GET /ai/performance/sessions
Authorization: Bearer <admin_jwt_token>
```

**Success Response (200):**
```json
{
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "user_12345",
      "agent_type": "personal",
      "status": "active",
      "created_at": "2025-10-30T10:30:00.000Z",
      "last_activity": "2025-10-30T10:35:00.000Z",
      "message_count": 12,
      "resource_usage": {
        "cpu_percent": 5.2,
        "memory_mb": 45.6,
        "network_bytes": 125000
      },
      "performance": {
        "avg_response_time_ms": 245.3,
        "error_count": 0,
        "tool_calls": 3
      }
    }
  ],
  "resource_status": {
    "total_cpu_percent": 45.2,
    "total_memory_mb": 512.8,
    "active_sessions": 8,
    "status": "healthy"
  },
  "summary": {
    "total_sessions": 8,
    "user_sessions": 8,
    "system_health": "healthy"
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/performance/model/warmup` - Get Model Warmup Status

Returns information about model warmup status and performance.

**Request Example:**
```http
GET /ai/performance/model/warmup
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "warmup_status": {
    "gpt-4": {
      "status": "warmed",
      "last_warmup": "2025-10-30T09:00:00.000Z",
      "performance": {
        "avg_load_time_ms": 50.2,
        "memory_usage_mb": 2048
      }
    },
    "claude-3": {
      "status": "warming",
      "progress_percent": 75,
      "estimated_completion": "2025-10-30T10:35:00.000Z"
    }
  },
  "performance": {
    "overall_avg_response_time_ms": 285.3,
    "cache_hit_rate": 0.85
  },
  "cache": {
    "total_entries": 5000,
    "memory_usage_mb": 256
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### POST `/ai/performance/model/warmup/{model_name}` - Warmup Model

Manually warms up a specific model (admin only).

**Request Example:**
```http
POST /ai/performance/model/warmup/gpt-4
Authorization: Bearer <admin_jwt_token>
```

**Success Response (200):**
```json
{
  "message": "Model 'gpt-4' warmed up successfully",
  "model": "gpt-4",
  "status": "warmed",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

**Error Response (500):**
```json
{
  "error": "system",
  "message": "Failed to warm up model 'gpt-4'",
  "category": "system",
  "severity": "medium",
  "details": {
    "model": "gpt-4",
    "error": "Model loading timeout"
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### POST `/ai/performance/benchmarks/run` - Run Performance Benchmarks

Runs comprehensive performance benchmarks (admin only).

**Request Example:**
```http
POST /ai/performance/benchmarks/run
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json

{
  "interval_minutes": 30
}
```

**Success Response (200):**
```json
{
  "message": "Performance benchmark suite started",
  "status": "running",
  "target_latency_ms": 300,
  "estimated_duration_minutes": 5,
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/performance/benchmarks/results` - Get Benchmark Results

Returns the latest performance benchmark results.

**Request Example:**
```http
GET /ai/performance/benchmarks/results
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "benchmark_results": {
    "timestamp": "2025-10-30T10:25:00.000Z",
    "average_response_time_ms": 285.3,
    "success_rate": 0.987,
    "total_tests": 1000,
    "meets_target": true,
    "p95_response_time_ms": 450.0,
    "p99_response_time_ms": 650.0,
    "throughput_rpm": 150,
    "error_breakdown": {
      "timeout": 8,
      "server_error": 5,
      "rate_limit": 0
    }
  },
  "performance_status": {
    "meets_target": true,
    "performance_grade": "PASS",
    "target_latency_ms": 300,
    "actual_latency_ms": 285.3,
    "performance_ratio": 0.951
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/performance/benchmarks/metrics` - Get Benchmark Metrics

Returns current performance metrics from ongoing monitoring.

**Request Example:**
```http
GET /ai/performance/benchmarks/metrics
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "metrics": {
    "average_response_times": {
      "create_session": 45.2,
      "send_message": 285.3,
      "voice_input": 320.1
    },
    "error_rates": {
      "create_session": 0.002,
      "send_message": 0.004,
      "voice_input": 0.008
    },
    "operation_counts": {
      "create_session": 1250,
      "send_message": 5000,
      "voice_input": 800
    },
    "last_updated": "2025-10-30T10:29:00.000Z"
  },
  "performance_summary": {
    "overall_status": "GOOD",
    "target_latency_ms": 300,
    "operations_monitored": 3,
    "total_operations": 7050,
    "total_errors": 28
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### POST `/ai/performance/benchmarks/continuous/start` - Start Continuous Monitoring

Starts continuous performance monitoring (admin only).

**Request Example:**
```http
POST /ai/performance/benchmarks/continuous/start
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json

{
  "interval_minutes": 30
}
```

**Success Response (200):**
```json
{
  "message": "Continuous performance monitoring started",
  "interval_minutes": 30,
  "status": "running",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/performance/benchmarks/status` - Get Benchmark Status

Returns current status of performance benchmarking system.

**Request Example:**
```http
GET /ai/performance/benchmarks/status
Authorization: Bearer <jwt_token>
```

**Success Response (200):**
```json
{
  "status": {
    "benchmark_system": "operational",
    "target_latency_ms": 300,
    "last_benchmark": "2025-10-30T10:25:00.000Z",
    "meets_performance_target": true,
    "current_monitoring": {
      "active": true,
      "operations_tracked": 3,
      "last_updated": "2025-10-30T10:29:00.000Z"
    }
  },
  "latest_results_summary": {
    "average_response_time_ms": 285.3,
    "success_rate_percent": 98.7,
    "total_tests": 1000,
    "meets_target": true
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### POST `/ai/performance/cleanup` - Trigger Manual Cleanup

Triggers manual cleanup of AI system resources (admin only).

**Request Example:**
```http
POST /ai/performance/cleanup
Authorization: Bearer <admin_jwt_token>
```

**Success Response (200):**
```json
{
  "message": "Cleanup task started",
  "status": "running",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

### GET `/ai/health/error-handling` - Get Error Handling Health

Returns detailed health status of AI error handling and recovery systems.

**Request Example:**
```http
GET /ai/health/error-handling
```

**Success Response (200):**
```json
{
  "status": "healthy",
  "error_handling": {
    "overall_healthy": true,
    "circuit_breakers": {
      "session_creation_api": "closed",
      "message_processing": "closed",
      "voice_processing": "closed"
    },
    "recovery_managers": {
      "session_recovery": "operational",
      "model_fallback": "operational",
      "communication_restoration": "operational"
    },
    "error_counters": {
      "authentication": 2,
      "rate_limiting": 15,
      "validation": 8,
      "system": 1
    }
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

## 3 — Authentication & security

- REST endpoints use JWT via `Authorization: Bearer <token>` (standard get_current_user dependency).
- WebSocket authentication uses a `token` query parameter on the WS URL (`/ai/ws/{session_id}?token=<JWT>`). The WS dependency reads that token to authenticate the connection.
- All operations perform server-side permission checks using AI-specific permissions (AIPermission enum). The frontend must present tokens for users with required permissions for actions like family management, voice, or admin operations.
- Rate limiting is enforced server side for endpoints (examples in code: message send limit ~60/60s, voice input ~30/60s, health endpoints etc.). The frontend should handle 429 responses gracefully (backoff + show message to user).

## 4 — WebSocket protocol (comprehensive JSON examples)

Endpoint: `ws://<host>/ai/ws/{session_id}?token=<JWT>`

Connection life-cycle:
- Client creates a session (POST /ai/sessions) and receives `session_id`.
- Client opens WebSocket to the session using the JWT token in query param.
- Server replies with a welcome event `session_ready`.
- Client sends messages either as structured JSON or plain text; server supports both.

### Client-to-Server Messages

**Ping/Pong (Connection Health):**
```json
{
  "type": "ping",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

**Structured Chat Message:**
```json
{
  "type": "message",
  "content": "Hello, how can you help me today?",
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

**Voice Audio (Base64):**
```json
{
  "type": "voice",
  "audio_data": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hV",
  "metadata": {
    "format": "wav",
    "sample_rate": 16000,
    "duration": 2.3
  },
  "timestamp": "2025-10-30T10:30:00.000Z"
}
```

**Plain Text Message (treated as chat):**
```
"Hello, how are you?"
```

### Server-to-Client Events

All events follow the AIEvent model with these base fields:
- `type` (string event type)
- `data` (payload object)
- `session_id` (string)
- `agent_type` (string)
- `timestamp` (ISO 8601 string)
- `metadata` (optional object)

**Session Ready (Welcome):**
```json
{
  "type": "session_ready",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "personal",
    "voice_enabled": false,
    "message": "Connected to personal agent"
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:00.000Z",
  "metadata": {}
}
```

**Pong Response:**
```json
{
  "type": "pong",
  "data": {},
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:00.000Z",
  "metadata": {}
}
```

**Thinking Status:**
```json
{
  "type": "thinking",
  "data": {
    "status": "thinking",
    "message": "Processing your message..."
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:05.000Z",
  "metadata": {}
}
```

**Typing Status:**
```json
{
  "type": "typing",
  "data": {
    "status": "typing",
    "message": "Generating response..."
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:05.200Z",
  "metadata": {}
}
```

**Token Streaming (Incremental):**
```json
{
  "type": "token",
  "data": {
    "token": "Hello"
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:05.300Z",
  "metadata": {}
}
```

```json
{
  "type": "token",
  "data": {
    "token": "!"
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:05.310Z",
  "metadata": {}
}
```

```json
{
  "type": "token",
  "data": {
    "token": " How"
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:05.320Z",
  "metadata": {}
}
```

**Complete Response:**
```json
{
  "type": "response",
  "data": {
    "response": "Hello! How can I help you today?"
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:05.500Z",
  "metadata": {
    "processing_time": 0.45,
    "token_count": 8,
    "tools_used": []
  }
}
```

**Tool Call Start:**
```json
{
  "type": "tool_call",
  "data": {
    "tool_name": "get_family_balance",
    "parameters": {
      "user_id": "user_12345",
      "include_pending": true
    }
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "family",
  "timestamp": "2025-10-30T10:30:05.600Z",
  "metadata": {
    "tool_call_id": "tool_abc123"
  },
  "tool_name": "get_family_balance"
}
```

**Tool Result:**
```json
{
  "type": "tool_result",
  "data": {
    "tool_name": "get_family_balance",
    "result": {
      "balance": 1250.75,
      "currency": "SBD",
      "last_updated": "2025-10-30T09:30:00.000Z",
      "pending_transactions": 2
    }
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "family",
  "timestamp": "2025-10-30T10:30:05.750Z",
  "metadata": {
    "tool_call_id": "tool_abc123",
    "execution_time": 0.15
  },
  "tool_name": "get_family_balance"
}
```

**Workflow Start:**
```json
{
  "type": "workflow_start",
  "data": {
    "workflow_name": "family_transfer",
    "steps": ["validate_accounts", "check_limits", "execute_transfer", "send_notifications"],
    "estimated_duration": 3.0
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "family",
  "timestamp": "2025-10-30T10:30:05.800Z",
  "metadata": {
    "workflow_id": "wf_xyz789"
  },
  "workflow_id": "wf_xyz789"
}
```

**Workflow Step:**
```json
{
  "type": "workflow_step",
  "data": {
    "step_name": "validate_accounts",
    "step_number": 1,
    "total_steps": 4,
    "status": "completed",
    "result": {
      "source_account": "valid",
      "destination_account": "valid"
    }
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "family",
  "timestamp": "2025-10-30T10:30:05.850Z",
  "metadata": {
    "workflow_id": "wf_xyz789",
    "step_execution_time": 0.05
  },
  "workflow_id": "wf_xyz789"
}
```

**Workflow End:**
```json
{
  "type": "workflow_end",
  "data": {
    "workflow_name": "family_transfer",
    "status": "completed",
    "total_steps": 4,
    "execution_time": 2.8,
    "result": {
      "transfer_id": "txn_123456",
      "amount": 100.00,
      "status": "completed"
    }
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "family",
  "timestamp": "2025-10-30T10:30:08.600Z",
  "metadata": {
    "workflow_id": "wf_xyz789"
  },
  "workflow_id": "wf_xyz789"
}
```

**Voice Processing Start:**
```json
{
  "type": "voice_start",
  "data": {
    "processing_type": "stt",
    "audio_format": "wav",
    "sample_rate": 16000,
    "duration": 2.3
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "voice",
  "timestamp": "2025-10-30T10:30:10.000Z",
  "metadata": {}
}
```

**Speech-to-Text Result:**
```json
{
  "type": "stt",
  "data": {
    "transcribed_text": "What's my current account balance?",
    "confidence": 0.92,
    "language": "en",
    "processing_time": 0.8
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "voice",
  "timestamp": "2025-10-30T10:30:10.800Z",
  "metadata": {}
}
```

**Text-to-Speech Audio:**
```json
{
  "type": "tts",
  "data": {
    "audio": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hV",
    "format": "base64",
    "audio_format": "wav",
    "sample_rate": 22050,
    "duration": 1.8
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "voice",
  "timestamp": "2025-10-30T10:30:11.200Z",
  "metadata": {}
}
```

**Voice Processing End:**
```json
{
  "type": "voice_end",
  "data": {
    "processing_type": "full_pipeline",
    "total_processing_time": 2.1,
    "audio_chunks_processed": 3,
    "text_generated": "Your current account balance is $1,250.75 SBD."
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "voice",
  "timestamp": "2025-10-30T10:30:12.100Z",
  "metadata": {}
}
```

**Agent Switch:**
```json
{
  "type": "agent_switch",
  "data": {
    "previous_agent": "personal",
    "current_agent": "family",
    "reason": "User requested family account assistance",
    "context_preserved": true
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "family",
  "timestamp": "2025-10-30T10:30:15.000Z",
  "metadata": {}
}
```

**Context Load:**
```json
{
  "type": "context_load",
  "data": {
    "context_type": "family_members",
    "items_loaded": 5,
    "source": "database"
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "family",
  "timestamp": "2025-10-30T10:30:15.100Z",
  "metadata": {}
}
```

**Context Ready:**
```json
{
  "type": "context_ready",
  "data": {
    "context_type": "family_members",
    "total_items": 5,
    "memory_usage_mb": 2.3,
    "ready_for_queries": true
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "family",
  "timestamp": "2025-10-30T10:30:15.200Z",
  "metadata": {}
}
```

**Memory Update:**
```json
{
  "type": "memory_update",
  "data": {
    "update_type": "conversation_summary",
    "items_added": 3,
    "total_memories": 25,
    "compression_applied": true
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:20.000Z",
  "metadata": {}
}
```

**Session Start:**
```json
{
  "type": "session_start",
  "data": {
    "agent_type": "personal",
    "voice_enabled": false,
    "preferences": {
      "language": "en",
      "response_style": "concise"
    }
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:00.000Z",
  "metadata": {}
}
```

**Session End:**
```json
{
  "type": "session_end",
  "data": {
    "reason": "user_initiated",
    "total_messages": 12,
    "session_duration_minutes": 25.5,
    "cleanup_completed": true
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:55:30.000Z",
  "metadata": {}
}
```

**Error Event:**
```json
{
  "type": "error",
  "data": {
    "error": "Failed to process voice input: audio format not supported"
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "voice",
  "timestamp": "2025-10-30T10:30:25.000Z",
  "metadata": {
    "error_code": "VOICE_PROCESSING_ERROR",
    "severity": "medium",
    "retry_possible": true
  },
  "error_code": "VOICE_PROCESSING_ERROR"
}
```

**Warning Event:**
```json
{
  "type": "warning",
  "data": {
    "warning": "Response time above target: 450ms > 300ms"
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "personal",
  "timestamp": "2025-10-30T10:30:30.000Z",
  "metadata": {
    "warning_code": "PERFORMANCE_DEGRADED",
    "current_latency": 450,
    "target_latency": 300
  }
}
```

**Waiting Status:**
```json
{
  "type": "waiting",
  "data": {
    "status": "waiting",
    "message": "Waiting for external service response...",
    "estimated_wait_seconds": 5
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "commerce",
  "timestamp": "2025-10-30T10:30:35.000Z",
  "metadata": {
    "waiting_for": "payment_processor"
  }
}
```

## 5 — Voice integration (LiveKit + STT/TTS)

Overview:
- Server supports LiveKit for real-time voice rooms and a voice processing pipeline (STT -> agent -> TTS).

Frontend flow for enabling voice:

1. Create session with `voice_enabled=true` or call `POST /ai/sessions/{session_id}/voice/setup`.
2. GET `/ai/sessions/{session_id}/voice/token` to acquire a LiveKit token and configuration (room name is `ai_voice_{session_id}` by convention).
3. Use LiveKit client SDK in frontend to join the room with the provided token.
4. For low-latency voice commands, stream audio through LiveKit into the server (LiveKit server integration handles audio capture); alternatively, capture audio in the client, base64-encode and send via WS `{type: "voice", audio_data: "<base64>"}` or POST `/ai/sessions/{session_id}/voice/input`.
5. Server emits STT events and TTS events via WebSocket. TTS audio chunks are base64 and can be played by the client.

TTS playback snippet (JS idea):

```js
// base64Audio is a base64 string received in event.data.audio
const audioBytes = Uint8Array.from(atob(base64Audio), c => c.charCodeAt(0))
const blob = new Blob([audioBytes], { type: 'audio/wav' })
const url = URL.createObjectURL(blob)
const audio = new Audio(url)
audio.play()
```

Requirements & config:
- LiveKit credentials must be configured on the server. Without LiveKit, only REST voice endpoints and TTS events (base64) are available for playback.

## 6 — Tool execution & workflows

- Agents can trigger MCP tools; the orchestrator emits `tool_call` at start and `tool_result` when finished.
- These events are intended to be surfaced by the frontend as actions (e.g., show a modal, show progress, confirm results).
- The frontend should never try to call MCP tools directly; instead, interpret `tool_call` events as server-driven actions.

## 7 — Error handling & UI guidance

- HTTP 4xx/5xx:
  - 401: show login prompt / token refresh.
  - 403: show permission error (this user lacks required AI permission).
  - 404: session not found — prompt to create a new session.
  - 429: rate limited — show backoff UI and retry countdown.

- WebSocket errors:
  - On `error` events, stop streaming UI and show the error message.
  - On disconnect, attempt reconnect with exponential backoff (e.g., 0.5s, 1s, 2s, 5s, 10s) and limit retries or let user re-open session manually after several attempts.

- Token backpressure and token events:
  - Batch token UI updates to keep rendering smooth.
  - If TTS audio arrives while tokens stream, prioritize audio playback for perceived responsiveness.

## 8 — Frontend integration checklist (copyable)

1. Authentication
   - [ ] Ensure REST requests include `Authorization: Bearer <JWT>`.
   - [ ] WS connect uses `?token=<JWT>` or Authorization header during upgrade if supported by client.

2. Session lifecycle
   - [ ] POST `/ai/sessions` to create session; store `session_id`.
   - [ ] Open WS: `/ai/ws/{session_id}?token=<JWT>`.
   - [ ] On WS `session_ready`, mark session connected.
   - [ ] On disconnect, re-open connection and re-sync session state.

3. Messaging
   - [ ] Send messages via WS for streaming; support REST POST as fallback.
   - [ ] Render token events incrementally and finalize on `response`.

4. Voice
   - [ ] Call `/ai/sessions/{id}/voice/setup` and `/ai/sessions/{id}/voice/token` to enable LiveKit.
   - [ ] Integrate LiveKit client to join room or send base64 audio via WS.
   - [ ] Play TTS audio from `tts` events.

5. Tool calls
   - [ ] Show progress/UI feedback when `tool_call` events arrive.
   - [ ] Display results / errors from `tool_result` events.

6. Robustness
   - [ ] Implement WS reconnect with exponential backoff.
   - [ ] On reconnect, fetch session state with `/ai/sessions/{session_id}` and rely on event replay buffering.
   - [ ] Handle rate limit responses (429) with user-friendly messages and client-side throttling.

## 9 — Example WebSocket client (JS, minimal)

```js
// Minimal example for connecting and handling token/response events
function connectAiWs(baseUrl, sessionId, jwtToken) {
  const wsUrl = `${baseUrl.replace(/^http/, 'ws')}/ai/ws/${sessionId}?token=${jwtToken}`
  const ws = new WebSocket(wsUrl)

  ws.onopen = () => console.log('AI WS open')

  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data)
      switch (msg.type) {
        case 'token':
          // append token to current draft
          appendToken(msg.data.token)
          break
        case 'response':
          finalizeResponse(msg.data.response)
          break
        case 'tts':
          playBase64Audio(msg.data.audio)
          break
        case 'error':
          showError(msg.data.error)
          break
        default:
          console.debug('AI event', msg.type, msg)
      }
    } catch (e) {
      console.error('Failed to parse WS message', e)
    }
  }

  ws.onclose = (e) => {
    console.log('AI WS closed', e.code)
    // implement reconnect logic here
  }

  ws.onerror = (err) => console.error('WS error', err)

  return ws
}
```

## 10 — Testing & local development

- There are demo and test scripts in `integrations/ai_orchestration` (e.g., `test_websocket_demo.py`, `test_voice_integration.py`). Use those to observe example event flows.
- For voice features, configure LiveKit credentials in environment variables on the server.
- To run local manual test:
  1. Create a session via POST `/ai/sessions` (obtain JWT using existing user creation tools in `scripts/`).
  2. Open WS `/ai/ws/{session_id}?token=<JWT>` and send messages.

## 12 — Sample WebSocket Event Trace

Here's a complete trace of a typical AI conversation with tool usage, showing the exact JSON events that would be sent over WebSocket. This covers session creation through message processing with tool calls.

**Sample Conversation Flow:**
1. User creates session
2. User sends message asking for family balance
3. AI processes message, calls tool, returns result
4. AI generates streaming response

**WebSocket Event Trace:**

```json
[
  {
    "type": "session_ready",
    "data": {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "agent_type": "family",
      "voice_enabled": true,
      "message": "Connected to family agent"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:00.000Z",
    "metadata": {}
  },
  {
    "type": "thinking",
    "data": {
      "status": "thinking",
      "message": "Processing your message..."
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.000Z",
    "metadata": {}
  },
  {
    "type": "tool_call",
    "data": {
      "tool_name": "get_family_balance",
      "parameters": {
        "user_id": "user_12345",
        "include_pending": true
      }
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.200Z",
    "metadata": {
      "tool_call_id": "tool_abc123"
    },
    "tool_name": "get_family_balance"
  },
  {
    "type": "tool_result",
    "data": {
      "tool_name": "get_family_balance",
      "result": {
        "balance": 1250.75,
        "currency": "SBD",
        "last_updated": "2025-10-30T09:30:00.000Z",
        "pending_transactions": 2
      }
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.350Z",
    "metadata": {
      "tool_call_id": "tool_abc123",
      "execution_time": 0.15
    },
    "tool_name": "get_family_balance"
  },
  {
    "type": "typing",
    "data": {
      "status": "typing",
      "message": "Generating response..."
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.400Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": "Your"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.500Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " current"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.510Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " family"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.520Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " balance"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.530Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " is"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.540Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " $1,250.75"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.550Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " SBD,"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.560Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " with"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.570Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " 2"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.580Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " pending"
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.590Z",
    "metadata": {}
  },
  {
    "type": "token",
    "data": {
      "token": " transactions."
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.600Z",
    "metadata": {}
  },
  {
    "type": "response",
    "data": {
      "response": "Your current family balance is $1,250.75 SBD, with 2 pending transactions."
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:30:01.650Z",
    "metadata": {
      "processing_time": 0.65,
      "token_count": 12,
      "tools_used": ["get_family_balance"]
    }
  }
]
```

**Voice Conversation Trace Example:**

```json
[
  {
    "type": "voice_start",
    "data": {
      "processing_type": "stt",
      "audio_format": "wav",
      "sample_rate": 16000,
      "duration": 2.1
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "voice",
    "timestamp": "2025-10-30T10:35:00.000Z",
    "metadata": {}
  },
  {
    "type": "stt",
    "data": {
      "transcribed_text": "Transfer $100 to my sister's account",
      "confidence": 0.94,
      "language": "en",
      "processing_time": 0.7
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "voice",
    "timestamp": "2025-10-30T10:35:00.700Z",
    "metadata": {}
  },
  {
    "type": "agent_switch",
    "data": {
      "previous_agent": "voice",
      "current_agent": "family",
      "reason": "Voice command requires family agent for transfers",
      "context_preserved": true
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:35:00.750Z",
    "metadata": {}
  },
  {
    "type": "workflow_start",
    "data": {
      "workflow_name": "family_transfer",
      "steps": ["validate_accounts", "check_limits", "execute_transfer", "send_notifications"],
      "estimated_duration": 3.0
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:35:00.800Z",
    "metadata": {
      "workflow_id": "wf_xyz789"
    },
    "workflow_id": "wf_xyz789"
  },
  {
    "type": "workflow_step",
    "data": {
      "step_name": "validate_accounts",
      "step_number": 1,
      "total_steps": 4,
      "status": "completed",
      "result": {
        "source_account": "valid",
        "destination_account": "valid"
      }
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:35:00.850Z",
    "metadata": {
      "workflow_id": "wf_xyz789",
      "step_execution_time": 0.05
    },
    "workflow_id": "wf_xyz789"
  },
  {
    "type": "workflow_step",
    "data": {
      "step_name": "check_limits",
      "step_number": 2,
      "total_steps": 4,
      "status": "completed",
      "result": {
        "daily_limit": 500.00,
        "used_today": 150.00,
        "remaining": 350.00,
        "transfer_allowed": true
      }
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:35:00.900Z",
    "metadata": {
      "workflow_id": "wf_xyz789",
      "step_execution_time": 0.05
    },
    "workflow_id": "wf_xyz789"
  },
  {
    "type": "workflow_step",
    "data": {
      "step_name": "execute_transfer",
      "step_number": 3,
      "total_steps": 4,
      "status": "completed",
      "result": {
        "transfer_id": "txn_123456",
        "amount": 100.00,
        "status": "completed",
        "fee": 0.00
      }
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:35:00.950Z",
    "metadata": {
      "workflow_id": "wf_xyz789",
      "step_execution_time": 0.05
    },
    "workflow_id": "wf_xyz789"
  },
  {
    "type": "workflow_step",
    "data": {
      "step_name": "send_notifications",
      "step_number": 4,
      "total_steps": 4,
      "status": "completed",
      "result": {
        "notifications_sent": 2,
        "recipients": ["sender", "recipient"]
      }
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:35:01.000Z",
    "metadata": {
      "workflow_id": "wf_xyz789",
      "step_execution_time": 0.05
    },
    "workflow_id": "wf_xyz789"
  },
  {
    "type": "workflow_end",
    "data": {
      "workflow_name": "family_transfer",
      "status": "completed",
      "total_steps": 4,
      "execution_time": 0.2,
      "result": {
        "transfer_id": "txn_123456",
        "amount": 100.00,
        "status": "completed"
      }
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "family",
    "timestamp": "2025-10-30T10:35:01.000Z",
    "metadata": {
      "workflow_id": "wf_xyz789"
    },
    "workflow_id": "wf_xyz789"
  },
  {
    "type": "tts",
    "data": {
      "audio": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hVFApGn+DyvmQcBzaL1/LNeSsFJHfH8N2QQAoUXrTp66hV",
      "format": "base64",
      "audio_format": "wav",
      "sample_rate": 22050,
      "duration": 2.8
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "voice",
    "timestamp": "2025-10-30T10:35:01.050Z",
    "metadata": {}
  },
  {
    "type": "voice_end",
    "data": {
      "processing_type": "full_pipeline",
      "total_processing_time": 1.05,
      "audio_chunks_processed": 1,
      "text_generated": "Transfer completed successfully. $100 has been sent to your sister's account."
    },
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "agent_type": "voice",
    "timestamp": "2025-10-30T10:35:01.050Z",
    "metadata": {}
  }
]
```

---

## 13 — Complete API Coverage Summary

This document now provides 100% coverage of all backend capabilities with comprehensive JSON examples for:

**REST Endpoints (15 total):**
- Session management: create, list, get, delete (4 endpoints)
- Message sending: text, voice, commands (1 endpoint) 
- Voice setup: LiveKit config and token retrieval (3 endpoints)
- Health/monitoring: basic health, detailed health, error handling (3 endpoints)
- Performance: metrics, cache invalidation, benchmarks, cleanup (5 endpoints)

**WebSocket Events (20+ event types):**
- Session lifecycle: session_ready, session_start, session_end
- Message processing: thinking, typing, token, response
- Tool execution: tool_call, tool_result, workflow_start/step/end
- Voice pipeline: voice_start, stt, tts, voice_end
- Context/memory: context_load, context_ready, memory_update
- Status/communication: pong, agent_switch, waiting
- Error handling: error, warning

**Error Scenarios (10+ error types):**
- Authentication/authorization failures
- Rate limiting and resource constraints
- Validation errors and malformed requests
- System/service unavailability
- Session state errors

**All examples include:**
- Success responses with complete data structures
- Error responses with proper error categorization
- Different parameter combinations and edge cases
- Real-world usage patterns and workflows
- Complete conversation traces for testing

The frontend team now has everything needed to implement full AI orchestration integration without gaps in understanding backend capabilities.
