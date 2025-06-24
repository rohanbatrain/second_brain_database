"""
Admin models for password reset abuse event review and admin API schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AbuseEvent(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: str
    ip: str
    event_type: str
    timestamp: datetime
    resolved: bool = False
    resolution_notes: Optional[str] = None
    details: Optional[dict] = None
