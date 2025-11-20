"""
Dashboard preferences models.

Pydantic models for dashboard widget configuration and user preferences.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WidgetPosition(BaseModel):
    """Widget position in grid layout."""

    x: int = Field(..., ge=0, description="X position in grid")
    y: int = Field(..., ge=0, description="Y position in grid")
    w: int = Field(..., ge=1, le=12, description="Width in grid units (1-12)")
    h: int = Field(..., ge=1, description="Height in grid units")


class WidgetConfig(BaseModel):
    """Widget configuration."""

    widget_id: str = Field(..., description="Unique widget instance ID")
    widget_type: str = Field(..., description="Widget type identifier")
    position: WidgetPosition = Field(..., description="Widget position in grid")
    visible: bool = Field(default=True, description="Widget visibility")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Widget-specific settings")


class DashboardLayout(BaseModel):
    """Dashboard layout configuration."""

    context: str = Field(..., pattern="^(personal|family|team)$", description="Dashboard context")
    context_id: Optional[str] = Field(None, description="Family ID or Workspace ID for context")
    widgets: List[WidgetConfig] = Field(default_factory=list, description="List of widgets")
    grid_columns: int = Field(default=12, ge=1, le=24, description="Number of grid columns")


class DashboardPreferences(BaseModel):
    """User dashboard preferences."""

    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    layouts: Dict[str, DashboardLayout] = Field(
        default_factory=dict, description="Layouts by context key (e.g., 'personal', 'family:123')"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Request/Response Models


class CreateWidgetRequest(BaseModel):
    """Request to add a widget to dashboard."""

    context: str = Field(..., pattern="^(personal|family|team)$")
    context_id: Optional[str] = None
    widget_type: str = Field(..., description="Widget type to add")
    position: Optional[WidgetPosition] = Field(None, description="Initial position (auto if not provided)")
    settings: Dict[str, Any] = Field(default_factory=dict)


class UpdateWidgetRequest(BaseModel):
    """Request to update widget configuration."""

    position: Optional[WidgetPosition] = None
    visible: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


class UpdateLayoutRequest(BaseModel):
    """Request to update entire dashboard layout."""

    widgets: List[WidgetConfig] = Field(..., description="Complete widget list")
    grid_columns: Optional[int] = Field(None, ge=1, le=24)


class DashboardPreferencesResponse(BaseModel):
    """Response with dashboard preferences."""

    context: str
    context_id: Optional[str]
    widgets: List[WidgetConfig]
    grid_columns: int


class WidgetResponse(BaseModel):
    """Response for single widget operation."""

    widget_id: str
    widget_type: str
    position: WidgetPosition
    visible: bool
    settings: Dict[str, Any]
