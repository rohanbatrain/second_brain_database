"""
Pydantic models for the Skill Log feature.

This module provides comprehensive data models for personal skill tracking,
including hierarchical relationships, progress logging, and analytics.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field


# --- Core Skill Models ---

class SkillMetadata(BaseModel):
    """Extensible metadata for skills."""

    category: Optional[str] = Field(None, description="Skill category (e.g., 'programming', 'design')")
    difficulty: Optional[Literal["beginner", "intermediate", "advanced", "expert"]] = Field(
        None, description="Self-assessed difficulty level"
    )
    priority: Optional[Literal["low", "medium", "high", "critical"]] = Field(
        None, description="Importance priority"
    )
    custom_fields: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="User-defined custom metadata"
    )


# --- Skill Log Models ---

class SkillEvidence(BaseModel):
    """Evidence attached to skill log entries."""

    type: Literal["note", "link", "reflection", "achievement"] = Field(
        ..., description="Type of evidence"
    )
    content: str = Field(..., min_length=1, max_length=5000, description="Evidence content")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional evidence metadata (e.g., URL for links)"
    )


class SkillLogContext(BaseModel):
    """Contextual information for skill log entries."""

    quarter: Optional[str] = Field(None, description="Time period (e.g., 'Q1 2025')")
    year: Optional[int] = Field(None, description="Year of the activity")
    duration_hours: Optional[float] = Field(None, gt=0, description="Time spent in hours")
    confidence_level: Optional[int] = Field(
        None, ge=1, le=10, description="Self-assessed confidence level (1-10)"
    )


class SkillLogDocument(BaseModel):
    """Embedded log entry within skill document."""

    log_id: str = Field(..., description="Unique log entry identifier")
    project_id: Optional[str] = Field(None, description="Optional project linkage")
    progress_state: Literal["learning", "practicing", "used", "mastered"] = Field(
        ..., description="Current progress state"
    )
    numeric_level: Optional[int] = Field(
        None, ge=1, le=5, description="Optional numeric proficiency level (1-5)"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When this activity occurred")
    # SIMPLIFIED: Single notes field instead of complex evidence
    notes: Optional[str] = Field(None, max_length=2000, description="Personal notes and reflections")
    context: SkillLogContext = Field(
        default_factory=SkillLogContext, description="Situational context"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SkillDocument(BaseModel):
    """Database document model for the user_skills collection."""

    skill_id: str = Field(..., description="Unique skill identifier (user-scoped)")
    user_id: str = Field(..., description="Owner of the skill")
    name: str = Field(..., min_length=1, max_length=200, description="Skill name")
    description: Optional[str] = Field(None, max_length=1000, description="Optional skill description")
    parent_skill_ids: List[str] = Field(
        default_factory=list, description="IDs of parent skills (multiple inheritance supported)"
    )
    # child_skill_ids removed - computed on-demand via queries to avoid consistency issues
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    metadata: SkillMetadata = Field(default_factory=SkillMetadata, description="Extensible skill metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(True, description="Soft delete flag")
    # EMBEDDED LOGS - No separate collection
    logs: List[SkillLogDocument] = Field(
        default_factory=list, description="Embedded skill log entries"
    )


# --- Analytics Models ---

class SkillRollupStats(BaseModel):
    """Roll-up statistics for parent skills aggregating child data."""

    child_count: int = Field(0, description="Total number of child skills")
    active_children: int = Field(0, description="Number of active child skills")
    total_child_logs: int = Field(0, description="Total log entries across all children")
    average_child_level: Optional[float] = Field(None, description="Average numeric level of children")
    last_child_activity: Optional[datetime] = Field(None, description="Most recent activity in child tree")


class SkillAnalyticsStats(BaseModel):
    """Computed analytics for a skill."""

    total_logs: int = Field(0, description="Total number of log entries")
    current_state: Optional[str] = Field(None, description="Most recent progress state")
    last_activity: Optional[datetime] = Field(None, description="Most recent log timestamp")
    project_count: int = Field(0, description="Number of unique projects linked")
    total_hours: float = Field(0.0, description="Total hours logged")
    average_confidence: Optional[float] = Field(None, description="Average confidence level")
    parent_rollup: SkillRollupStats = Field(
        default_factory=SkillRollupStats, description="Aggregated child skill statistics"
    )


class SkillAnalyticsDocument(BaseModel):
    """Database document model for the skill_analytics_cache collection."""

    user_id: str = Field(..., description="Owner of the analytics")
    skill_id: str = Field(..., description="Skill being analyzed")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    stats: SkillAnalyticsStats = Field(..., description="Computed analytics data")


# --- API Request/Response Models ---

class CreateSkillRequest(BaseModel):
    """Request model for creating a new skill."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    parent_skill_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Optional[SkillMetadata] = None


class UpdateSkillRequest(BaseModel):
    """Request model for updating an existing skill."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    metadata: Optional[SkillMetadata] = None


class SkillResponse(BaseModel):
    """Response model for skill data."""

    skill_id: str
    name: str
    description: Optional[str]
    parent_skill_ids: List[str]
    child_skill_ids: List[str] = Field(default_factory=list, description="Computed children - not stored")
    tags: List[str]
    metadata: SkillMetadata
    created_at: str
    updated_at: str
    analytics: Optional[SkillAnalyticsStats] = None


class SkillTreeNode(BaseModel):
    """Node in the skill hierarchy tree."""

    skill: SkillResponse
    children: List['SkillTreeNode'] = Field(default_factory=list)


class CreateSkillLogRequest(BaseModel):
    """Request model for creating a skill log entry."""

    project_id: Optional[str] = None
    progress_state: Literal["learning", "practicing", "used", "mastered"]
    numeric_level: Optional[int] = Field(None, ge=1, le=5)
    timestamp: Optional[datetime] = None
    # SIMPLIFIED: Single notes field instead of complex evidence
    notes: Optional[str] = Field(None, max_length=2000)
    context: Optional[SkillLogContext] = None


class SkillLogResponse(BaseModel):
    """Response model for skill log entries."""

    log_id: str
    skill_id: str
    project_id: Optional[str]
    progress_state: str
    numeric_level: Optional[int]
    timestamp: str
    # SIMPLIFIED: Single notes field instead of complex evidence
    notes: Optional[str]
    context: SkillLogContext
    created_at: str


class SkillAnalyticsSummary(BaseModel):
    """Summary analytics for a user's skill log."""

    total_skills: int
    active_skills: int
    skills_by_state: Dict[str, int]
    recent_activity: List[Dict[str, Any]]
    stale_skills: List[Dict[str, Any]]
    total_log_entries: int
    average_confidence: Optional[float]
    total_hours_logged: float


class LinkSkillRequest(BaseModel):
    """Request model for linking skills in hierarchy."""

    parent_skill_id: str = Field(..., description="ID of the parent skill to link to")


class BatchSkillOperation(BaseModel):
    """Base model for batch skill operations."""

    skill_ids: List[str] = Field(..., description="List of skill IDs to operate on")


# Update forward reference for SkillTreeNode
SkillTreeNode.model_rebuild()
