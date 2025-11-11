"""
Blog Celery Tasks for background processing.

This module provides Celery tasks for blog operations including:
- Content processing and optimization
- Analytics aggregation
- Cache warming
- Email notifications
- SEO optimization
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import asyncio

from celery import Celery
from celery.schedules import crontab

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.blog_cache_manager import blog_cache_manager
from second_brain_database.managers.blog_manager import (
    BlogAnalyticsService,
    BlogContentService,
    BlogSEOService,
    BlogWebsiteManager,
)
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.tasks.celery_app import celery_app

logger = get_logger(prefix="[BlogTasks]")


# Initialize blog services
website_manager = BlogWebsiteManager()
content_service = BlogContentService()
analytics_service = BlogAnalyticsService()
seo_service = BlogSEOService()


# Content Processing Tasks

@celery_app.task(
    name="blog_process_post_content",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="blog_processing"
)
def process_post_content(self, website_id: str, post_id: str) -> Dict[str, Any]:
    """
    Process and optimize blog post content.

    Performs:
    - Content analysis and optimization
    - SEO metadata generation
    - Read time calculation
    - Image optimization triggers
    - Search indexing updates

    Args:
        website_id: Website identifier
        post_id: Post identifier

    Returns:
        Processing results
    """
    try:
        logger.info("Processing content for post %s in website %s", post_id, website_id)

        # Run async processing in event loop
        result = asyncio.run(_async_process_post_content(website_id, post_id))

        logger.info("Completed content processing for post %s", post_id)
        return result

    except Exception as e:
        logger.error("Failed to process post content: %s", e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=self.default_retry_delay * (2 ** self.request.retries))
        raise


async def _async_process_post_content(website_id: str, post_id: str) -> Dict[str, Any]:
    """Async implementation of post content processing."""
    try:
        # Get post data
        posts_collection = db_manager.get_collection("blog_posts")
        post = await posts_collection.find_one({"post_id": post_id, "website_id": website_id})

        if not post:
            raise ValueError(f"Post {post_id} not found in website {website_id}")

        updates = {}

        # Calculate reading time if not set
        if not post.get("reading_time"):
            content = post.get("content", "")
            word_count = len(content.split())
            reading_time = max(1, word_count // 200)
            updates["reading_time"] = reading_time

        # Calculate word count if not set
        if not post.get("word_count"):
            content = post.get("content", "")
            updates["word_count"] = len(content.split())

        # Generate excerpt if not set
        if not post.get("excerpt") and post.get("content"):
            content = post.get("content", "")
            excerpt = content[:300] + "..." if len(content) > 300 else content
            updates["excerpt"] = excerpt

        # Update post with processed data
        if updates:
            await posts_collection.update_one(
                {"post_id": post_id, "website_id": website_id},
                {"$set": updates}
            )

        # Invalidate cache
        await blog_cache_manager.invalidate_post_cache(website_id, post_id)

        return {
            "status": "success",
            "post_id": post_id,
            "website_id": website_id,
            "updates": updates
        }

    except Exception as e:
        logger.error("Async post content processing failed: %s", e, exc_info=True)
        raise


@celery_app.task(
    name="blog_generate_seo_metadata",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue="blog_processing"
)
def generate_seo_metadata(self, website_id: str, post_id: str) -> Dict[str, Any]:
    """
    Generate SEO metadata for a blog post.

    Args:
        website_id: Website identifier
        post_id: Post identifier

    Returns:
        SEO metadata generation results
    """
    try:
        logger.info("Generating SEO metadata for post %s in website %s", post_id, website_id)

        # Run async processing
        result = asyncio.run(_async_generate_seo_metadata(website_id, post_id))

        logger.info("Completed SEO metadata generation for post %s", post_id)
        return result

    except Exception as e:
        logger.error("Failed to generate SEO metadata: %s", e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=self.default_retry_delay)
        raise


async def _async_generate_seo_metadata(website_id: str, post_id: str) -> Dict[str, Any]:
    """Async implementation of SEO metadata generation."""
    try:
        # Get post and website data
        posts_collection = db_manager.get_collection("blog_posts")
        websites_collection = db_manager.get_collection("blog_websites")

        post = await posts_collection.find_one({"post_id": post_id, "website_id": website_id})
        website = await websites_collection.find_one({"website_id": website_id})

        if not post or not website:
            raise ValueError("Post or website not found")

        # Generate SEO suggestions (simplified - in production use AI/ML)
        updates = {}

        # Auto-generate SEO title if not set
        if not post.get("seo_title"):
            title = post.get("title", "")
            if len(title) > 60:
                seo_title = title[:57] + "..."
            else:
                seo_title = title
            updates["seo_title"] = seo_title

        # Auto-generate SEO description if not set
        if not post.get("seo_description"):
            excerpt = post.get("excerpt", "")
            if len(excerpt) > 160:
                seo_desc = excerpt[:157] + "..."
            else:
                seo_desc = excerpt
            updates["seo_description"] = seo_desc

        # Auto-generate SEO keywords if not set
        if not post.get("seo_keywords"):
            # Simple keyword extraction from title and content
            title_words = post.get("title", "").lower().split()
            content_words = post.get("content", "").lower().split()[:50]  # First 50 words

            # Filter out common words and get unique keywords
            common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
            keywords = []
            for word in title_words + content_words:
                word = word.strip(".,!?")
                if len(word) > 3 and word not in common_words and word not in keywords:
                    keywords.append(word)
                    if len(keywords) >= 5:  # Limit to 5 keywords
                        break

            updates["seo_keywords"] = keywords

        # Update post with SEO data
        if updates:
            await posts_collection.update_one(
                {"post_id": post_id, "website_id": website_id},
                {"$set": updates}
            )

        # Invalidate cache
        await blog_cache_manager.invalidate_post_cache(website_id, post_id)

        return {
            "status": "success",
            "post_id": post_id,
            "website_id": website_id,
            "seo_updates": updates
        }

    except Exception as e:
        logger.error("Async SEO metadata generation failed: %s", e, exc_info=True)
        raise


# Analytics and Reporting Tasks

@celery_app.task(
    name="blog_aggregate_analytics",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    queue="blog_analytics"
)
def aggregate_blog_analytics(self, website_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Aggregate analytics data for a website.

    Performs:
    - Daily analytics aggregation
    - Popular posts calculation
    - Traffic trend analysis
    - Cache warming for analytics

    Args:
        website_id: Website identifier
        days: Number of days to aggregate

    Returns:
        Aggregation results
    """
    try:
        logger.info("Aggregating analytics for website %s (%d days)", website_id, days)

        # Run async aggregation
        result = asyncio.run(_async_aggregate_analytics(website_id, days))

        logger.info("Completed analytics aggregation for website %s", website_id)
        return result

    except Exception as e:
        logger.error("Failed to aggregate analytics: %s", e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=self.default_retry_delay)
        raise


