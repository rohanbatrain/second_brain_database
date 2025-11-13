"""
IPAM Enhancement Pydantic Models.

This module contains request and response models for IPAM backend enhancements including:
- Reservations
- Shareable links
- User preferences
- Notifications
- Statistics and forecasting
- Webhooks
- Bulk operations
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from bson import ObjectId


# ============================================================================
# Utility Models
# ============================================================================

class PaginationResponse(BaseModel):
    """Pagination metadata for list responses."""
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_count: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


# ============================================================================
# Reservation Models (Task 2.1)
# ============================================================================

class ReservationCreateRequest(BaseModel):
    """Request model for creating a new reservation."""
    resource_type: Literal["region", "host"] = Field(..., description="Type of resource to reserve")
    x_octet: int = Field(..., ge=0, le=255, description="X octet value")
    y_octet: int = Field(..., ge=0, le=255, description="Y octet value")
    z_octet: Optional[int] = Field(None, ge=1, le=254, description="Z octet value (required for host reservations)")
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for reservation")
    expires_in_days: Optional[int] = Field(None, ge=1, le=90, description="Expiration in days (max 90)")

    @model_validator(mode='after')
    def validate_host_reservation(self):
        """Validate that host reservations include z_octet."""
        if self.resource_type == "host" and self.z_octet is None:
            raise ValueError("z_octet is required for host reservations")
        if self.resource_type == "region" and self.z_octet is not None:
            raise ValueError("z_octet should not be provided for region reservations")
        return self


class ReservationResponse(BaseModel):
    """Response model for reservation data."""
    reservation_id: str = Field(..., description="Unique reservation ID")
    user_id: str = Field(..., description="User who created the reservation")
    resource_type: Literal["region", "host"] = Field(..., description="Type of reserved resource")
    x_octet: int = Field(..., description="X octet value")
    y_octet: int = Field(..., description="Y octet value")
    z_octet: Optional[int] = Field(None, description="Z octet value (for hosts)")
    reserved_address: str = Field(..., description="Reserved IP address or CIDR")
    reason: str = Field(..., description="Reason for reservation")
    status: Literal["active", "expired", "converted"] = Field(..., description="Reservation status")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    created_by: str = Field(..., description="Username of creator")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "reservation_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_123",
                "resource_type": "region",
                "x_octet": 5,
                "y_octet": 23,
                "z_octet": None,
                "reserved_address": "10.5.23.0/24",
                "reason": "Reserved for Q1 expansion",
                "status": "active",
                "expires_at": "2025-12-31T23:59:59Z",
                "created_at": "2025-11-12T10:00:00Z",
                "created_by": "john.doe",
                "metadata": {}
            }
        }


class ReservationConvertRequest(BaseModel):
    """Request model for converting a reservation to an allocation."""
    region_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Region name (for region conversion)")
    hostname: Optional[str] = Field(None, min_length=1, max_length=100, description="Hostname (for host conversion)")
    description: Optional[str] = Field(None, max_length=2000, description="Description")
    owner: Optional[str] = Field(None, max_length=100, description="Owner/team identifier")
    tags: Optional[Dict[str, str]] = Field(default_factory=dict, description="Resource tags")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


# ============================================================================
# Sharing Models (Task 2.2)
# ============================================================================

class ShareCreateRequest(BaseModel):
    """Request model for creating a shareable link."""
    resource_type: Literal["country", "region", "host"] = Field(..., description="Type of resource to share")
    resource_id: str = Field(..., min_length=1, description="ID of resource to share")
    expires_in_days: int = Field(..., ge=1, le=90, description="Expiration in days (max 90)")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")


class ShareResponse(BaseModel):
    """Response model for share data."""
    share_id: str = Field(..., description="Unique share ID")
    share_token: str = Field(..., description="Share token (UUID)")
    share_url: str = Field(..., description="Full shareable URL")
    resource_type: Literal["country", "region", "host"] = Field(..., description="Type of shared resource")
    resource_id: str = Field(..., description="ID of shared resource")
    view_count: int = Field(default=0, description="Number of times accessed")
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    is_active: bool = Field(default=True, description="Whether share is active")

    class Config:
        json_schema_extra = {
            "example": {
                "share_id": "660e8400-e29b-41d4-a716-446655440001",
                "share_token": "abc123def456",
                "share_url": "https://api.example.com/ipam/shares/abc123def456",
                "resource_type": "region",
                "resource_id": "550e8400-e29b-41d4-a716-446655440000",
                "view_count": 5,
                "last_accessed": "2025-11-12T15:30:00Z",
                "expires_at": "2025-12-12T10:00:00Z",
                "created_at": "2025-11-12T10:00:00Z",
                "is_active": True
            }
        }


class ShareAccessResponse(BaseModel):
    """Response model for accessing a shared resource (sanitized)."""
    resource_type: Literal["country", "region", "host"] = Field(..., description="Type of shared resource")
    resource_data: Dict[str, Any] = Field(..., description="Sanitized resource data")
    shared_by: str = Field(..., description="Username of person who shared")
    created_at: datetime = Field(..., description="When share was created")


# ============================================================================
# User Preferences Models (Task 2.3)
# ============================================================================

class SavedFilterRequest(BaseModel):
    """Request model for saving a search filter."""
    name: str = Field(..., min_length=1, max_length=100, description="Filter name")
    criteria: Dict[str, Any] = Field(..., description="Filter criteria")

    @field_validator('criteria')
    @classmethod
    def validate_criteria_size(cls, v):
        """Ensure criteria is not too large."""
        import json
        if len(json.dumps(v)) > 10000:  # 10KB limit per filter
            raise ValueError("Filter criteria too large (max 10KB)")
        return v


class SavedFilterResponse(BaseModel):
    """Response model for saved filter data."""
    filter_id: str = Field(..., description="Unique filter ID")
    name: str = Field(..., description="Filter name")
    criteria: Dict[str, Any] = Field(..., description="Filter criteria")
    created_at: datetime = Field(..., description="Creation timestamp")


class UserPreferencesResponse(BaseModel):
    """Response model for user preferences."""
    user_id: str = Field(..., description="User ID")
    saved_filters: List[SavedFilterResponse] = Field(default_factory=list, description="Saved search filters")
    dashboard_layout: Dict[str, Any] = Field(default_factory=dict, description="Dashboard layout preferences")
    notification_settings: Dict[str, Any] = Field(default_factory=dict, description="Notification preferences")
    theme_preference: Optional[str] = Field(None, description="UI theme preference")
    updated_at: datetime = Field(..., description="Last update timestamp")


class PreferencesUpdateRequest(BaseModel):
    """Request model for updating user preferences."""
    dashboard_layout: Optional[Dict[str, Any]] = Field(None, description="Dashboard layout preferences")
    notification_settings: Optional[Dict[str, Any]] = Field(None, description="Notification preferences")
    theme_preference: Optional[str] = Field(None, max_length=50, description="UI theme preference")

    @model_validator(mode='after')
    def validate_size(self):
        """Ensure total preferences size doesn't exceed 50KB."""
        import json
        total_size = len(json.dumps(self.model_dump(exclude_none=True)))
        if total_size > 51200:  # 50KB
            raise ValueError("Preferences too large (max 50KB)")
        return self


