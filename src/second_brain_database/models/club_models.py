"""
Club Management Models for Second Brain Database.

This module defines Pydantic models for university clubs, verticals, and members
with comprehensive validation and hierarchical relationships.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import re


class ClubRole(str, Enum):
    """Club member roles with hierarchical permissions."""
    OWNER = "owner"
    ADMIN = "admin"
    LEAD = "lead"
    MEMBER = "member"


class ClubCategory(str, Enum):
    """Club categories for organization and discovery."""
    TECH = "tech"
    CULTURAL = "cultural"
    SPORTS = "sports"
    ACADEMIC = "academic"
    SOCIAL = "social"
    ENTREPRENEURSHIP = "entrepreneurship"
    ENVIRONMENTAL = "environmental"
    ARTS = "arts"
    OTHER = "other"


class UniversityStatus(str, Enum):
    """University verification status."""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


# Document Models (for MongoDB)

class UniversityDocument(BaseModel):
    """University/Institution document model."""
    university_id: str = Field(..., description="Unique university identifier")
    name: str = Field(..., min_length=2, max_length=200, description="University name")
    domain: str = Field(..., description="Primary domain (e.g., university.edu)")
    description: Optional[str] = Field(None, max_length=1000, description="University description")
    location: Optional[str] = Field(None, max_length=200, description="University location")
    website: Optional[str] = Field(None, description="University website URL")
    logo_url: Optional[str] = Field(None, description="University logo URL")
    is_verified: bool = Field(default=False, description="Domain verification status")
    admin_approved: bool = Field(default=False, description="Admin approval status")
    status: UniversityStatus = Field(default=UniversityStatus.PENDING, description="Verification status")
    created_by: str = Field(..., description="User ID who requested university")
    approved_by: Optional[str] = Field(None, description="Admin ID who approved")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    club_count: int = Field(default=0, description="Number of active clubs")
    total_members: int = Field(default=0, description="Total members across all clubs")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator('domain')
    @classmethod
    def validate_domain(cls, v):
        """Validate domain format."""
        if not v:
            raise ValueError('Domain is required')
        # Basic domain validation
        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, v):
            raise ValueError('Invalid domain format')
        return v.lower()

    @field_validator('website')
    @classmethod
    def validate_website(cls, v):
        """Validate website URL format."""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Website must start with http:// or https://')
        return v


class ClubDocument(BaseModel):
    """Club document model."""
    club_id: str = Field(..., description="Unique club identifier")
    name: str = Field(..., min_length=2, max_length=100, description="Club name")
    slug: str = Field(..., description="URL-friendly slug")
    description: Optional[str] = Field(None, max_length=1000, description="Club description")
    category: ClubCategory = Field(..., description="Club category")
    university_id: str = Field(..., description="Parent university ID")
    owner_id: str = Field(..., description="Club owner user ID")
    logo_url: Optional[str] = Field(None, description="Club logo URL")
    banner_url: Optional[str] = Field(None, description="Club banner image URL")
    website_url: Optional[str] = Field(None, description="Club website URL")
    social_links: Dict[str, str] = Field(default_factory=dict, description="Social media links")
    is_active: bool = Field(default=True, description="Club active status")
    is_public: bool = Field(default=True, description="Public visibility")
    member_count: int = Field(default=1, description="Total member count")
    vertical_count: int = Field(default=0, description="Number of verticals")
    max_members: Optional[int] = Field(None, description="Maximum member limit")
    tags: List[str] = Field(default_factory=list, description="Club tags for search")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Club-specific settings")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v):
        """Validate slug format."""
        if not v:
            raise ValueError('Slug is required')
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Slug must be between 3 and 50 characters')
        return v

    @model_validator(mode='after')
    def generate_slug_from_name(self):
        """Auto-generate slug from name if not provided."""
        if not self.slug and self.name:
            # Generate slug from name
            slug = re.sub(r'[^\w\s-]', '', self.name.lower())
            slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
            self.slug = slug[:50]  # Limit length
        return self


class VerticalDocument(BaseModel):
    """Club vertical/team document model."""
    vertical_id: str = Field(..., description="Unique vertical identifier")
    club_id: str = Field(..., description="Parent club ID")
    name: str = Field(..., min_length=2, max_length=50, description="Vertical name")
    description: Optional[str] = Field(None, max_length=500, description="Vertical description")
    lead_id: Optional[str] = Field(None, description="Vertical lead user ID")
    member_count: int = Field(default=0, description="Number of members in vertical")
    max_members: Optional[int] = Field(None, description="Maximum member limit")
    color: Optional[str] = Field(None, description="Vertical color/theme")
    icon: Optional[str] = Field(None, description="Vertical icon identifier")
    is_active: bool = Field(default=True, description="Vertical active status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClubMemberDocument(BaseModel):
    """Club membership document model."""
    member_id: str = Field(..., description="Unique membership identifier")
    club_id: str = Field(..., description="Club ID")
    user_id: str = Field(..., description="User ID")
    role: ClubRole = Field(..., description="Member role in club")
    vertical_id: Optional[str] = Field(None, description="Assigned vertical ID")
    invited_by: str = Field(..., description="User ID who invited this member")
    invited_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    joined_at: Optional[datetime] = Field(None, description="When member accepted invitation")
    is_active: bool = Field(default=True, description="Membership active status")
    is_alumni: bool = Field(default=False, description="Alumni status")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    contributions: int = Field(default=0, description="Contribution/activity score")
    notes: Optional[str] = Field(None, max_length=500, description="Admin notes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def set_joined_at(self):
        """Set joined_at when membership becomes active."""
        if self.is_active and not self.joined_at:
            self.joined_at = datetime.now(timezone.utc)
        return self


# Request/Response Models (for API)

class CreateUniversityRequest(BaseModel):
    """Request model for creating a university."""
    name: str = Field(..., min_length=2, max_length=200)
    domain: str = Field(...)
    description: Optional[str] = Field(None, max_length=1000)
    location: Optional[str] = Field(None, max_length=200)
    website: Optional[str] = Field(None)
    logo_url: Optional[str] = Field(None)


class UniversityResponse(BaseModel):
    """Response model for university data."""
    university_id: str
    name: str
    domain: str
    description: Optional[str]
    location: Optional[str]
    website: Optional[str]
    logo_url: Optional[str]
    is_verified: bool
    admin_approved: bool
    status: UniversityStatus
    club_count: int
    total_members: int
    created_at: datetime
    updated_at: datetime


class CreateClubRequest(BaseModel):
    """Request model for creating a club."""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    category: ClubCategory = Field(...)
    university_id: str = Field(...)
    logo_url: Optional[str] = Field(None)
    banner_url: Optional[str] = Field(None)
    website_url: Optional[str] = Field(None)
    social_links: Dict[str, str] = Field(default_factory=dict)
    max_members: Optional[int] = Field(None, gt=0, le=10000)
    tags: List[str] = Field(default_factory=list)


class ClubResponse(BaseModel):
    """Response model for club data."""
    club_id: str
    name: str
    slug: str
    description: Optional[str]
    category: ClubCategory
    university_id: str
    owner_id: str
    logo_url: Optional[str]
    banner_url: Optional[str]
    website_url: Optional[str]
    social_links: Dict[str, str]
    is_active: bool
    is_public: bool
    member_count: int
    vertical_count: int
    max_members: Optional[int]
    tags: List[str]
    created_at: datetime
    updated_at: datetime


class CreateVerticalRequest(BaseModel):
    """Request model for creating a vertical."""
    name: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    lead_id: Optional[str] = Field(None)
    max_members: Optional[int] = Field(None, gt=0, le=1000)
    color: Optional[str] = Field(None)
    icon: Optional[str] = Field(None)


class VerticalResponse(BaseModel):
    """Response model for vertical data."""
    vertical_id: str
    club_id: str
    name: str
    description: Optional[str]
    lead_id: Optional[str]
    member_count: int
    max_members: Optional[int]
    color: Optional[str]
    icon: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class InviteMemberRequest(BaseModel):
    """Request model for inviting a member."""
    user_id: str = Field(..., description="User ID to invite")
    role: ClubRole = Field(..., description="Role to assign")
    vertical_id: Optional[str] = Field(None, description="Vertical to assign")
    message: Optional[str] = Field(None, max_length=500, description="Invitation message")


class ClubMemberResponse(BaseModel):
    """Response model for club member data."""
    member_id: str
    club_id: str
    user_id: str
    role: ClubRole
    vertical_id: Optional[str]
    invited_by: str
    invited_at: datetime
    joined_at: Optional[datetime]
    is_active: bool
    is_alumni: bool
    last_activity: Optional[datetime]
    contributions: int
    created_at: datetime
    updated_at: datetime


class ClubSearchRequest(BaseModel):
    """Request model for club search."""
    query: Optional[str] = Field(None, description="Search query")
    category: Optional[ClubCategory] = Field(None, description="Filter by category")
    university_id: Optional[str] = Field(None, description="Filter by university")
    tags: List[str] = Field(default_factory=list, description="Filter by tags")
    page: int = Field(default=1, gt=0, description="Page number")
    limit: int = Field(default=20, gt=0, le=100, description="Results per page")


class ClubAnalyticsResponse(BaseModel):
    """Response model for club analytics."""
    club_id: str
    member_growth: List[Dict[str, Any]] = Field(default_factory=list)
    vertical_participation: Dict[str, int] = Field(default_factory=dict)
    activity_metrics: Dict[str, Any] = Field(default_factory=dict)
    engagement_score: float = Field(default=0.0)


class BulkInviteRequest(BaseModel):
    """Request model for bulk member invitation."""
    invites: List[InviteMemberRequest] = Field(..., min_length=1, max_length=50)


class TransferMemberRequest(BaseModel):
    """Request model for transferring member between verticals."""
    member_id: str = Field(...)
    vertical_id: Optional[str] = Field(None, description="New vertical ID, null to remove")


class UpdateMemberRoleRequest(BaseModel):
    """Request model for updating member role."""
    role: ClubRole = Field(...)
    vertical_id: Optional[str] = Field(None, description="Optional vertical assignment")


# Event Models

class EventType(str, Enum):
    """Types of club events."""
    MEETING = "meeting"
    WORKSHOP = "workshop"
    SOCIAL = "social"
    COMPETITION = "competition"
    CONFERENCE = "conference"
    NETWORKING = "networking"
    OTHER = "other"


class EventStatus(str, Enum):
    """Event status states."""
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class EventVisibility(str, Enum):
    """Event visibility settings."""
    PUBLIC = "public"
    MEMBERS_ONLY = "members_only"
    INVITE_ONLY = "invite_only"


class EventDocument(BaseModel):
    """Club event document model."""
    event_id: str = Field(..., description="Unique event identifier")
    club_id: str = Field(..., description="Parent club ID")
    title: str = Field(..., min_length=3, max_length=200, description="Event title")
    description: Optional[str] = Field(None, max_length=2000, description="Event description")
    event_type: EventType = Field(..., description="Type of event")
    status: EventStatus = Field(default=EventStatus.DRAFT, description="Event status")
    visibility: EventVisibility = Field(default=EventVisibility.MEMBERS_ONLY, description="Event visibility")
    start_time: datetime = Field(..., description="Event start time")
    end_time: datetime = Field(..., description="Event end time")
    timezone: str = Field(default="UTC", description="Event timezone")
    location: Optional[str] = Field(None, max_length=500, description="Physical location")
    virtual_link: Optional[str] = Field(None, description="Virtual meeting link")
    max_attendees: Optional[int] = Field(None, gt=0, description="Maximum number of attendees")
    attendee_count: int = Field(default=0, description="Current attendee count")
    organizer_id: str = Field(..., description="Event organizer user ID")
    co_organizers: List[str] = Field(default_factory=list, description="Co-organizer user IDs")
    tags: List[str] = Field(default_factory=list, description="Event tags")
    image_url: Optional[str] = Field(None, description="Event image/banner URL")
    agenda: List[Dict[str, Any]] = Field(default_factory=list, description="Event agenda items")
    requirements: List[str] = Field(default_factory=list, description="Event requirements/prerequisites")
    is_recurring: bool = Field(default=False, description="Whether event is recurring")
    recurrence_rule: Optional[str] = Field(None, description="Recurrence rule (RRULE)")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID for recurring events")
    webrtc_room_id: Optional[str] = Field(None, description="WebRTC room ID for virtual events")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Event-specific settings")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def validate_times(self):
        """Validate event timing."""
        if self.end_time <= self.start_time:
            raise ValueError('End time must be after start time')
        return self


class EventAttendeeDocument(BaseModel):
    """Event attendee document model."""
    attendee_id: str = Field(..., description="Unique attendee identifier")
    event_id: str = Field(..., description="Event ID")
    user_id: str = Field(..., description="Attendee user ID")
    status: str = Field(default="registered", description="Attendance status")
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attended_at: Optional[datetime] = Field(None, description="When user marked as attended")
    notes: Optional[str] = Field(None, max_length=500, description="Attendee notes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Event Request/Response Models

class CreateEventRequest(BaseModel):
    """Request model for creating an event."""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    event_type: EventType = Field(...)
    visibility: EventVisibility = Field(default=EventVisibility.MEMBERS_ONLY)
    start_time: datetime = Field(...)
    end_time: datetime = Field(...)
    timezone: str = Field(default="UTC")
    location: Optional[str] = Field(None, max_length=500)
    virtual_link: Optional[str] = Field(None)
    max_attendees: Optional[int] = Field(None, gt=0)
    co_organizers: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    image_url: Optional[str] = Field(None)
    agenda: List[Dict[str, Any]] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    is_recurring: bool = Field(default=False)
    recurrence_rule: Optional[str] = Field(None)

    @model_validator(mode='after')
    def validate_times(self):
        """Validate event timing."""
        if self.end_time <= self.start_time:
            raise ValueError('End time must be after start time')
        return self


class EventResponse(BaseModel):
    """Response model for event data."""
    event_id: str
    club_id: str
    title: str
    description: Optional[str]
    event_type: EventType
    status: EventStatus
    visibility: EventVisibility
    start_time: datetime
    end_time: datetime
    timezone: str
    location: Optional[str]
    virtual_link: Optional[str]
    max_attendees: Optional[int]
    attendee_count: int
    organizer_id: str
    co_organizers: List[str]
    tags: List[str]
    image_url: Optional[str]
    agenda: List[Dict[str, Any]]
    requirements: List[str]
    is_recurring: bool
    recurrence_rule: Optional[str]
    parent_event_id: Optional[str]
    webrtc_room_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class UpdateEventRequest(BaseModel):
    """Request model for updating an event."""
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    event_type: Optional[EventType] = Field(None)
    visibility: Optional[EventVisibility] = Field(None)
    start_time: Optional[datetime] = Field(None)
    end_time: Optional[datetime] = Field(None)
    timezone: Optional[str] = Field(None)
    location: Optional[str] = Field(None, max_length=500)
    virtual_link: Optional[str] = Field(None)
    max_attendees: Optional[int] = Field(None, gt=0)
    co_organizers: Optional[List[str]] = Field(None)
    tags: Optional[List[str]] = Field(None)
    image_url: Optional[str] = Field(None)
    agenda: Optional[List[Dict[str, Any]]] = Field(None)
    requirements: Optional[List[str]] = Field(None)
    status: Optional[EventStatus] = Field(None)


class EventAttendeeResponse(BaseModel):
    """Response model for event attendee data."""
    attendee_id: str
    event_id: str
    user_id: str
    status: str
    registered_at: datetime
    attended_at: Optional[datetime]
    notes: Optional[str]


class RegisterForEventRequest(BaseModel):
    """Request model for registering for an event."""
    notes: Optional[str] = Field(None, max_length=500)


class EventSearchRequest(BaseModel):
    """Request model for event search."""
    query: Optional[str] = Field(None, description="Search query")
    event_type: Optional[EventType] = Field(None, description="Filter by event type")
    status: Optional[EventStatus] = Field(None, description="Filter by status")
    visibility: Optional[EventVisibility] = Field(None, description="Filter by visibility")
    start_date: Optional[datetime] = Field(None, description="Events starting after this date")
    end_date: Optional[datetime] = Field(None, description="Events ending before this date")
    club_id: Optional[str] = Field(None, description="Filter by club")
    organizer_id: Optional[str] = Field(None, description="Filter by organizer")
    tags: List[str] = Field(default_factory=list, description="Filter by tags")
    page: int = Field(default=1, gt=0, description="Page number")
    limit: int = Field(default=20, gt=0, le=100, description="Results per page")