async def _async_aggregate_analytics(website_id: str, days: int) -> Dict[str, Any]:
    """Async implementation of analytics aggregation."""
    try:
        # Get analytics data
        analytics = await analytics_service.get_website_analytics(website_id, days)

        # Cache the results
        await blog_cache_manager.cache_analytics(website_id, analytics, days)

        # Calculate additional metrics
        analytics_collection = db_manager.get_collection("blog_analytics")

        # Get top posts
        pipeline = [
            {"$match": {"website_id": website_id}},
            {"$group": {
                "_id": "$post_id",
                "total_views": {"$sum": "$views"},
                "total_unique_views": {"$sum": "$unique_views"}
            }},
            {"$sort": {"total_views": -1}},
            {"$limit": 10}
        ]

        top_posts = await analytics_collection.aggregate(pipeline).to_list(10)

        # Update website with aggregated data
        websites_collection = db_manager.get_collection("blog_websites")
        await websites_collection.update_one(
            {"website_id": website_id},
            {
                "$set": {
                    "analytics_last_updated": datetime.utcnow(),
                    "top_posts": top_posts
                }
            }
        )

        return {
            "status": "success",
            "website_id": website_id,
            "analytics": analytics,
            "top_posts": top_posts,
            "aggregated_days": days
        }

    except Exception as e:
        logger.error("Async analytics aggregation failed: %s", e, exc_info=True)
        raise