# ============================================================================
# Notification Models (Task 2.4)
# ============================================================================

class NotificationRuleRequest(BaseModel):
    """Request model for creating a notification rule."""
    rule_name: str = Field(..., min_length=1, max_length=100, description="Rule name")
    conditions: Dict[str, Any] = Field(..., description="Rule conditions")
    notification_channels: List[Literal["in_app", "email", "webhook"]] = Field(
        default=["in_app"],
        description="Notification channels"
    )

    @field_validator('conditions')
    @classmethod
    def validate_conditions(cls, v):
        """Validate rule conditions."""
        if not v:
            raise ValueError("Conditions cannot be empty")
        # Validate utilization_threshold if present
        if 'utilization_threshold' in v:
            threshold = v['utilization_threshold']
            if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 100:
                raise ValueError("utilization_threshold must be between 0 and 100")
        return v


class NotificationRuleResponse(BaseModel):
    """Response model for notification rule data."""
    rule_id: str = Field(..., description="Unique rule ID")
    user_id: str = Field(..., description="User ID")
    rule_name: str = Field(..., description="Rule name")
    conditions: Dict[str, Any] = Field(..., description="Rule conditions")
    notification_channels: List[str] = Field(..., description="Notification channels")
    is_active: bool = Field(default=True, description="Whether rule is active")
    last_triggered: Optional[datetime] = Field(None, description="Last trigger timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class NotificationResponse(BaseModel):
    """Response model for notification data."""
    notification_id: str = Field(..., description="Unique notification ID")
    user_id: str = Field(..., description="User ID")
    notification_type: str = Field(..., description="Notification type")
    severity: Literal["info", "warning", "critical"] = Field(..., description="Severity level")
    message: str = Field(..., description="Notification message")
    resource_type: Optional[str] = Field(None, description="Related resource type")
    resource_id: Optional[str] = Field(None, description="Related resource ID")
    resource_link: Optional[str] = Field(None, description="Link to resource")
    is_read: bool = Field(default=False, description="Whether notification is read")
    read_at: Optional[datetime] = Field(None, description="Read timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")


class NotificationUpdateRequest(BaseModel):
    """Request model for updating a notification."""
    is_read: bool = Field(..., description="Mark as read/unread")


# ============================================================================
# Statistics & Forecasting Models (Task 2.5)
# ============================================================================

class DashboardStatsResponse(BaseModel):
    """Response model for dashboard statistics."""
    total_countries: int = Field(..., ge=0, description="Total number of countries")
    total_regions: int = Field(..., ge=0, description="Total number of regions")
    total_hosts: int = Field(..., ge=0, description="Total number of hosts")
    overall_utilization: float = Field(..., ge=0, le=100, description="Overall utilization percentage")
    top_countries: List[Dict[str, Any]] = Field(..., description="Top 5 countries by allocation")
    recent_activity_count: int = Field(..., ge=0, description="Recent activity count (last 7 days)")
    capacity_warnings: int = Field(..., ge=0, description="Number of capacity warnings")
    cached_at: Optional[datetime] = Field(None, description="Cache timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "total_countries": 15,
                "total_regions": 250,
                "total_hosts": 5000,
                "overall_utilization": 45.5,
                "top_countries": [
                    {"country": "India", "regions": 50, "utilization": 65.2},
                    {"country": "USA", "regions": 45, "utilization": 55.8}
                ],
                "recent_activity_count": 125,
                "capacity_warnings": 3,
                "cached_at": "2025-11-12T10:00:00Z"
            }
        }


