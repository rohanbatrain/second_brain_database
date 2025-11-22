"""
Blog API routes for multi-tenant blog operations.

This module provides RESTful API endpoints for blog websites, posts, categories,
comments, and analytics with website-level isolation and role-based access control.
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from second_brain_database.managers.blog_auth_manager import (
    blog_auth_manager,
    require_website_admin,
    require_website_author,
    require_website_editor,
    require_website_owner,
    require_website_viewer,
)
from second_brain_database.managers.blog_manager import (
    BlogContentService,
    BlogWebsiteManager,
)
from second_brain_database.managers.blog_security import (
    blog_audit_logger,
    blog_xss_protection,
)
from second_brain_database.managers.logging_manager import get_logger


from second_brain_database.models.blog_models import (
    AutoSavePostRequest,
    CreateBlogCategoryRequest,
    BlogCategoryResponse,
    UpdateBlogCategoryRequest,
    CreateBlogCommentRequest,
    BlogCommentResponse,
    UpdateBlogCommentRequest,
    CreateBlogPostRequest,
    BlogPostResponse,
    UpdateBlogPostRequest,
    CreateBlogWebsiteRequest,
    BlogWebsiteResponse,
    UpdateBlogWebsiteRequest,
    WebsiteRole,
    RestoreVersionRequest,
    NewsletterSubscribeRequest,
    TrackAnalyticsRequest,
    NewsletterSubscriberResponse,
    EngagementMetricsResponse,
    BlogVersion,
)

logger = get_logger(prefix="[Blog Routes]")

# Initialize managers
website_manager = BlogWebsiteManager()
content_service = BlogContentService()

# Create router
router = APIRouter(prefix="/blog", tags=["blog"])


# Website Management Routes

@router.post("/websites", response_model=BlogWebsiteResponse)
async def create_website(
    request: BlogWebsiteCreateRequest,
    current_user: dict = Depends(require_website_viewer)  # Any authenticated user can create
):
    """Create a new blog website."""
    try:
        website = await website_manager.create_website(
            owner_id=current_user["_id"],
            name=request.name,
            slug=request.slug,
            description=request.description
        )

        logger.info("Created website: %s for user %s", website.website_id, current_user["username"])
        return BlogWebsiteResponse(**website.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create website: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create website")


@router.get("/websites", response_model=List[BlogWebsiteResponse])
async def get_user_websites(
    current_user: dict = Depends(require_website_viewer)
):
    """Get all websites accessible to the current user."""
    try:
        websites = await website_manager.get_user_websites(current_user["_id"])
        return [BlogWebsiteResponse(**w.model_dump()) for w in websites]

    except Exception as e:
        logger.error("Failed to get user websites: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get websites")


@router.get("/websites/{website_id}", response_model=BlogWebsiteResponse)
async def get_website(
    website_id: str,
    current_user: dict = Depends(require_website_viewer)
):
    """Get a specific website by ID."""
    try:
        # Check access
        membership = await website_manager.check_website_access(
            current_user["_id"], website_id, WebsiteRole.VIEWER
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")

        website = await website_manager.get_website_by_slug(website_id)  # website_id could be slug
        if not website:
            # Try as ID
            from second_brain_database.database import db_manager
            website_doc = await db_manager.get_tenant_collection("blog_websites").find_one({"website_id": website_id})
            if website_doc:
                website = BlogWebsiteResponse(**website_doc)

        if not website:
            raise HTTPException(status_code=404, detail="Website not found")

        return website

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get website: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get website")


# Website-scoped routes with {website_id} prefix

@router.put("/websites/{website_id}", response_model=BlogWebsiteResponse)
async def update_website(
    website_id: str,
    request: BlogWebsiteUpdateRequest,
    current_user: dict = Depends(require_website_admin)
):
    """Update website settings (admin only)."""
    try:
        # Check if user has admin access to this website
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        # Update website
        from second_brain_database.database import db_manager
        update_data = request.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        result = await db_manager.get_tenant_collection("blog_websites").update_one(
            {"website_id": website_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Website not found")

        # Get updated website
        website_doc = await db_manager.get_tenant_collection("blog_websites").find_one({"website_id": website_id})
        website = BlogWebsiteResponse(**website_doc)

        # Clear cache
        await website_manager._clear_website_cache(website_id)

        logger.info("Updated website: %s", website_id)
        return website

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update website: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update website")


# Post Management Routes

@router.post("/websites/{website_id}/posts", response_model=BlogPostResponse)
async def create_post(
    website_id: str,
    request: BlogPostCreateRequest,
    current_user: dict = Depends(require_website_author),
    req: Request = None
):
    """Create a new blog post."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        # Sanitize content for XSS protection
        sanitized_title = blog_xss_protection.sanitize_html(request.title, allow_html=False)
        sanitized_content = blog_xss_protection.sanitize_post_content(request.content)
        sanitized_excerpt = blog_xss_protection.sanitize_html(request.excerpt, allow_html=False) if request.excerpt else None

        # Validate URLs if provided
        if request.featured_image and not blog_xss_protection.validate_url(request.featured_image):
            raise HTTPException(status_code=400, detail="Invalid featured image URL")

        # Calculate reading time (average 200 words per minute)
        word_count = len(sanitized_content.split())
        reading_time = max(1, word_count // 200)

        post = await content_service.create_post(
            website_id=website_id,
            author_id=current_user["_id"],
            title=sanitized_title,
            content=sanitized_content,
            excerpt=sanitized_excerpt,
            featured_image=request.featured_image,
            categories=request.categories,
            tags=request.tags,
            seo_title=request.seo_title,
            seo_description=request.seo_description,
            seo_keywords=request.seo_keywords,
            status=request.status
        )

        # Create initial version
        initial_version = BlogVersion(
            version_id=f"version_{uuid4().hex[:16]}",
            post_id=post.post_id,
            title=sanitized_title,
            content=sanitized_content,
            excerpt=sanitized_excerpt,
            created_at=datetime.utcnow(),
            created_by=current_user["_id"],
            change_summary="Initial version",
        )

        # Update post with reading time and initial version
        from second_brain_database.database import db_manager
        await db_manager.get_tenant_collection("blog_posts").update_one(
            {"post_id": post.post_id},
            {
                "$set": {"reading_time": reading_time, "word_count": word_count},
                "$push": {"revision_history": initial_version.model_dump()},
            },
        )

        # Audit log
        client_ip = req.client.host if req.client else "unknown"
        await blog_audit_logger.log_content_event(
            event_type="post_created",
            user_id=current_user["_id"],
            website_id=website_id,
            content_type="post",
            content_id=post.post_id,
            action="create",
            ip_address=client_ip,
            details={"title": sanitized_title, "status": request.status}
        )

        logger.info("Created post: %s in website %s", post.post_id, website_id)
        return BlogPostResponse(**post.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create post: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create post")


@router.get("/websites/{website_id}/posts", response_model=List[BlogPostResponse])
async def get_website_posts(
    website_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    status: str = Query("published", regex="^(draft|published|archived)$"),
    category: Optional[str] = None,
    current_user: dict = Depends(require_website_viewer)
):
    """Get posts for a website with pagination."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        posts = await content_service.get_website_posts(
            website_id=website_id,
            page=page,
            limit=limit,
            status=status,
            category=category
        )

        return [BlogPostResponse(**p.model_dump()) for p in posts]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get website posts: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get posts")


@router.get("/websites/{website_id}/posts/{post_slug}", response_model=BlogPostResponse)
async def get_post(
    website_id: str,
    post_slug: str,
    current_user: dict = Depends(require_website_viewer)
):
    """Get a specific post by slug."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        post = await content_service.get_post_by_slug(website_id, post_slug)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        return BlogPostResponse(**post.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get post: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get post")


@router.put("/websites/{website_id}/posts/{post_id}", response_model=BlogPostResponse)
async def update_post(
    website_id: str,
    post_id: str,
    request: BlogPostUpdateRequest,
    current_user: dict = Depends(require_website_author),
    req: Request = None
):
    """Update a blog post."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        # Check if user can edit this post (owner or editor+)
        from second_brain_database.database import db_manager
        post_doc = await db_manager.get_tenant_collection("blog_posts").find_one({
            "post_id": post_id,
            "website_id": website_id
        })

        if not post_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        # Check permissions
        user_role = current_user.get("website_role")
        is_owner = post_doc["author_id"] == current_user["_id"]
        can_edit = (
            user_role in [WebsiteRole.OWNER, WebsiteRole.ADMIN, WebsiteRole.EDITOR] or
            (user_role == WebsiteRole.AUTHOR and is_owner)
        )

        if not can_edit:
            raise HTTPException(status_code=403, detail="Cannot edit this post")

        # Sanitize content for XSS protection
        update_data = request.model_dump(exclude_unset=True)
        if "title" in update_data:
            update_data["title"] = blog_xss_protection.sanitize_html(update_data["title"], allow_html=False)
        if "content" in update_data:
            update_data["content"] = blog_xss_protection.sanitize_post_content(update_data["content"])
        if "excerpt" in update_data and update_data["excerpt"]:
            update_data["excerpt"] = blog_xss_protection.sanitize_html(update_data["excerpt"], allow_html=False)

        # Validate URLs if provided
        if "featured_image" in update_data and update_data["featured_image"] and not blog_xss_protection.validate_url(update_data["featured_image"]):
            raise HTTPException(status_code=400, detail="Invalid featured image URL")

        # Save version if content changed
        version_update = {}
        if "content" in update_data or "title" in update_data:
            new_version = BlogVersion(
                version_id=f"version_{uuid4().hex[:16]}",
                post_id=post_id,
                title=post_doc["title"],
                content=post_doc["content"],
                excerpt=post_doc.get("excerpt"),
                created_at=datetime.utcnow(),
                created_by=current_user["_id"],
                change_summary=f"Update by {current_user.get('username', 'user')}",
            )
            version_update["$push"] = {"revision_history": new_version.model_dump()}

            # Recalculate reading time if content changed
            if "content" in update_data:
                word_count = len(update_data["content"].split())
                update_data["reading_time"] = max(1, word_count // 200)
                update_data["word_count"] = word_count

        # Update post
        update_data["updated_at"] = datetime.utcnow()

        update_operations = {"$set": update_data}
        if version_update:
            update_operations.update(version_update)

        result = await db_manager.get_tenant_collection("blog_posts").update_one(
            {"post_id": post_id, "website_id": website_id},
            update_operations
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Post not found")

        # Get updated post
        updated_post_doc = await db_manager.get_tenant_collection("blog_posts").find_one({
            "post_id": post_id, "website_id": website_id
        })
        post = BlogPostResponse(**updated_post_doc)

        # Audit log
        client_ip = req.client.host if req.client else "unknown"
        await blog_audit_logger.log_content_event(
            event_type="post_updated",
            user_id=current_user["_id"],
            website_id=website_id,
            content_type="post",
            content_id=post_id,
            action="update",
            ip_address=client_ip,
            details={"title": update_data.get("title"), "status": update_data.get("status")}
        )

        # Clear cache
        await content_service._clear_website_cache(website_id)

        logger.info("Updated post: %s", post_id)
        return post

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update post: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update post")


@router.delete("/websites/{website_id}/posts/{post_id}")
async def delete_post(
    website_id: str,
    post_id: str,
    current_user: dict = Depends(require_website_editor)
):
    """Delete a blog post (editor+ only)."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        from second_brain_database.database import db_manager

        # Check if post exists
        post_doc = await db_manager.get_tenant_collection("blog_posts").find_one({
            "post_id": post_id,
            "website_id": website_id
        })

        if not post_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        # Delete post
        result = await db_manager.get_tenant_collection("blog_posts").delete_one({
            "post_id": post_id,
            "website_id": website_id
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Post not found")

        # Update website post count
        await db_manager.get_tenant_collection("blog_websites").update_one(
            {"website_id": website_id},
            {"$inc": {"post_count": -1}}
        )

        # Clear cache
        await content_service._clear_website_cache(website_id)

        logger.info("Deleted post: %s from website %s", post_id, website_id)
        return {"message": "Post deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete post: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete post")


# Category Management Routes

@router.post("/websites/{website_id}/categories", response_model=BlogCategoryResponse)
async def create_category(
    website_id: str,
    request: CreateBlogCategoryRequest,
    current_user: dict = Depends(require_website_editor)
):
    """Create a new blog category (editor+ only)."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        from second_brain_database.database import db_manager
        from datetime import datetime

        # Check if slug is unique within website
        existing = await db_manager.get_tenant_collection("blog_categories").find_one({
            "website_id": website_id,
            "slug": request.slug
        })

        if existing:
            raise HTTPException(status_code=400, detail="Category slug already exists")

        category_doc = {
            "category_id": f"category_{uuid4().hex[:16]}",
            "website_id": website_id,
            "name": request.name,
            "slug": request.slug,
            "description": request.description,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        await db_manager.get_tenant_collection("blog_categories").insert_one(category_doc)

        # Clear cache
        await content_service._clear_website_cache(website_id)

        logger.info("Created category: %s in website %s", category_doc["category_id"], website_id)
        return BlogCategoryResponse(**category_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create category: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create category")


@router.get("/websites/{website_id}/categories", response_model=List[BlogCategoryResponse])
async def get_website_categories(
    website_id: str,
    current_user: dict = Depends(require_website_viewer)
):
    """Get all categories for a website."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        from second_brain_database.database import db_manager

        categories = []
        async for cat in db_manager.get_tenant_collection("blog_categories").find({"website_id": website_id}):
            categories.append(BlogCategoryResponse(**cat))

        return categories

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get website categories: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get categories")


# Comment Management Routes

@router.post("/websites/{website_id}/posts/{post_id}/comments", response_model=BlogCommentResponse)
async def create_comment(
    website_id: str,
    post_id: str,
    request: BlogCommentCreateRequest,
    current_user: dict = Depends(require_website_viewer),
    req: Request = None
):
    """Create a new comment on a post."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        from second_brain_database.database import db_manager
        from datetime import datetime

        # Check if post exists and allows comments
        post_doc = await db_manager.get_tenant_collection("blog_posts").find_one({
            "post_id": post_id,
            "website_id": website_id
        })

        if not post_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        # Check if website allows comments
        website_doc = await db_manager.get_tenant_collection("blog_websites").find_one({"website_id": website_id})
        if not website_doc or not website_doc.get("allow_comments", True):
            raise HTTPException(status_code=403, detail="Comments are disabled for this website")

        # Check approval requirement
        needs_approval = website_doc.get("require_comment_approval", True)
        is_author = post_doc["author_id"] == current_user["_id"]
        user_role = current_user.get("website_role")

        # Authors and editors can comment without approval
        status = "approved" if (
            not needs_approval or
            is_author or
            user_role in [WebsiteRole.OWNER, WebsiteRole.ADMIN, WebsiteRole.EDITOR]
        ) else "pending"

        # Sanitize comment content for XSS protection
        sanitized_content = blog_xss_protection.sanitize_comment_content(request.content)
        sanitized_author_name = blog_xss_protection.sanitize_html(request.author_name or current_user.get("username"), allow_html=False)

        comment_doc = {
            "comment_id": f"comment_{uuid4().hex[:16]}",
            "website_id": website_id,
            "post_id": post_id,
            "author_id": current_user["_id"],
            "author_name": sanitized_author_name,
            "author_email": request.author_email,
            "content": sanitized_content,
            "status": status,
            "parent_id": request.parent_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        await db_manager.get_tenant_collection("blog_comments").insert_one(comment_doc)

        # Update post comment count
        await db_manager.get_tenant_collection("blog_posts").update_one(
            {"post_id": post_id, "website_id": website_id},
            {"$inc": {"comment_count": 1}}
        )

        # Audit log
        client_ip = req.client.host if req.client else "unknown"
        await blog_audit_logger.log_content_event(
            event_type="comment_created",
            user_id=current_user["_id"],
            website_id=website_id,
            content_type="comment",
            content_id=comment_doc["comment_id"],
            action="create",
            ip_address=client_ip,
            details={"post_id": post_id, "status": status}
        )

        logger.info("Created comment: %s on post %s", comment_doc["comment_id"], post_id)
        return BlogCommentResponse(**comment_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create comment: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create comment")


@router.get("/websites/{website_id}/posts/{post_id}/comments", response_model=List[BlogCommentResponse])
async def get_post_comments(
    website_id: str,
    post_id: str,
    status: str = Query("approved", regex="^(pending|approved|spam|deleted)$"),
    current_user: dict = Depends(require_website_viewer)
):
    """Get comments for a post."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        from second_brain_database.database import db_manager

        # Check if user can see pending comments (editors+)
        user_role = current_user.get("website_role")
        can_see_pending = user_role in [WebsiteRole.OWNER, WebsiteRole.ADMIN, WebsiteRole.EDITOR]

        if status == "pending" and not can_see_pending:
            raise HTTPException(status_code=403, detail="Cannot view pending comments")

        query = {"website_id": website_id, "post_id": post_id}
        if not can_see_pending:
            query["status"] = "approved"

        comments = []
        async for comment in db_manager.get_tenant_collection("blog_comments").find(query).sort("created_at", 1):
            comments.append(BlogCommentResponse(**comment))

        return comments

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get post comments: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get comments")


# Authentication Routes for Blog

@router.post("/auth/websites/{website_id}/login")
async def login_to_website(
    website_id: str,
    current_user: dict = Depends(require_website_viewer)  # Any authenticated user
):
    """Login to a specific website and get website-scoped token."""
    try:
        # Check if user has access to this website
        membership = await website_manager.check_website_access(
            current_user["_id"], website_id, WebsiteRole.VIEWER
        )

        if not membership:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        # Create website token
        token = await blog_auth_manager.create_website_token(
            user_id=current_user["_id"],
            username=current_user["username"],
            website_id=website_id,
            role=membership.role
        )

        logger.info("User %s logged into website %s with role %s",
                   current_user["username"], website_id, membership.role.value)

        return {
            "access_token": token,
            "token_type": "bearer",
            "website_id": website_id,
            "role": membership.role.value
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to login to website: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to login to website")


# Analytics Routes (Admin only)

@router.get("/websites/{website_id}/analytics")
async def get_website_analytics(
    website_id: str,
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(require_website_admin)
):
    """Get analytics for a website (admin only)."""
    try:
        # Check website access
        if current_user.get("website_id") != website_id:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        from second_brain_database.managers.blog_manager import BlogAnalyticsService

        analytics_service = BlogAnalyticsService()
        analytics = await analytics_service.get_website_analytics(website_id, days)

        return analytics

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get website analytics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get analytics")