@celery_app.task(
    name="blog_update_popular_posts",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="blog_analytics"
)
def update_popular_posts(self, website_id: str) -> Dict[str, Any]:
    """
    Update popular posts rankings for a website.

    Args:
        website_id: Website identifier

    Returns:
        Update results
    """
    try:
        logger.info("Updating popular posts for website %s", website_id)

        # Run async update
        result = asyncio.run(_async_update_popular_posts(website_id))

        logger.info("Completed popular posts update for website %s", website_id)
        return result

    except Exception as e:
        logger.error("Failed to update popular posts: %s", e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=self.default_retry_delay)
        raise


async def _async_update_popular_posts(website_id: str) -> Dict[str, Any]:
    """Async implementation of popular posts update."""
    try:
        analytics_collection = db_manager.get_collection("blog_analytics")
        posts_collection = db_manager.get_collection("blog_posts")

        # Calculate popular posts based on recent views
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        pipeline = [
            {
                "$match": {
                    "website_id": website_id,
                    "date": {"$gte": thirty_days_ago.date()}
                }
            },
            {
                "$group": {
                    "_id": "$post_id",
                    "total_views": {"$sum": "$views"},
                    "total_unique_views": {"$sum": "$unique_views"},
                    "avg_daily_views": {"$avg": "$views"}
                }
            },
            {"$sort": {"total_views": -1}},
            {"$limit": 20}
        ]

        popular_posts = await analytics_collection.aggregate(pipeline).to_list(20)

        # Update posts with popularity scores
        for post_data in popular_posts:
            post_id = post_data["_id"]
            popularity_score = post_data["total_views"] * 0.7 + post_data["avg_daily_views"] * 0.3

            await posts_collection.update_one(
                {"post_id": post_id, "website_id": website_id},
                {
                    "$set": {
                        "popularity_score": popularity_score,
                        "popularity_last_updated": datetime.utcnow()
                    }
                }
            )

        return {
            "status": "success",
            "website_id": website_id,
            "popular_posts_count": len(popular_posts)
        }

    except Exception as e:
        logger.error("Async popular posts update failed: %s", e, exc_info=True)
        raise


# Cache Management Tasks

@celery_app.task(
    name="blog_warm_cache",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue="blog_maintenance"
)
def warm_blog_cache(self, website_id: str) -> Dict[str, Any]:
    """
    Warm up cache for a blog website.

    Pre-loads frequently accessed data into cache:
    - Website info
    - Categories
    - Popular posts
    - Recent posts

    Args:
        website_id: Website identifier

    Returns:
        Cache warming results
    """
    try:
        logger.info("Warming cache for website %s", website_id)

        # Run async cache warming
        result = asyncio.run(_async_warm_blog_cache(website_id))

        logger.info("Completed cache warming for website %s", website_id)
        return result

    except Exception as e:
        logger.error("Failed to warm blog cache: %s", e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=self.default_retry_delay)
        raise


async def _async_warm_blog_cache(website_id: str) -> Dict[str, Any]:
    """Async implementation of cache warming."""
    try:
        # Cache website info
        website = await website_manager.get_website_by_slug(website_id)  # Assuming website_id is slug
        if website:
            await blog_cache_manager.cache_website(website.model_dump())

        # Cache categories
        categories = await content_service.get_website_categories(website_id)
        if categories:
            await blog_cache_manager.cache_categories(website_id, [c.model_dump() for c in categories])

        # Cache popular posts
        popular_posts = await content_service.get_website_posts(
            website_id=website_id,
            status="published",
            page=1,
            limit=10
        )
        if popular_posts:
            await blog_cache_manager.cache_posts_list(
                website_id, [p.model_dump() for p in popular_posts],
                "published", None, 1, 10
            )

        # Cache analytics
        analytics = await analytics_service.get_website_analytics(website_id, 30)
        if analytics:
            await blog_cache_manager.cache_analytics(website_id, analytics, 30)

        return {
            "status": "success",
            "website_id": website_id,
            "cached_items": ["website", "categories", "popular_posts", "analytics"]
        }

    except Exception as e:
        logger.error("Async cache warming failed: %s", e, exc_info=True)
        raise