class ForecastResponse(BaseModel):
    """Response model for capacity forecast."""
    resource_type: Literal["country", "region"] = Field(..., description="Resource type")
    resource_id: str = Field(..., description="Resource ID")
    current_utilization: float = Field(..., ge=0, le=100, description="Current utilization percentage")
    daily_allocation_rate: float = Field(..., description="Average daily allocation rate")
    estimated_exhaustion_date: Optional[datetime] = Field(None, description="Estimated exhaustion date")
    confidence_level: Literal["high", "medium", "low", "insufficient_data"] = Field(..., description="Confidence level")
    recommendation: str = Field(..., description="Recommendation text")
    data_points: int = Field(..., ge=0, description="Number of data points used")
    forecast_period_days: int = Field(..., ge=0, description="Forecast period in days")

    class Config:
        json_schema_extra = {
            "example": {
                "resource_type": "region",
                "resource_id": "550e8400-e29b-41d4-a716-446655440000",
                "current_utilization": 65.5,
                "daily_allocation_rate": 2.5,
                "estimated_exhaustion_date": "2026-02-15T00:00:00Z",
                "confidence_level": "high",
                "recommendation": "Consider allocating additional regions in this country",
                "data_points": 90,
                "forecast_period_days": 90
            }
        }


class TrendDataPoint(BaseModel):
    """Single data point in trend analysis."""
    timestamp: datetime = Field(..., description="Timestamp")
    allocations: int = Field(..., ge=0, description="Number of allocations")
    releases: int = Field(..., ge=0, description="Number of releases")
    net_growth: int = Field(..., description="Net growth (allocations - releases)")


class TrendDataResponse(BaseModel):
    """Response model for trend analysis."""
    time_series: List[TrendDataPoint] = Field(..., description="Time series data")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    group_by: Literal["day", "week", "month"] = Field(..., description="Grouping period")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")


