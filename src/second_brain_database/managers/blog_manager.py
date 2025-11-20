"""
Blog Manager for handling multi-tenant blog operations.

This module provides the BlogWebsiteManager, BlogContentService, BlogSEOService,
and BlogAnalyticsService classes for managing blog websites, posts, categories,
comments, and analytics with website-level data isolation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.models.blog_models import (
    BlogAnalyticsDocument,
    BlogCategoryDocument,
    BlogCommentDocument,
    BlogPostDocument,
    BlogWebsiteDocument,
    BlogWebsiteMemberDocument,
    WebsiteRole,
)

logger = get_logger(prefix="[BlogManager]")


class BlogWebsiteManager:
    """
    Manager for blog website operations with multi-tenant isolation.

    Handles website creation, configuration, member management, and
    website-level permissions.
    """

    def __init__(self, db_manager=None, redis_manager=None):
        self.db = db_manager or globals()["db_manager"]
        self.redis = redis_manager or globals()["redis_manager"]
        self.websites_collection = self.db.get_collection("blog_websites")
        self.members_collection = self.db.get_collection("blog_website_members")
        self.logger = logger

    async def create_website(
        self,
        owner_id: str,
        name: str,
        slug: str,
        description: Optional[str] = None
    ) -> BlogWebsiteDocument:
        """Create a new blog website."""
        try:
            # Validate slug uniqueness
            existing = await self.websites_collection.find_one({"slug": slug})
            if existing:
                raise ValueError(f"Website slug '{slug}' already exists")

            # Generate unique IDs
            website_id = f"website_{uuid.uuid4().hex[:16]}"

            # Create website document
            website_doc = BlogWebsiteDocument(
                website_id=website_id,
                name=name,
                slug=slug,
                description=description,
                owner_id=owner_id,
                is_active=True,
                is_public=True,
                allow_comments=True,
                require_comment_approval=True,
                allow_guest_comments=True,
                post_count=0,
                total_views=0,
                monthly_views=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            # Insert website
            await self.websites_collection.insert_one(website_doc.model_dump(by_alias=True))

            # Create owner membership
            member_doc = BlogWebsiteMemberDocument(
                member_id=f"member_{uuid.uuid4().hex[:16]}",
                website_id=website_id,
                user_id=owner_id,
                role=WebsiteRole.OWNER,
                invited_by=owner_id,
                invited_at=datetime.now(timezone.utc),
                joined_at=datetime.now(timezone.utc),
                is_active=True
            )

            await self.members_collection.insert_one(member_doc.model_dump(by_alias=True))

            # Create default categories
            await self._create_default_categories(website_id)

            self.logger.info("Created blog website: %s for user %s", website_id, owner_id)
            return website_doc

        except Exception as e:
            self.logger.error("Failed to create blog website: %s", e, exc_info=True)
            raise

    async def get_user_websites(self, user_id: str) -> List[BlogWebsiteDocument]:
        """Get all websites owned by or accessible to a user."""
        try:
            # Get websites where user is owner
            owned_websites = []
            async for website in self.websites_collection.find({"owner_id": user_id}):
                owned_websites.append(BlogWebsiteDocument(**website))

            # Get websites where user is a member
            member_websites = []
            async for membership in self.members_collection.find({"user_id": user_id, "is_active": True}):
                website = await self.websites_collection.find_one({"website_id": membership["website_id"]})
                if website and website not in owned_websites:
                    member_websites.append(BlogWebsiteDocument(**website))

            return owned_websites + member_websites

        except Exception as e:
            self.logger.error("Failed to get user websites for %s: %s", user_id, e, exc_info=True)
            raise

    async def get_website_by_slug(self, slug: str) -> Optional[BlogWebsiteDocument]:
        """Get website by slug with caching."""
        try:
            # Check cache first
            cache_key = f"blog:website:slug:{slug}"
            cached = await self.redis.get(cache_key)
            if cached:
                return BlogWebsiteDocument.parse_raw(cached)

            # Query database
            website = await self.websites_collection.find_one({"slug": slug})
            if website:
                website_doc = BlogWebsiteDocument(**website)
                # Cache for 1 hour
                await self.redis.setex(cache_key, 3600, website_doc.model_dump_json())
                return website_doc

            return None

        except Exception as e:
            self.logger.error("Failed to get website by slug %s: %s", slug, e, exc_info=True)
            raise

    async def check_website_access(
        self,
        user_id: str,
        website_id: str,
        required_role: WebsiteRole = WebsiteRole.VIEWER
    ) -> Optional[BlogWebsiteMemberDocument]:
        """Check if user has access to website with required role."""
        try:
            # Check if user is owner
            website = await self.websites_collection.find_one({"website_id": website_id, "owner_id": user_id})
            if website:
                return BlogWebsiteMemberDocument(
                    member_id=f"owner_{website_id}",
                    website_id=website_id,
                    user_id=user_id,
                    role=WebsiteRole.OWNER,
                    invited_by=user_id,
                    invited_at=website["created_at"],
                    joined_at=website["created_at"],
                    is_active=True
                )

            # Check membership
            membership = await self.members_collection.find_one({
                "website_id": website_id,
                "user_id": user_id,
                "is_active": True
            })

            if membership:
                member_doc = BlogWebsiteMemberDocument(**membership)
                # Check role hierarchy
                role_hierarchy = {
                    WebsiteRole.VIEWER: 0,
                    WebsiteRole.AUTHOR: 1,
                    WebsiteRole.EDITOR: 2,
                    WebsiteRole.ADMIN: 3,
                    WebsiteRole.OWNER: 4
                }

                user_level = role_hierarchy.get(member_doc.role, 0)
                required_level = role_hierarchy.get(required_role, 0)

                if user_level >= required_level:
                    return member_doc

            return None

        except Exception as e:
            self.logger.error("Failed to check website access: %s", e, exc_info=True)
            raise

    async def _create_default_categories(self, website_id: str):
        """Create default categories for a new website."""
        default_categories = [
            {"name": "Uncategorized", "slug": "uncategorized"},
            {"name": "News", "slug": "news"},
            {"name": "Tutorials", "slug": "tutorials"}
        ]

        for cat_data in default_categories:
            category_doc = BlogCategoryDocument(
                category_id=f"category_{uuid.uuid4().hex[:16]}",
                website_id=website_id,
                name=cat_data["name"],
                slug=cat_data["slug"],
                description=f"Default {cat_data['name'].lower()} category",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            await self.db.get_collection("blog_categories").insert_one(
                category_doc.model_dump(by_alias=True)
            )


class BlogContentService:
    """
    Service for blog content operations with website isolation.

    Handles posts, categories, and comments within specific websites.
    """

    def __init__(self, db_manager=None, redis_manager=None, website_manager=None):
        self.db = db_manager or globals()["db_manager"]
        self.redis = redis_manager or globals()["redis_manager"]
        self.website_manager = website_manager or BlogWebsiteManager()
        self.posts_collection = self.db.get_collection("blog_posts")
        self.categories_collection = self.db.get_collection("blog_categories")
        self.comments_collection = self.db.get_collection("blog_comments")
        self.logger = logger

    async def create_post(
        self,
        website_id: str,
        author_id: str,
        title: str,
        content: str,
        **kwargs
    ) -> BlogPostDocument:
        """Create a new blog post within a website."""
        try:
            # Check website access
            membership = await self.website_manager.check_website_access(
                author_id, website_id, WebsiteRole.AUTHOR
            )
            if not membership:
                raise ValueError("Insufficient permissions to create posts")

            # Generate unique slug within website
            base_slug = self._generate_slug(title)
            slug = await self._ensure_unique_slug(website_id, base_slug)

            # Calculate reading time and word count
            word_count = len(content.split())
            reading_time = max(1, word_count // 200)  # ~200 words per minute

            # Create post document
            post_doc = BlogPostDocument(
                post_id=f"post_{uuid.uuid4().hex[:16]}",
                website_id=website_id,
                title=title,
                slug=slug,
                content=content,
                excerpt=kwargs.get("excerpt", content[:300] + "..." if len(content) > 300 else content),
                featured_image=kwargs.get("featured_image"),
                author_id=author_id,
                status=kwargs.get("status", "draft"),
                categories=kwargs.get("categories", ["uncategorized"]),
                tags=kwargs.get("tags", []),
                seo_title=kwargs.get("seo_title"),
                seo_description=kwargs.get("seo_description"),
                seo_keywords=kwargs.get("seo_keywords", []),
                reading_time=reading_time,
                word_count=word_count,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            # Insert post
            await self.posts_collection.insert_one(post_doc.model_dump(by_alias=True))

            # Update website post count
            await self.db.get_collection("blog_websites").update_one(
                {"website_id": website_id},
                {"$inc": {"post_count": 1}}
            )

            # Clear website cache
            await self._clear_website_cache(website_id)

            self.logger.info("Created blog post: %s in website %s", post_doc.post_id, website_id)
            return post_doc

        except Exception as e:
            self.logger.error("Failed to create blog post: %s", e, exc_info=True)
            raise

    async def get_website_posts(
        self,
        website_id: str,
        page: int = 1,
        limit: int = 10,
        status: str = "published",
        category: Optional[str] = None
    ) -> List[BlogPostDocument]:
        """Get posts for a specific website with pagination."""
        try:
            # Build query
            query = {"website_id": website_id}
            if status:
                query["status"] = status
            if category:
                query["categories"] = category

            # Pagination
            skip = (page - 1) * limit

            # Get posts
            posts = []
            async for post in self.posts_collection.find(query).sort("published_at", -1).skip(skip).limit(limit):
                posts.append(BlogPostDocument(**post))

            return posts

        except Exception as e:
            self.logger.error("Failed to get website posts: %s", e, exc_info=True)
            raise

    async def get_post_by_slug(self, website_id: str, slug: str) -> Optional[BlogPostDocument]:
        """Get a post by slug within a website."""
        try:
            # Check cache first
            cache_key = f"blog:website:{website_id}:post:slug:{slug}"
            cached = await self.redis.get(cache_key)
            if cached:
                return BlogPostDocument.parse_raw(cached)

            # Query database
            post = await self.posts_collection.find_one({
                "website_id": website_id,
                "slug": slug
            })

            if post:
                post_doc = BlogPostDocument(**post)
                # Cache for 1 hour
                await self.redis.setex(cache_key, 3600, post_doc.model_dump_json())

                # Increment view count (async, don't wait)
                self.posts_collection.update_one(
                    {"post_id": post_doc.post_id},
                    {"$inc": {"view_count": 1}}
                )

                return post_doc

            return None

        except Exception as e:
            self.logger.error("Failed to get post by slug: %s", e, exc_info=True)
            raise

    async def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug from title."""
        import re
        # Convert to lowercase, replace spaces and special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s_-]+', '-', slug)
        return slug.strip('-')

    async def _ensure_unique_slug(self, website_id: str, base_slug: str) -> str:
        """Ensure slug is unique within website."""
        slug = base_slug
        counter = 1

        while await self.posts_collection.find_one({"website_id": website_id, "slug": slug}):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    async def _clear_website_cache(self, website_id: str):
        """Clear all cache keys for a website."""
        try:
            pattern = f"blog:website:{website_id}:*"
            # Note: In production, you'd want to use Redis SCAN or a more sophisticated cache clearing
            await self.redis.delete(pattern)
        except Exception as e:
            self.logger.warning("Failed to clear website cache: %s", e)