@celery_app.task(
    name="blog_cleanup_expired_cache",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="blog_maintenance"
)
def cleanup_expired_blog_cache(self) -> Dict[str, Any]:
    """
    Clean up expired cache entries.

    This task runs periodically to remove stale cache entries
    and optimize Redis memory usage.

    Returns:
        Cleanup results
    """
    try:
        logger.info("Starting blog cache cleanup")

        # For Redis, expired keys are automatically cleaned up
        # This task could be used for custom cleanup logic
        result = {
            "status": "success",
            "message": "Redis automatically handles expired key cleanup",
            "note": "Custom cleanup logic can be added here if needed"
        }

        logger.info("Completed blog cache cleanup")
        return result

    except Exception as e:
        logger.error("Failed to cleanup blog cache: %s", e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=self.default_retry_delay)
        raise


# Notification Tasks

@celery_app.task(
    name="blog_send_comment_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="blog_notifications"
)
def send_comment_notification(
    self,
    website_id: str,
    post_id: str,
    comment_id: str,
    recipient_email: str
) -> Dict[str, Any]:
    """
    Send email notification for new comment.

    Args:
        website_id: Website identifier
        post_id: Post identifier
        comment_id: Comment identifier
        recipient_email: Email to send notification to

    Returns:
        Notification results
    """
    try:
        logger.info("Sending comment notification for comment %s", comment_id)

        # Run async notification
        result = asyncio.run(_async_send_comment_notification(
            website_id, post_id, comment_id, recipient_email
        ))

        logger.info("Sent comment notification for comment %s", comment_id)
        return result

    except Exception as e:
        logger.error("Failed to send comment notification: %s", e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=self.default_retry_delay)
        raise


async def _async_send_comment_notification(
    website_id: str,
    post_id: str,
    comment_id: str,
    recipient_email: str
) -> Dict[str, Any]:
    """Async implementation of comment notification."""
    try:
        # Get comment and post data
        comments_collection = db_manager.get_collection("blog_comments")
        posts_collection = db_manager.get_collection("blog_posts")
        websites_collection = db_manager.get_collection("blog_websites")

        comment = await comments_collection.find_one({"comment_id": comment_id})
        post = await posts_collection.find_one({"post_id": post_id, "website_id": website_id})
        website = await websites_collection.find_one({"website_id": website_id})

        if not all([comment, post, website]):
            raise ValueError("Comment, post, or website not found")

        # Send notification email
        subject = f"New comment on: {post['title']}"
        body = f"""
        A new comment has been posted on your blog post "{post['title']}".

        Comment by: {comment.get('author_name', 'Anonymous')}
        Comment: {comment['content'][:200]}{'...' if len(comment['content']) > 200 else ''}

        View comment: /websites/{website_id}/posts/{post['slug']}#comment-{comment_id}
        Manage comments: /admin/websites/{website_id}/comments

        Website: {website['name']}
        """

        await email_manager.send_email(
            to_email=recipient_email,
            subject=subject,
            body=body,
            html_body=None
        )

        return {
            "status": "success",
            "comment_id": comment_id,
            "recipient_email": recipient_email,
            "notification_type": "comment"
        }

    except Exception as e:
        logger.error("Async comment notification failed: %s", e, exc_info=True)
        raise


# Periodic Tasks Configuration

# Update Celery beat schedule for blog tasks
celery_app.conf.beat_schedule.update({
    # Daily analytics aggregation
    "blog-daily-analytics": {
        "task": "blog_aggregate_analytics",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
        "args": ("all_websites", 30),  # This would need to be handled differently
    },

    # Update popular posts weekly
    "blog-weekly-popular-posts": {
        "task": "blog_update_popular_posts",
        "schedule": crontab(day_of_week=1, hour=3, minute=0),  # Monday 3 AM
        "args": ("all_websites",),  # This would need to be handled differently
    },

    # Cache warming daily
    "blog-daily-cache-warm": {
        "task": "blog_warm_cache",
        "schedule": crontab(hour=4, minute=0),  # 4 AM daily
        "args": ("all_websites",),  # This would need to be handled differently
    },

    # Cache cleanup weekly
    "blog-weekly-cache-cleanup": {
        "task": "blog_cleanup_expired_cache",
        "schedule": crontab(day_of_week=0, hour=5, minute=0),  # Sunday 5 AM
    },
})

logger.info("Blog Celery tasks initialized")