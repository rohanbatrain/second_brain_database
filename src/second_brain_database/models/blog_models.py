"""
Pydantic models for the blog system.

This module contains all request/response models, validation schemas,
and data transfer objects for the blog functionality.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# Constants for validation
BLOG_POST_STATUSES = ["draft", "published", "scheduled", "archived"]
COMMENT_STATUSES = ["pending", "approved", "rejected", "spam"]
WEBSITE_ROLES = ["owner", "admin", "editor", "author", "viewer"]

# Enums
class BlogPostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    ARCHIVED = "archived"


class CommentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SPAM = "spam"



class WebsiteRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    AUTHOR = "author"
    VIEWER = "viewer"


class BlogVersion(BaseModel):
    """Model for a blog post version."""
    version_id: str
    post_id: str
    title: str
    content: str
    excerpt: Optional[str]
    created_at: datetime
    created_by: str
    change_summary: Optional[str]



# Request Models
class CreateBlogWebsiteRequest(BaseModel):
    """Request model for creating a new blog website."""

    name: str = Field(..., min_length=1, max_length=100, description="Website name")
    slug: str = Field(..., min_length=1, max_length=50, description="Unique website slug for URLs")
    description: Optional[str] = Field(None, max_length=500, description="Website description")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        v = v.lower().strip()
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Slug can only contain letters, numbers, hyphens, and underscores")
        if v.startswith(("-", "_")) or v.endswith(("-", "_")):
            raise ValueError("Slug cannot start or end with hyphens or underscores")
        return v


class UpdateBlogWebsiteRequest(BaseModel):
    """Request model for updating a blog website."""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Website name")
    description: Optional[str] = Field(None, max_length=500, description="Website description")
    is_active: Optional[bool] = Field(None, description="Whether website is active")
    is_public: Optional[bool] = Field(None, description="Whether website is public")
    allow_comments: Optional[bool] = Field(None, description="Whether to allow comments")
    require_comment_approval: Optional[bool] = Field(None, description="Whether comments require approval")
    allow_guest_comments: Optional[bool] = Field(None, description="Whether guests can comment")
    seo_title: Optional[str] = Field(None, max_length=60, description="SEO title")
    seo_description: Optional[str] = Field(None, max_length=160, description="SEO description")
    google_analytics_id: Optional[str] = Field(None, description="Google Analytics ID")


class CreateBlogPostRequest(BaseModel):
    """Request model for creating a new blog post."""

    title: str = Field(..., min_length=1, max_length=200, description="Post title")
    content: str = Field(..., min_length=10, description="Post content (MDX)")
    excerpt: Optional[str] = Field(None, max_length=500, description="Post excerpt")
    featured_image: Optional[str] = Field(None, description="Featured image URL")
    categories: List[str] = Field(default_factory=list, max_items=5, description="Category slugs")
    tags: List[str] = Field(default_factory=list, max_items=10, description="Post tags")
    status: BlogPostStatus = Field(default=BlogPostStatus.DRAFT, description="Post status")
    scheduled_publish_at: Optional[datetime] = Field(None, description="Scheduled publish time")
    seo_title: Optional[str] = Field(None, max_length=60, description="SEO title")
    seo_description: Optional[str] = Field(None, max_length=160, description="SEO description")
    seo_keywords: List[str] = Field(default_factory=list, max_items=10, description="SEO keywords")
    social_image: Optional[str] = Field(None, description="Social media preview image URL")
    is_featured: bool = Field(default=False, description="Whether post is featured")
    is_pinned: bool = Field(default=False, description="Whether post is pinned")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        import bleach
        # Remove any HTML tags and strip whitespace
        return bleach.clean(v, tags=[], strip=True).strip()

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        import bleach
        # Allow specific HTML tags for MDX content
        allowed_tags = ['p', 'br', 'strong', 'em', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                       'ul', 'ol', 'li', 'blockquote', 'a', 'img', 'hr', 'table', 'thead', 'tbody',
                       'tr', 'th', 'td']
        return bleach.clean(v, tags=allowed_tags, strip=True)


class UpdateBlogPostRequest(BaseModel):
    """Request model for updating a blog post."""

    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Post title")
    content: Optional[str] = Field(None, min_length=10, description="Post content (MDX)")
    excerpt: Optional[str] = Field(None, max_length=500, description="Post excerpt")
    featured_image: Optional[str] = Field(None, description="Featured image URL")
    categories: Optional[List[str]] = Field(None, max_items=5, description="Category slugs")
    tags: Optional[List[str]] = Field(None, max_items=10, description="Post tags")
    status: Optional[BlogPostStatus] = Field(None, description="Post status")
    scheduled_publish_at: Optional[datetime] = Field(None, description="Scheduled publish time")
    seo_title: Optional[str] = Field(None, max_length=60, description="SEO title")
    seo_description: Optional[str] = Field(None, max_length=160, description="SEO description")
    seo_keywords: Optional[List[str]] = Field(None, max_items=10, description="SEO keywords")
    social_image: Optional[str] = Field(None, description="Social media preview image URL")
    is_featured: Optional[bool] = Field(None, description="Whether post is featured")
    is_pinned: Optional[bool] = Field(None, description="Whether post is pinned")


class CreateBlogCategoryRequest(BaseModel):
    """Request model for creating a blog category."""

    name: str = Field(..., min_length=1, max_length=50, description="Category name")
    slug: str = Field(..., min_length=1, max_length=50, description="Category slug")
    description: Optional[str] = Field(None, max_length=200, description="Category description")
    parent_id: Optional[str] = Field(None, description="Parent category ID")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        v = v.lower().strip()
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Slug can only contain letters, numbers, hyphens, and underscores")
        if v.startswith(("-", "_")) or v.endswith(("-", "_")):
            raise ValueError("Slug cannot start or end with hyphens or underscores")
        return v


class UpdateBlogCategoryRequest(BaseModel):
    """Request model for updating a blog category."""

    name: Optional[str] = Field(None, min_length=1, max_length=50, description="Category name")
    description: Optional[str] = Field(None, max_length=200, description="Category description")
    parent_id: Optional[str] = Field(None, description="Parent category ID")


class CreateBlogCommentRequest(BaseModel):
    """Request model for creating a blog comment."""

    content: str = Field(..., min_length=1, max_length=2000, description="Comment content")
    parent_id: Optional[str] = Field(None, description="Parent comment ID for nested comments")
    author_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Author name (for guests)")
    author_email: Optional[EmailStr] = Field(None, description="Author email (for guests)")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        import bleach
        # Allow basic HTML tags for comments
        allowed_tags = ['p', 'br', 'strong', 'em', 'code', 'a']
        return bleach.clean(v, tags=allowed_tags, strip=True).strip()


class UpdateBlogCommentRequest(BaseModel):
    """Request model for updating a blog comment."""

    content: str = Field(..., min_length=1, max_length=2000, description="Comment content")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        import bleach
        # Allow basic HTML tags for comments
        allowed_tags = ['p', 'br', 'strong', 'em', 'code', 'a']
        return bleach.clean(v, tags=allowed_tags, strip=True).strip()


class InviteWebsiteMemberRequest(BaseModel):
    """Request model for inviting a website member."""

    email: EmailStr = Field(..., description="Email address of the user to invite")
    role: WebsiteRole = Field(WebsiteRole.VIEWER, description="Role to assign to the member")


class UpdateWebsiteMemberRequest(BaseModel):
    """Request model for updating a website member."""

    role: WebsiteRole = Field(..., description="New role for the member")


class PublishBlogPostRequest(BaseModel):
    """Request model for publishing a blog post."""

    scheduled_publish_at: Optional[datetime] = Field(None, description="Optional scheduled publish time")


class ModerateCommentRequest(BaseModel):
    """Request model for moderating a comment."""

    action: str = Field(..., description="Action to take: 'approve', 'reject', or 'spam'")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for moderation action")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v):
        valid_actions = ["approve", "reject", "spam"]
        if v not in valid_actions:
            raise ValueError(f"Action must be one of: {', '.join(valid_actions)}")
        return v


class AutoSavePostRequest(BaseModel):
    """Request model for auto-saving a post draft."""

    content: str = Field(..., min_length=1, description="Post content to auto-save")
    title: Optional[str] = Field(None, description="Post title")


class RestoreVersionRequest(BaseModel):
    """Request model for restoring a post version."""

    version_id: str = Field(..., description="Version ID to restore")


class NewsletterSubscribeRequest(BaseModel):
    """Request model for newsletter subscription."""

    email: EmailStr = Field(..., description="Email address for newsletter")
    name: Optional[str] = Field(None, max_length=100, description="Subscriber name")


class TrackAnalyticsRequest(BaseModel):
    """Request model for tracking analytics events."""

    event_type: str = Field(..., description="Type of event: 'view', 'like', 'share', 'bookmark'")
    post_id: Optional[str] = Field(None, description="Post ID if applicable")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    device_type: Optional[str] = Field(None, description="Device type: 'desktop', 'mobile', 'tablet'")

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v):
        valid_types = ["view", "like", "share", "bookmark"]
        if v not in valid_types:
            raise ValueError(f"Event type must be one of: {', '.join(valid_types)}")
        return v


# Response Models
class BlogWebsiteResponse(BaseModel):
    """Response model for blog website information."""

    website_id: str
    name: str
    slug: str
    description: Optional[str]
    owner_id: str
    is_active: bool
    is_public: bool
    allow_comments: bool
    require_comment_approval: bool
    allow_guest_comments: bool
    seo_title: Optional[str]
    seo_description: Optional[str]
    google_analytics_id: Optional[str]
    post_count: int
    total_views: int
    monthly_views: int
    created_at: datetime
    updated_at: datetime
    last_post_at: Optional[datetime]
    user_role: Optional[str] = None  # Current user's role in this website


class BlogPostResponse(BaseModel):
    """Response model for blog post information."""

    post_id: str
    website_id: str
    title: str
    slug: str
    excerpt: str
    featured_image: Optional[str]
    author_id: str
    author_name: str
    status: str
    published_at: Optional[datetime]
    updated_at: datetime
    categories: List[Dict[str, Any]]
    tags: List[str]
    seo_title: Optional[str]
    seo_description: Optional[str]
    seo_keywords: List[str]
    social_image: Optional[str]
    reading_time: int
    word_count: int
    view_count: int
    like_count: int
    comment_count: int
    is_featured: bool
    is_pinned: bool
    scheduled_publish_at: Optional[datetime]
    versions: List[BlogVersion] = []


class BlogCategoryResponse(BaseModel):
    """Response model for blog category information."""

    category_id: str
    website_id: str
    name: str
    slug: str
    description: Optional[str]
    parent_id: Optional[str]
    post_count: int
    created_at: datetime
    updated_at: datetime


class BlogCommentResponse(BaseModel):
    """Response model for blog comment information."""

    comment_id: str
    website_id: str
    post_id: str
    author_id: Optional[str]
    author_name: str
    author_email: str
    content: str
    parent_id: Optional[str]
    status: str
    is_approved: bool
    likes: int
    created_at: datetime
    updated_at: datetime
    replies: List["BlogCommentResponse"] = []


class WebsiteMemberResponse(BaseModel):
    """Response model for website member information."""

    user_id: str
    username: str
    email: str
    role: str
    joined_at: datetime
    is_active: bool


class BlogAnalyticsResponse(BaseModel):
    """Response model for blog analytics."""

    total_posts: int
    total_views: int
    total_comments: int
    total_likes: int
    posts_by_status: Dict[str, int]
    views_by_period: List[Dict[str, Any]]
    top_posts: List[Dict[str, Any]]
    popular_categories: List[Dict[str, Any]]
    popular_tags: List[str]


class BlogSearchResponse(BaseModel):
    """Response model for blog search results."""

    query: str
    total_results: int
    posts: List[BlogPostResponse]
    categories: List[BlogCategoryResponse]
    pagination: Dict[str, Any]


class BlogFeedResponse(BaseModel):
    """Response model for blog RSS/Atom feeds."""

    title: str
    description: str
    link: str
    language: str
    last_build_date: datetime
    items: List[Dict[str, Any]]


class NewsletterSubscriberResponse(BaseModel):
    """Response model for newsletter subscriber."""

    subscriber_id: str
    website_id: str
    email: str
    name: Optional[str]
    is_active: bool
    subscribed_at: datetime


class EngagementMetricsResponse(BaseModel):
    """Response model for reader engagement metrics."""

    post_id: str
    views: int
    unique_views: int
    avg_time_on_page: float
    bounce_rate: float
    shares: Dict[str, int]
    bookmarks: int
    comments: int
    likes: int


# Pagination Models
class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int
    limit: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedBlogPostsResponse(BaseModel):
    """Paginated response for blog posts."""

    posts: List[BlogPostResponse]
    pagination: PaginationMeta
    meta: Dict[str, Any] = {}


class PaginatedBlogCommentsResponse(BaseModel):
    """Paginated response for blog comments."""

    comments: List[BlogCommentResponse]
    pagination: PaginationMeta


class PaginatedWebsitesResponse(BaseModel):
    """Paginated response for websites."""

    websites: List[BlogWebsiteResponse]
    pagination: PaginationMeta


# Database Schema Models (for internal use)
class BlogWebsiteDocument(BaseModel):
    """Database document model for blog_websites collection."""

    website_id: str
    name: str
    slug: str
    description: Optional[str]
    owner_id: str
    is_active: bool = True
    is_public: bool = True
    allow_comments: bool = True
    require_comment_approval: bool = True
    allow_guest_comments: bool = True
    seo_title: Optional[str]
    seo_description: Optional[str]
    google_analytics_id: Optional[str]
    post_count: int = 0
    total_views: int = 0
    monthly_views: int = 0
    created_at: datetime
    updated_at: datetime
    last_post_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "website_id": "website_abc123def456",
                "name": "Tech Blog",
                "slug": "tech-blog",
                "description": "A blog about technology and programming",
                "owner_id": "user_123",
                "is_active": True,
                "is_public": True,
                "allow_comments": True,
                "require_comment_approval": True,
                "allow_guest_comments": True,
                "seo_title": "Tech Blog - Latest in Technology",
                "seo_description": "Stay updated with the latest technology trends and programming tutorials",
                "google_analytics_id": "GA-XXXXXXXXX",
                "post_count": 25,
                "total_views": 15420,
                "monthly_views": 1250,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "last_post_at": "2024-01-15T10:30:00Z"
            }
        }


class BlogPostDocument(BaseModel):
    """Database document model for blog_posts collection."""

    post_id: str
    website_id: str
    title: str
    slug: str
    content: str
    excerpt: str
    featured_image: Optional[str]
    author_id: str
    status: str
    published_at: Optional[datetime]
    updated_at: datetime
    categories: List[str] = []
    tags: List[str] = []
    seo_title: Optional[str]
    seo_description: Optional[str]
    seo_keywords: List[str] = []
    social_image: Optional[str] = None
    reading_time: int = 0
    word_count: int = 0
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    is_featured: bool = False
    is_pinned: bool = False
    scheduled_publish_at: Optional[datetime] = None
    auto_save_content: Optional[str] = None
    auto_save_at: Optional[datetime] = None
    revision_history: List[BlogVersion] = []

    class Config:
        json_schema_extra = {
            "example": {
                "post_id": "post_abc123def456",
                "website_id": "website_abc123def456",
                "title": "Getting Started with FastAPI",
                "slug": "getting-started-with-fastapi",
                "content": "# Introduction\n\nFastAPI is a modern web framework...",
                "excerpt": "Learn how to build APIs with FastAPI from scratch",
                "featured_image": "https://example.com/image.jpg",
                "author_id": "user_123",
                "status": "published",
                "published_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "categories": ["technology", "python"],
                "tags": ["fastapi", "api", "python"],
                "seo_title": "Getting Started with FastAPI - Complete Guide",
                "seo_description": "Learn FastAPI from scratch with this comprehensive guide",
                "seo_keywords": ["fastapi", "python", "api", "tutorial"],
                "reading_time": 5,
                "word_count": 1200,
                "view_count": 1250,
                "like_count": 23,
                "comment_count": 5,
                "is_featured": False,
                "is_pinned": False,
                "scheduled_publish_at": None,
                "revision_history": []
            }
        }


class BlogCategoryDocument(BaseModel):
    """Database document model for blog_categories collection."""

    category_id: str
    website_id: str
    name: str
    slug: str
    description: Optional[str]
    parent_id: Optional[str]
    post_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "category_id": "category_abc123def456",
                "website_id": "website_abc123def456",
                "name": "Technology",
                "slug": "technology",
                "description": "Posts about technology and programming",
                "parent_id": None,
                "post_count": 15,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }


class BlogCommentDocument(BaseModel):
    """Database document model for blog_comments collection."""

    comment_id: str
    website_id: str
    post_id: str
    author_id: Optional[str]
    author_name: str
    author_email: str
    content: str
    parent_id: Optional[str]
    status: str = "pending"
    is_approved: bool = False
    moderated_by: Optional[str] = None
    moderated_at: Optional[datetime] = None
    likes: int = 0
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "comment_id": "comment_abc123def456",
                "website_id": "website_abc123def456",
                "post_id": "post_abc123def456",
                "author_id": "user_456",
                "author_name": "John Doe",
                "author_email": "john@example.com",
                "content": "Great article! Very helpful.",
                "parent_id": None,
                "status": "approved",
                "is_approved": True,
                "moderated_by": "user_123",
                "moderated_at": "2024-01-16T09:15:00Z",
                "likes": 3,
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0...",
                "created_at": "2024-01-16T08:30:00Z",
                "updated_at": "2024-01-16T08:30:00Z"
            }
        }


class BlogWebsiteMemberDocument(BaseModel):
    """Database document model for blog_website_members collection."""

    member_id: str
    website_id: str
    user_id: str
    role: str
    invited_by: str
    invited_at: datetime
    joined_at: Optional[datetime]
    is_active: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "member_id": "member_abc123def456",
                "website_id": "website_abc123def456",
                "user_id": "user_456",
                "role": "editor",
                "invited_by": "user_123",
                "invited_at": "2024-01-01T00:00:00Z",
                "joined_at": "2024-01-01T12:00:00Z",
                "is_active": True
            }
        }


class BlogAnalyticsDocument(BaseModel):
    """Database document model for blog_analytics collection."""

    analytics_id: str
    website_id: str
    post_id: Optional[str]
    date: datetime
    views: int = 0
    unique_views: int = 0
    likes: int = 0
    comments: int = 0
    shares: Dict[str, int] = {}
    referrer_sources: Dict[str, int] = {}
    device_types: Dict[str, int] = {}
    countries: Dict[str, int] = {}
    top_pages: List[str] = []


class NewsletterSubscriberDocument(BaseModel):
    """Database document model for blog_newsletter_subscribers collection."""

    subscriber_id: str
    website_id: str
    email: str
    name: Optional[str]
    is_active: bool = True
    subscribed_at: datetime
    unsubscribed_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "analytics_id": "analytics_abc123def456",
                "website_id": "website_abc123def456",
                "post_id": "post_abc123def456",
                "date": "2024-01-15T00:00:00Z",
                "views": 1250,
                "unique_views": 980,
                "likes": 23,
                "comments": 5,
                "shares": {"twitter": 5, "facebook": 3, "linkedin": 2},
                "referrer_sources": {"google": 450, "direct": 320, "social": 180},
                "device_types": {"desktop": 600, "mobile": 580, "tablet": 70},
                "countries": {"US": 450, "UK": 120, "DE": 80},
                "top_pages": ["/posts/getting-started", "/posts/advanced-topics"]
            }
        }


# Error Response Models
class BlogErrorResponse(BaseModel):
    """Error response model for blog operations."""

    error: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "WEBSITE_NOT_FOUND",
                    "message": "The requested website was not found",
                    "details": {"website_id": "website_abc123def456"},
                    "suggestions": ["Check the website ID", "Verify the website exists"]
                }
            }
        }


class BlogValidationErrorResponse(BaseModel):
    """Validation error response model for blog operations."""

    detail: List[Dict[str, Any]]

    class Config:
        json_schema_extra = {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "title"],
                        "msg": "Title is required and cannot be empty",
                        "type": "value_error"
                    }
                ]
            }
        }