class BlogSEOService:
    """
    Service for SEO-related blog operations.

    Handles meta tags, sitemaps, RSS feeds, and search optimization.
    """

    def __init__(self, db_manager=None):
        self.db = db_manager or globals()["db_manager"]
        self.logger = logger

    def generate_meta_tags(self, post: BlogPostDocument, website: BlogWebsiteDocument) -> Dict[str, str]:
        """Generate SEO meta tags for a post."""
        meta = {}

        # Title
        if post.seo_title:
            meta["title"] = post.seo_title
        else:
            meta["title"] = f"{post.title} | {website.name}"

        # Description
        if post.seo_description:
            meta["description"] = post.seo_description
        else:
            meta["description"] = post.excerpt

        # Keywords
        if post.seo_keywords:
            meta["keywords"] = ", ".join(post.seo_keywords)

        # Open Graph
        meta["og:title"] = meta["title"]
        meta["og:description"] = meta["description"]
        meta["og:type"] = "article"
        if post.featured_image:
            meta["og:image"] = post.featured_image

        # Twitter Cards
        meta["twitter:card"] = "summary_large_image"
        meta["twitter:title"] = meta["title"]
        meta["twitter:description"] = meta["description"]
        if post.featured_image:
            meta["twitter:image"] = post.featured_image

        return meta

    async def generate_sitemap(self, website_id: str) -> str:
        """Generate XML sitemap for a website."""
        try:
            posts_collection = self.db.get_collection("blog_posts")

            # Get all published posts
            posts = []
            async for post in posts_collection.find({
                "website_id": website_id,
                "status": "published"
            }).sort("published_at", -1):
                posts.append(post)

            # Generate XML
            xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

            for post in posts:
                xml_parts.append('  <url>')
                xml_parts.append(f'    <loc>/posts/{post["slug"]}</loc>')
                if post.get("updated_at"):
                    xml_parts.append(f'    <lastmod>{post["updated_at"].date().isoformat()}</lastmod>')
                xml_parts.append('    <changefreq>monthly</changefreq>')
                xml_parts.append('    <priority>0.8</priority>')
                xml_parts.append('  </url>')

            xml_parts.append('</urlset>')

            return '\n'.join(xml_parts)

        except Exception as e:
            self.logger.error("Failed to generate sitemap: %s", e, exc_info=True)
            raise


