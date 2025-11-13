"""
Pydantic models for IPAM (IP Address Management) system.

This module contains all request/response models, validation schemas,
and data transfer objects for the hierarchical IP allocation functionality.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Constants for validation
VALID_STATUSES = ["Active", "Reserved", "Retired"]
VALID_DEVICE_TYPES = ["VM", "Container", "Physical", "Network", "Storage", "Other"]
TAG_KEY_PATTERN = r"^[a-zA-Z0-9_-]+$"


# Request Models - Region Management
class RegionCreateRequest(BaseModel):
    """Request model for creating a new region allocation."""

    country: str = Field(..., min_length=2, max_length=100, description="Country name for region allocation")
    region_name: str = Field(..., min_length=2, max_length=100, description="User-defined region name")
    description: Optional[str] = Field(None, max_length=500, description="Optional region description")
    owner: Optional[str] = Field(None, max_length=100, description="Team or owner identifier")
    tags: Optional[Dict[str, str]] = Field(None, description="Key-value tags for organization")

    @field_validator("country")
    @classmethod
    def validate_country(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Country name cannot be empty")
        return v

    @field_validator("region_name")
    @classmethod
    def validate_region_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Region name cannot be empty")
        if len(v) < 2:
            raise ValueError("Region name must be at least 2 characters long")
        # Prevent special characters that could cause issues
        if any(char in v for char in ["<", ">", "&", '"', "'"]):
            raise ValueError("Region name contains invalid characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        return v.strip() if v else None

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, v):
        return v.strip() if v else None


class RegionUpdateRequest(BaseModel):
    """Request model for updating an existing region."""

    region_name: Optional[str] = Field(None, min_length=2, max_length=100, description="Updated region name")
    description: Optional[str] = Field(None, max_length=500, description="Updated description")
    owner: Optional[str] = Field(None, max_length=100, description="Updated owner")
    status: Optional[Literal["Active", "Reserved", "Retired"]] = Field(None, description="Updated status")
    tags: Optional[Dict[str, str]] = Field(None, description="Updated tags")

    @field_validator("region_name")
    @classmethod
    def validate_region_name(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Region name cannot be empty")
            if len(v) < 2:
                raise ValueError("Region name must be at least 2 characters long")
            if any(char in v for char in ["<", ">", "&", '"', "'"]):
                raise ValueError("Region name contains invalid characters")
        return v

    @field_validator("description", "owner")
    @classmethod
    def validate_optional_strings(cls, v):
        return v.strip() if v else None


# Request Models - Host Management
class HostCreateRequest(BaseModel):
    """Request model for creating a new host allocation."""

    region_id: str = Field(..., description="Region ID where host will be allocated")
    hostname: str = Field(..., min_length=1, max_length=253, description="Hostname for the device")
    device_type: Optional[Literal["VM", "Container", "Physical", "Network", "Storage", "Other"]] = Field(
        None, description="Type of device"
    )
    os_type: Optional[str] = Field(None, max_length=100, description="Operating system type")
    application: Optional[str] = Field(None, max_length=200, description="Application running on host")
    cost_center: Optional[str] = Field(None, max_length=100, description="Cost center for billing")
    owner: Optional[str] = Field(None, max_length=100, description="Team or owner identifier")
    purpose: Optional[str] = Field(None, max_length=500, description="Purpose or description")
    tags: Optional[Dict[str, str]] = Field(None, description="Key-value tags for organization")
    notes: Optional[str] = Field(None, max_length=2000, description="Additional notes")

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError("Hostname cannot be empty")
        # Basic hostname validation (RFC 1123)
        if not all(c.isalnum() or c in ["-", "."] for c in v):
            raise ValueError("Hostname can only contain alphanumeric characters, hyphens, and dots")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Hostname cannot start or end with a hyphen")
        return v

    @field_validator("os_type", "application", "cost_center", "owner", "purpose", "notes")
    @classmethod
    def validate_optional_strings(cls, v):
        return v.strip() if v else None


class HostUpdateRequest(BaseModel):
    """Request model for updating an existing host."""

    hostname: Optional[str] = Field(None, min_length=1, max_length=253, description="Updated hostname")
    device_type: Optional[Literal["VM", "Container", "Physical", "Network", "Storage", "Other"]] = Field(
        None, description="Updated device type"
    )
    os_type: Optional[str] = Field(None, max_length=100, description="Updated OS type")
    application: Optional[str] = Field(None, max_length=200, description="Updated application")
    cost_center: Optional[str] = Field(None, max_length=100, description="Updated cost center")
    owner: Optional[str] = Field(None, max_length=100, description="Updated owner")
    purpose: Optional[str] = Field(None, max_length=500, description="Updated purpose")
    status: Optional[Literal["Active", "Reserved", "Released"]] = Field(None, description="Updated status")
    tags: Optional[Dict[str, str]] = Field(None, description="Updated tags")
    notes: Optional[str] = Field(None, max_length=2000, description="Updated notes")

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v):
        if v is not None:
            v = v.strip().lower()
            if not v:
                raise ValueError("Hostname cannot be empty")
            if not all(c.isalnum() or c in ["-", "."] for c in v):
                raise ValueError("Hostname can only contain alphanumeric characters, hyphens, and dots")
            if v.startswith("-") or v.endswith("-"):
                raise ValueError("Hostname cannot start or end with a hyphen")
        return v

    @field_validator("os_type", "application", "cost_center", "owner", "purpose", "notes")
    @classmethod
    def validate_optional_strings(cls, v):
        return v.strip() if v else None


class BatchHostCreateRequest(BaseModel):
    """Request model for batch host allocation."""

    region_id: str = Field(..., description="Region ID where hosts will be allocated")
    count: int = Field(..., ge=1, le=100, description="Number of hosts to allocate (max 100)")
    hostname_prefix: str = Field(..., min_length=1, max_length=240, description="Prefix for generated hostnames")
    device_type: Optional[Literal["VM", "Container", "Physical", "Network", "Storage", "Other"]] = Field(
        None, description="Device type for all hosts"
    )
    owner: Optional[str] = Field(None, max_length=100, description="Owner for all hosts")
    tags: Optional[Dict[str, str]] = Field(None, description="Tags for all hosts")

    @field_validator("hostname_prefix")
    @classmethod
    def validate_hostname_prefix(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError("Hostname prefix cannot be empty")
        if not all(c.isalnum() or c in ["-"] for c in v):
            raise ValueError("Hostname prefix can only contain alphanumeric characters and hyphens")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Hostname prefix cannot start or end with a hyphen")
        return v


# Request Models - Comments
class CommentCreateRequest(BaseModel):
    """Request model for adding a comment to a resource."""

    comment_text: str = Field(..., min_length=1, max_length=2000, description="Comment text")

    @field_validator("comment_text")
    @classmethod
    def validate_comment_text(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Comment text cannot be empty")
        return v


# Request Models - Retirement and Release
class RetireAllocationRequest(BaseModel):
    """Request model for retiring an allocation."""

    reason: str = Field(..., min_length=5, max_length=500, description="Reason for retirement")
    cascade: bool = Field(False, description="For regions: also retire all child hosts")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Reason cannot be empty")
        if len(v) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v


class BulkReleaseRequest(BaseModel):
    """Request model for bulk host release."""

    host_ids: List[str] = Field(..., min_items=1, max_items=100, description="List of host IDs to release")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for release")

    @field_validator("host_ids")
    @classmethod
    def validate_host_ids(cls, v):
        if not v:
            raise ValueError("At least one host ID must be provided")
        if len(v) > 100:
            raise ValueError("Cannot release more than 100 hosts at once")
        # Remove duplicates
        return list(set(v))

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Reason cannot be empty")
        if len(v) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v


# Request Models - Reservation
class ReservationCreateRequest(BaseModel):
    """Request model for creating a reservation."""

    resource_type: Literal["region", "host"] = Field(..., description="Type of resource to reserve")
    x_octet: int = Field(..., ge=0, le=255, description="X octet value")
    y_octet: int = Field(..., ge=0, le=255, description="Y octet value")
    z_octet: Optional[int] = Field(None, ge=1, le=254, description="Z octet value (for host reservations)")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for reservation")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Reason cannot be empty")
        if len(v) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v


# Request Models - Search and Filtering
class SearchRequest(BaseModel):
    """Request model for searching allocations."""

    ip_address: Optional[str] = Field(None, description="IP address for exact or partial match")
    cidr: Optional[str] = Field(None, description="CIDR range for matching")
    hostname: Optional[str] = Field(None, description="Hostname for partial match (case-insensitive)")
    region_name: Optional[str] = Field(None, description="Region name for partial match")
    continent: Optional[str] = Field(None, description="Filter by continent")
    country: Optional[str] = Field(None, description="Filter by country")
    status: Optional[Literal["Active", "Reserved", "Retired", "Released"]] = Field(None, description="Filter by status")
    owner: Optional[str] = Field(None, description="Filter by owner")
    tags: Optional[Dict[str, str]] = Field(None, description="Filter by tags (AND logic)")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date (after)")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date (before)")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=100, description="Results per page (max 100)")


# Request Models - Import/Export
class ExportRequest(BaseModel):
    """Request model for exporting allocations."""

    format: Literal["csv", "json"] = Field("json", description="Export format")
    resource_type: Optional[Literal["regions", "hosts", "all"]] = Field("all", description="Resources to export")
    include_hierarchy: bool = Field(True, description="Include hierarchical structure")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters to apply")


class ImportRequest(BaseModel):
    """Request model for importing allocations."""

    mode: Literal["auto", "manual", "preview"] = Field("preview", description="Import mode")
    force: bool = Field(False, description="Skip existing allocations without error")


# Response Models - Country and Mapping
class CountryResponse(BaseModel):
    """Response model for country information."""

    continent: str
    country: str
    x_start: int
    x_end: int
    total_blocks: int
    allocated_regions: int
    remaining_capacity: int
    utilization_percent: float
    is_reserved: bool


class ContinentCountryMapping(BaseModel):
    """Response model for continent-country mapping."""

    continent: str
    countries: List[CountryResponse]


# Response Models - Utilization Statistics
class UtilizationStats(BaseModel):
    """Response model for utilization statistics."""

    total_capacity: int
    allocated: int
    available: int
    utilization_percent: float
    breakdown: Optional[Dict[str, Any]] = None


class RegionUtilizationResponse(BaseModel):
    """Response model for region utilization."""

    region_id: str
    cidr: str
    region_name: str
    total_hosts: int = 254
    allocated_hosts: int
    available_hosts: int
    utilization_percent: float


class CountryUtilizationResponse(BaseModel):
    """Response model for country utilization."""

    country: str
    continent: str
    x_range: str
    total_capacity: int
    allocated_regions: int
    utilization_percent: float
    x_value_breakdown: List[Dict[str, Any]]


# Response Models - Region
class CommentResponse(BaseModel):
    """Response model for a comment."""

    text: str
    author_id: str
    timestamp: datetime


class RegionResponse(BaseModel):
    """Response model for region allocation."""

    region_id: str
    user_id: str
    country: str
    continent: str
    x_octet: int
    y_octet: int
    cidr: str
    region_name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    status: str
    tags: Dict[str, str] = {}
    comments: List[CommentResponse] = []
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


# Response Models - Host
class HostResponse(BaseModel):
    """Response model for host allocation."""

    host_id: str
    user_id: str
    region_id: str
    x_octet: int
    y_octet: int
    z_octet: int
    ip_address: str
    hostname: str
    device_type: Optional[str] = None
    os_type: Optional[str] = None
    application: Optional[str] = None
    cost_center: Optional[str] = None
    owner: Optional[str] = None
    purpose: Optional[str] = None
    status: str
    tags: Dict[str, str] = {}
    notes: Optional[str] = None
    comments: List[CommentResponse] = []
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


# Response Models - Batch Operations
class BatchHostCreateResult(BaseModel):
    """Response model for batch host creation."""

    total_requested: int
    successful: int
    failed: int
    hosts: List[HostResponse]
    errors: List[Dict[str, Any]] = []


class BulkReleaseResult(BaseModel):
    """Response model for bulk host release."""

    total_requested: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]


# Response Models - IP Interpretation
class HostHierarchyInfo(BaseModel):
    """Host information in hierarchy."""

    host_id: str
    hostname: str
    z_octet: int
    status: str
    device_type: Optional[str] = None


class RegionHierarchyInfo(BaseModel):
    """Region information in hierarchy."""

    region_id: str
    region_name: str
    cidr: str
    y_octet: int
    status: str


class CountryHierarchyInfo(BaseModel):
    """Country information in hierarchy."""

    name: str
    x_range: str
    x_octet: int


class IPHierarchyResponse(BaseModel):
    """Response model for IP address interpretation."""

    ip_address: str
    hierarchy: Dict[str, Any]


# Response Models - Validation
class ValidationResult(BaseModel):
    """Response model for validation results."""

    valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class ImportValidationResult(BaseModel):
    """Response model for import validation."""

    valid: bool
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []


# Response Models - Search and Pagination
class PaginationMetadata(BaseModel):
    """Pagination metadata."""

    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class SearchResponse(BaseModel):
    """Response model for search results."""

    results: List[Dict[str, Any]]
    pagination: PaginationMetadata
    filters_applied: Dict[str, Any]


# Response Models - Audit and History
class AuditChangeEntry(BaseModel):
    """Model for field-level change in audit history."""

    field: str
    old_value: Any
    new_value: Any


class AuditHistoryEntry(BaseModel):
    """Response model for audit history entry."""

    audit_id: str
    user_id: str
    action_type: str
    resource_type: str
    resource_id: str
    ip_address: Optional[str] = None
    cidr: Optional[str] = None
    snapshot: Dict[str, Any]
    changes: List[AuditChangeEntry] = []
    reason: Optional[str] = None
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class AuditHistoryResponse(BaseModel):
    """Response model for audit history query."""

    entries: List[AuditHistoryEntry]
    pagination: PaginationMetadata


# Response Models - Quota Management
class QuotaResponse(BaseModel):
    """Response model for user quota information."""

    user_id: str
    region_quota: int
    host_quota: int
    region_count: int
    host_count: int
    region_usage_percent: float
    host_usage_percent: float
    last_updated: datetime


# Response Models - Statistics and Analytics
class AllocationVelocityResponse(BaseModel):
    """Response model for allocation velocity metrics."""

    time_range: str
    allocations_per_day: float
    allocations_per_week: float
    allocations_per_month: float
    trend: str  # "increasing", "decreasing", "stable"


class TopUtilizedResource(BaseModel):
    """Model for top utilized resource."""

    resource_type: str
    resource_id: str
    resource_name: str
    utilization_percent: float
    allocated: int
    total_capacity: int


class ContinentStatisticsResponse(BaseModel):
    """Response model for continent statistics."""

    continent: str
    total_countries: int
    total_capacity: int
    allocated_regions: int
    utilization_percent: float
    countries: List[CountryUtilizationResponse]


# Response Models - Preview
class NextAvailablePreview(BaseModel):
    """Response model for next available allocation preview."""

    available: bool
    next_allocation: Optional[str] = None
    message: str


# Response Models - Export Job
class ExportJobResponse(BaseModel):
    """Response model for export job."""

    job_id: str
    status: str
    format: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None


# Error Response Models
class IPAMErrorResponse(BaseModel):
    """Error response model for IPAM operations."""

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class CapacityExhaustedError(BaseModel):
    """Error response for capacity exhaustion."""

    error: str = "capacity_exhausted"
    message: str
    details: Dict[str, Any]


class QuotaExceededError(BaseModel):
    """Error response for quota exceeded."""

    error: str = "quota_exceeded"
    message: str
    quota_type: str
    current_usage: int
    quota_limit: int
