"""
Blog Cache Manager for Redis-based caching with website isolation.

This module provides comprehensive caching for blog operations including
posts, categories, search results, analytics, and cache invalidation strategies.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
import hashlib

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[BlogCache]")


class BlogCacheManager:
    """
    Comprehensive Redis caching manager for blog operations.

    Provides caching for posts, categories, search results, analytics,
    and user permissions with website-level isolation and intelligent
    cache invalidation.
    """

    def __init__(self, redis_manager=None):
        self.redis = redis_manager or globals().get("redis_manager")
        self.logger = logger

    # Cache Key Patterns
    @staticmethod
    def _website_key(website_id: str) -> str:
        return f"blog:website:{website_id}"

    @staticmethod
    def _post_key(website_id: str, post_id: str) -> str:
        return f"blog:website:{website_id}:post:{post_id}"

    @staticmethod
    def _post_slug_key(website_id: str, slug: str) -> str:
        return f"blog:website:{website_id}:post:slug:{slug}"

    @staticmethod
    def _posts_list_key(website_id: str, status: str, category: Optional[str], page: int, limit: int) -> str:
        category_part = f":cat:{category}" if category else ""
        return f"blog:website:{website_id}:posts:{status}{category_part}:page:{page}:limit:{limit}"

    @staticmethod
    def _categories_key(website_id: str) -> str:
        return f"blog:website:{website_id}:categories"

    @staticmethod
    def _comments_key(website_id: str, post_id: str, status: str) -> str:
        return f"blog:website:{website_id}:post:{post_id}:comments:{status}"

    @staticmethod
    def _analytics_key(website_id: str, days: int) -> str:
        return f"blog:website:{website_id}:analytics:days:{days}"

    @staticmethod
    def _search_key(website_id: str, query: str, filters: Dict[str, Any]) -> str:
        # Create deterministic key from query and filters
        filter_str = json.dumps(filters, sort_keys=True)
        key_content = f"{website_id}:{query}:{filter_str}"
        key_hash = hashlib.md5(key_content.encode()).hexdigest()[:16]
        return f"blog:website:{website_id}:search:{key_hash}"

    @staticmethod
    def _user_permissions_key(user_id: str, website_id: str) -> str:
        return f"blog:user:{user_id}:website:{website_id}:permissions"

    # Website Caching
    async def cache_website(self, website_data: Dict[str, Any], ttl: int = 3600) -> None:
        """Cache website data."""
        try:
            website_id = website_data.get("website_id")
            if not website_id:
                return

            key = self._website_key(website_id)
            await self.redis.setex(key, ttl, json.dumps(website_data))
            self.logger.debug("Cached website: %s", website_id)
        except Exception as e:
            self.logger.error("Failed to cache website: %s", e)

    async def get_cached_website(self, website_id: str) -> Optional[Dict[str, Any]]:
        """Get cached website data."""
        try:
            key = self._website_key(website_id)
            cached = await self.redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            self.logger.error("Failed to get cached website: %s", e)
            return None

    # Post Caching
    async def cache_post(self, post_data: Dict[str, Any], ttl: int = 1800) -> None:
        """Cache post data with multiple keys."""
        try:
            website_id = post_data.get("website_id")
            post_id = post_data.get("post_id")
            slug = post_data.get("slug")

            if not all([website_id, post_id, slug]):
                return

            # Cache by post ID
            post_key = self._post_key(website_id, post_id)
            await self.redis.setex(post_key, ttl, json.dumps(post_data))

            # Cache by slug
            slug_key = self._post_slug_key(website_id, slug)
            await self.redis.setex(slug_key, ttl, json.dumps(post_data))

            self.logger.debug("Cached post: %s in website %s", post_id, website_id)
        except Exception as e:
            self.logger.error("Failed to cache post: %s", e)

    async def get_cached_post(self, website_id: str, post_id: str) -> Optional[Dict[str, Any]]:
        """Get cached post by ID."""
        try:
            key = self._post_key(website_id, post_id)
            cached = await self.redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            self.logger.error("Failed to get cached post: %s", e)
            return None

    async def get_cached_post_by_slug(self, website_id: str, slug: str) -> Optional[Dict[str, Any]]:
        """Get cached post by slug."""
        try:
            key = self._post_slug_key(website_id, slug)
            cached = await self.redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            self.logger.error("Failed to get cached post by slug: %s", e)
            return None

    # Posts List Caching
    async def cache_posts_list(
        self,
        website_id: str,
        posts: List[Dict[str, Any]],
        status: str,
        category: Optional[str],
        page: int,
        limit: int,
        ttl: int = 600
    ) -> None:
        """Cache posts list with pagination."""
        try:
            key = self._posts_list_key(website_id, status, category, page, limit)
            cache_data = {
                "posts": posts,
                "total": len(posts),  # This should be enhanced with actual total count
                "cached_at": datetime.utcnow().isoformat()
            }
            await self.redis.setex(key, ttl, json.dumps(cache_data))
            self.logger.debug("Cached posts list for website %s: %d posts", website_id, len(posts))
        except Exception as e:
            self.logger.error("Failed to cache posts list: %s", e)

    async def get_cached_posts_list(
        self,
        website_id: str,
        status: str,
        category: Optional[str],
        page: int,
        limit: int
    ) -> Optional[Dict[str, Any]]:
        """Get cached posts list."""
        try:
            key = self._posts_list_key(website_id, status, category, page, limit)
            cached = await self.redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            self.logger.error("Failed to get cached posts list: %s", e)
            return None

    # Categories Caching
    async def cache_categories(self, website_id: str, categories: List[Dict[str, Any]], ttl: int = 1800) -> None:
        """Cache website categories."""
        try:
            key = self._categories_key(website_id)
            cache_data = {
                "categories": categories,
                "cached_at": datetime.utcnow().isoformat()
            }
            await self.redis.setex(key, ttl, json.dumps(cache_data))
            self.logger.debug("Cached categories for website %s: %d categories", website_id, len(categories))
        except Exception as e:
            self.logger.error("Failed to cache categories: %s", e)

    async def get_cached_categories(self, website_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached categories."""
        try:
            key = self._categories_key(website_id)
            cached = await self.redis.get(key)
            if cached:
                data = json.loads(cached)
                return data.get("categories", [])
            return None
        except Exception as e:
            self.logger.error("Failed to get cached categories: %s", e)
            return None

    # Comments Caching
    async def cache_comments(
        self,
        website_id: str,
        post_id: str,
        comments: List[Dict[str, Any]],
        status: str,
        ttl: int = 300
    ) -> None:
        """Cache post comments."""
        try:
            key = self._comments_key(website_id, post_id, status)
            cache_data = {
                "comments": comments,
                "cached_at": datetime.utcnow().isoformat()
            }
            await self.redis.setex(key, ttl, json.dumps(cache_data))
            self.logger.debug("Cached comments for post %s: %d comments", post_id, len(comments))
        except Exception as e:
            self.logger.error("Failed to cache comments: %s", e)

    async def get_cached_comments(self, website_id: str, post_id: str, status: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached comments."""
        try:
            key = self._comments_key(website_id, post_id, status)
            cached = await self.redis.get(key)
            if cached:
                data = json.loads(cached)
                return data.get("comments", [])
            return None
        except Exception as e:
            self.logger.error("Failed to get cached comments: %s", e)
            return None

    # Analytics Caching
    async def cache_analytics(self, website_id: str, analytics: Dict[str, Any], days: int, ttl: int = 900) -> None:
        """Cache website analytics."""
        try:
            key = self._analytics_key(website_id, days)
            cache_data = {
                "analytics": analytics,
                "cached_at": datetime.utcnow().isoformat()
            }
            await self.redis.setex(key, ttl, json.dumps(cache_data))
            self.logger.debug("Cached analytics for website %s (%d days)", website_id, days)
        except Exception as e:
            self.logger.error("Failed to cache analytics: %s", e)

    async def get_cached_analytics(self, website_id: str, days: int) -> Optional[Dict[str, Any]]:
        """Get cached analytics."""
        try:
            key = self._analytics_key(website_id, days)
            cached = await self.redis.get(key)
            if cached:
                data = json.loads(cached)
                return data.get("analytics")
            return None
        except Exception as e:
            self.logger.error("Failed to get cached analytics: %s", e)
            return None

    # Search Results Caching
    async def cache_search_results(
        self,
        website_id: str,
        query: str,
        filters: Dict[str, Any],
        results: List[Dict[str, Any]],
        ttl: int = 300
    ) -> None:
        """Cache search results."""
        try:
            key = self._search_key(website_id, query, filters)
            cache_data = {
                "query": query,
                "filters": filters,
                "results": results,
                "cached_at": datetime.utcnow().isoformat()
            }
            await self.redis.setex(key, ttl, json.dumps(cache_data))
            self.logger.debug("Cached search results for website %s: %d results", website_id, len(results))
        except Exception as e:
            self.logger.error("Failed to cache search results: %s", e)

    async def get_cached_search_results(
        self,
        website_id: str,
        query: str,
        filters: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results."""
        try:
            key = self._search_key(website_id, query, filters)
            cached = await self.redis.get(key)
            if cached:
                data = json.loads(cached)
                return data.get("results", [])
            return None
        except Exception as e:
            self.logger.error("Failed to get cached search results: %s", e)
            return None

    # User Permissions Caching
    async def cache_user_permissions(
        self,
        user_id: str,
        website_id: str,
        permissions: Dict[str, Any],
        ttl: int = 600
    ) -> None:
        """Cache user permissions for a website."""
        try:
            key = self._user_permissions_key(user_id, website_id)
            cache_data = {
                "permissions": permissions,
                "cached_at": datetime.utcnow().isoformat()
            }
            await self.redis.setex(key, ttl, json.dumps(cache_data))
            self.logger.debug("Cached permissions for user %s on website %s", user_id, website_id)
        except Exception as e:
            self.logger.error("Failed to cache user permissions: %s", e)

    async def get_cached_user_permissions(self, user_id: str, website_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user permissions."""
        try:
            key = self._user_permissions_key(user_id, website_id)
            cached = await self.redis.get(key)
            if cached:
                data = json.loads(cached)
                return data.get("permissions")
            return None
        except Exception as e:
            self.logger.error("Failed to get cached user permissions: %s", e)
            return None

    # Cache Invalidation Methods
    async def invalidate_website_cache(self, website_id: str) -> None:
        """Invalidate all cache for a website."""
        try:
            pattern = f"blog:website:{website_id}:*"
            # In production, use Redis SCAN for better performance
            # For now, we'll delete known patterns
            keys_to_delete = []

            # Get all related keys (this is simplified - in production use SCAN)
            # For now, we'll just clear the main website key and rely on TTL for others
            website_key = self._website_key(website_id)
            categories_key = self._categories_key(website_id)
            analytics_keys = [
                self._analytics_key(website_id, days) for days in [7, 30, 90]
            ]

            keys_to_delete.extend([website_key, categories_key] + analytics_keys)

            if keys_to_delete:
                await self.redis.delete(*keys_to_delete)

            self.logger.info("Invalidated cache for website: %s", website_id)
        except Exception as e:
            self.logger.error("Failed to invalidate website cache: %s", e)

    async def invalidate_post_cache(self, website_id: str, post_id: str) -> None:
        """Invalidate cache for a specific post."""
        try:
            # Get post data to find slug
            post_key = self._post_key(website_id, post_id)
            cached_post = await self.redis.get(post_key)

            keys_to_delete = [post_key]

            if cached_post:
                post_data = json.loads(cached_post)
                slug = post_data.get("slug")
                if slug:
                    slug_key = self._post_slug_key(website_id, slug)
                    keys_to_delete.append(slug_key)

                # Also invalidate posts lists (this is simplified)
                # In production, you might want to track which lists contain this post

            if keys_to_delete:
                await self.redis.delete(*keys_to_delete)

            self.logger.debug("Invalidated cache for post: %s", post_id)
        except Exception as e:
            self.logger.error("Failed to invalidate post cache: %s", e)

    async def invalidate_user_permissions(self, user_id: str, website_id: Optional[str] = None) -> None:
        """Invalidate user permissions cache."""
        try:
            if website_id:
                key = self._user_permissions_key(user_id, website_id)
                await self.redis.delete(key)
            else:
                # Invalidate all permissions for user (simplified)
                pattern = f"blog:user:{user_id}:website:*:permissions"
                # In production, use SCAN to find all matching keys
                pass

            self.logger.debug("Invalidated permissions cache for user: %s", user_id)
        except Exception as e:
            self.logger.error("Failed to invalidate user permissions: %s", e)

    # Cache Warming Methods
    async def warm_website_cache(self, website_id: str) -> None:
        """Warm up cache for a website."""
        try:
            # This would be called by a background task
            # Implementation would fetch and cache frequently accessed data
            self.logger.info("Warming cache for website: %s", website_id)
        except Exception as e:
            self.logger.error("Failed to warm website cache: %s", e)

    # Cache Statistics
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            # This would provide cache hit/miss statistics
            # Implementation depends on your monitoring setup
            return {
                "status": "cache_stats_not_implemented",
                "note": "Implement cache statistics based on your monitoring needs"
            }
        except Exception as e:
            self.logger.error("Failed to get cache stats: %s", e)
            return {"error": str(e)}


# Global blog cache manager instance
blog_cache_manager = BlogCacheManager()