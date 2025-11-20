"""
Family Calendar and Tasks API endpoints.

This module extends the family routes with calendar event and task management functionality.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import Query
from pydantic import BaseModel, Field


# ============================================================================
# CALENDAR MODELS
# ============================================================================

class CalendarEventCreate(BaseModel):
    """Request model for creating a calendar event."""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    start_time: datetime
    end_time: datetime
    event_type: str = Field("family", pattern="^(family|personal|task)$")
    location: Optional[str] = Field(None, max_length=200)
    reminder_minutes: Optional[int] = Field(30, ge=0, le=10080)  # Max 1 week
    family_id: str


class CalendarEventUpdate(BaseModel):
    """Request model for updating a calendar event."""
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    event_type: Optional[str] = Field(None, pattern="^(family|personal|task)$")
    location: Optional[str] = Field(None, max_length=200)
    reminder_minutes: Optional[int] = Field(None, ge=0, le=10080)


class CalendarEventResponse(BaseModel):
    """Response model for calendar events."""
    event_id: str
    family_id: str
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    event_type: str
    location: Optional[str]
    reminder_minutes: Optional[int]
    created_by: str
    created_by_name: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


# ============================================================================
# TASK MODELS
# ============================================================================

class TaskCreate(BaseModel):
    """Request model for creating a task."""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    assigned_to: Optional[str] = None  # user_id
    due_date: Optional[datetime] = None
    priority: str = Field("medium", pattern="^(low|medium|high)$")
    family_id: str


class TaskUpdate(BaseModel):
    """Request model for updating a task."""
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    status: Optional[str] = Field(None, pattern="^(pending|in_progress|completed)$")


class TaskResponse(BaseModel):
    """Response model for tasks."""
    task_id: str
    family_id: str
    title: str
    description: Optional[str]
    assigned_to: Optional[str]
    assigned_to_name: Optional[str]
    due_date: Optional[datetime]
    priority: str
    status: str  # pending, in_progress, completed
    created_by: str
    created_by_name: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    completed_by: Optional[str]
    completed_by_name: Optional[str]
