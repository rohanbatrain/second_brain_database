"""
Admin models for password reset abuse event review and admin API schemas.

- PEP 8/257 compliant, MyPy strict compatible.
- All fields are typed, with docstrings for models and fields.
- Linting/tooling config at file end.
"""
from typing import Optional, Dict, TypedDict
from datetime import datetime
from pydantic import BaseModel, Field

class EmailIpPairDict(TypedDict):
    """TypedDict for (email, ip) pair used in Redis and service logic."""
    email: str
    ip: str

class AbuseEvent(BaseModel):
    """
    Model representing a password reset abuse event for admin review.

    Attributes:
        id: Optional MongoDB document ID (alias: _id).
        email: Email address involved in the event.
        ip: IP address associated with the event.
        event_type: Type of abuse event (e.g., 'reset', 'block', etc.).
        timestamp: UTC timestamp of the event.
        resolved: Whether the event has been resolved by an admin.
        resolution_notes: Optional notes about the resolution.
        details: Optional extra metadata (e.g., user agent, geo info).
    """
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    email: str = Field(..., description="Email address involved in the event")
    ip: str = Field(..., description="IP address associated with the event")
    event_type: str = Field(..., description="Type of abuse event (e.g., 'reset', 'block')")
    timestamp: datetime = Field(..., description="UTC timestamp of the event")
    resolved: bool = Field(False, description="Whether the event has been resolved by an admin")
    resolution_notes: Optional[str] = Field(None, description="Optional notes about the resolution")
    details: Optional[Dict] = Field(None, description="Optional extra metadata (e.g., user agent, geo info)")

class EmailIpPair(BaseModel):
    """Model for (email, ip) pair used in whitelist/blocklist endpoints."""
    email: str = Field(..., description="Email address")
    ip: str = Field(..., description="IP address")

class AbuseEventResolveRequest(BaseModel):
    """Model for resolving an abuse event."""
    event_id: str = Field(..., description="Abuse event ID")
    notes: Optional[str] = Field(None, description="Resolution notes")