# ============================================================================
# Webhook Models (Task 2.6)
# ============================================================================

class WebhookCreateRequest(BaseModel):
    """Request model for creating a webhook."""
    webhook_url: str = Field(..., min_length=1, max_length=500, description="Webhook URL")
    events: List[str] = Field(..., min_length=1, description="Events to subscribe to")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")

    @field_validator('webhook_url')
    @classmethod
    def validate_url(cls, v):
        """Validate webhook URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v

    @field_validator('events')
    @classmethod
    def validate_events(cls, v):
        """Validate event names."""
        valid_events = {
            "region.created", "region.updated", "region.retired",
            "host.allocated", "host.updated", "host.retired",
            "capacity.warning", "capacity.critical"
        }
        for event in v:
            if event not in valid_events:
                raise ValueError(f"Invalid event: {event}. Valid events: {valid_events}")
        return v


class WebhookResponse(BaseModel):
    """Response model for webhook data."""
    webhook_id: str = Field(..., description="Unique webhook ID")
    user_id: str = Field(..., description="User ID")
    webhook_url: str = Field(..., description="Webhook URL")
    secret_key: Optional[str] = Field(None, description="Secret key for HMAC (only on creation)")
    events: List[str] = Field(..., description="Subscribed events")
    is_active: bool = Field(default=True, description="Whether webhook is active")
    failure_count: int = Field(default=0, ge=0, description="Consecutive failure count")
    last_delivery: Optional[datetime] = Field(None, description="Last delivery timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class WebhookDeliveryResponse(BaseModel):
    """Response model for webhook delivery data."""
    delivery_id: str = Field(..., description="Unique delivery ID")
    webhook_id: str = Field(..., description="Webhook ID")
    event_type: str = Field(..., description="Event type")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    response_time_ms: Optional[int] = Field(None, ge=0, description="Response time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    attempt_number: int = Field(..., ge=1, le=3, description="Attempt number (1-3)")
    delivered_at: datetime = Field(..., description="Delivery timestamp")


# ============================================================================
# Bulk Operations Models (Task 2.7)
# ============================================================================

class BulkTagUpdateRequest(BaseModel):
    """Request model for bulk tag updates."""
    resource_type: Literal["region", "host"] = Field(..., description="Resource type")
    resource_ids: List[str] = Field(..., min_length=1, max_length=500, description="Resource IDs (max 500)")
    operation: Literal["add", "remove", "replace"] = Field(..., description="Tag operation")
    tags: Dict[str, str] = Field(..., description="Tags to add/remove/replace")

    @field_validator('resource_ids')
    @classmethod
    def validate_resource_ids(cls, v):
        """Validate resource IDs list."""
        if len(v) > 500:
            raise ValueError("Maximum 500 resources per bulk operation")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate resource IDs not allowed")
        return v


class BulkJobResponse(BaseModel):
    """Response model for bulk job creation."""
    job_id: str = Field(..., description="Unique job ID")
    operation_type: str = Field(..., description="Operation type")
    total_items: int = Field(..., ge=0, description="Total items to process")
    status: Literal["pending", "processing", "completed", "failed"] = Field(..., description="Job status")
    created_at: datetime = Field(..., description="Creation timestamp")


class BulkJobStatusResponse(BaseModel):
    """Response model for bulk job status."""
    job_id: str = Field(..., description="Unique job ID")
    user_id: str = Field(..., description="User ID")
    operation_type: str = Field(..., description="Operation type")
    total_items: int = Field(..., ge=0, description="Total items")
    processed_items: int = Field(..., ge=0, description="Processed items")
    successful_items: int = Field(..., ge=0, description="Successful items")
    failed_items: int = Field(..., ge=0, description="Failed items")
    status: Literal["pending", "processing", "completed", "failed"] = Field(..., description="Job status")
    progress_percent: float = Field(..., ge=0, le=100, description="Progress percentage")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="Operation results")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

    @model_validator(mode='after')
    def calculate_progress(self):
        """Calculate progress percentage."""
        if self.total_items > 0:
            self.progress_percent = (self.processed_items / self.total_items) * 100
        else:
            self.progress_percent = 0.0
        return self