class BlogAnalyticsService:
    """
    Service for blog analytics and tracking.

    Handles view tracking, engagement metrics, and analytics aggregation.
    """

    def __init__(self, db_manager=None, redis_manager=None):
        self.db = db_manager or globals()["db_manager"]
        self.redis = redis_manager or globals()["redis_manager"]
        self.analytics_collection = self.db.get_collection("blog_analytics")
        self.logger = logger

    async def track_post_view(
        self,
        website_id: str,
        post_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Track a view for a blog post."""
        try:
            today = datetime.now(timezone.utc).date()

            # Check for duplicate view (same IP/post/day)
            if ip_address:
                cache_key = f"blog:view:{post_id}:{ip_address}:{today.isoformat()}"
                if await self.redis.get(cache_key):
                    return  # Already counted today

                # Mark as viewed
                await self.redis.setex(cache_key, 86400, "1")  # 24 hours

            # Update analytics
            await self.analytics_collection.update_one(
                {
                    "website_id": website_id,
                    "post_id": post_id,
                    "date": today
                },
                {
                    "$inc": {"views": 1, "unique_views": 1 if ip_address else 0},
                    "$setOnInsert": {
                        "analytics_id": f"analytics_{uuid.uuid4().hex[:16]}",
                        "website_id": website_id,
                        "post_id": post_id,
                        "date": today
                    }
                },
                upsert=True
            )

            # Update post view count
            await self.db.get_collection("blog_posts").update_one(
                {"post_id": post_id},
                {"$inc": {"view_count": 1}}
            )

            # Update website view count
            await self.db.get_collection("blog_websites").update_one(
                {"website_id": website_id},
                {"$inc": {"total_views": 1, "monthly_views": 1}}
            )

        except Exception as e:
            self.logger.error("Failed to track post view: %s", e)

    async def get_website_analytics(self, website_id: str, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a website."""
        try:
            start_date = datetime.now(timezone.utc) - timezone.timedelta(days=days)

            pipeline = [
                {"$match": {"website_id": website_id, "date": {"$gte": start_date.date()}}},
                {"$group": {
                    "_id": None,
                    "total_views": {"$sum": "$views"},
                    "total_unique_views": {"$sum": "$unique_views"},
                    "total_likes": {"$sum": "$likes"},
                    "total_comments": {"$sum": "$comments"}
                }}
            ]

            result = await self.analytics_collection.aggregate(pipeline).to_list(1)

            if result:
                return result[0]
            else:
                return {
                    "total_views": 0,
                    "total_unique_views": 0,
                    "total_likes": 0,
                    "total_comments": 0
                }

        except Exception as e:
            self.logger.error("Failed to get website analytics: %s", e, exc_info=True)
            raise