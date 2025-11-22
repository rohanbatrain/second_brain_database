"""
Pydantic models for MemEx (Memory Extension) system.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

class Deck(BaseModel):
    """Model for a flashcard deck."""
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Physics Definitions",
                "created_at": "2023-01-01T00:00:00Z"
            }
        }

class Card(BaseModel):
    """Model for a flashcard."""
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    deck_id: str
    front_content: str
    back_content: str
    
    # Spaced Repetition Metadata
    next_review_date: datetime = Field(default_factory=datetime.utcnow)
    interval: int = Field(default=0, description="Interval in days")
    ease_factor: float = Field(default=2.5, description="Ease factor multiplier")
    repetition_count: int = Field(default=0, description="Number of successful recalls")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "deck_id": "123e4567-e89b-12d3-a456-426614174000",
                "front_content": "What is the speed of light?",
                "back_content": "299,792,458 m/s",
                "next_review_date": "2023-01-01T00:00:00Z",
                "interval": 0,
                "ease_factor": 2.5,
                "repetition_count": 0
            }
        }

class ReviewRequest(BaseModel):
    """Request model for reviewing a card."""
    rating: int = Field(..., ge=0, le=5, description="Rating: 0=Forgot, 3=Hard, 4=Good, 5=Easy")
