"""
Migration for creating blog collections and indexes.

This migration creates all necessary collections for the multi-tenant blog system
with proper indexes, constraints, and website-level data isolation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid

from pymongo.errors import DuplicateKeyError, PyMongoError

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

from .migration_manager import BaseMigration

logger = get_logger(prefix="[BlogCollectionsMigration]")


class BlogCollectionsMigration(BaseMigration):
    """
    Migration to create blog collections with proper schema and indexes.

    This migration creates:
    - blog_websites collection with indexes
    - blog_posts collection with website-partitioned indexes
    - blog_categories collection with website-partitioned indexes
    - blog_comments collection with website-partitioned indexes
    - blog_website_members collection for team management
    - blog_analytics collection for website analytics
    """

    @property
    def name(self) -> str:
        return "create_blog_collections"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Create blog collections with website-partitioned indexes and constraints"

    async def validate(self) -> bool:
        """Validate that the migration can be applied."""
        try:
            # Check database connection
            if not await db_manager.health_check():
                self.logger.error("Database health check failed")
                return False

            # Check if collections already exist
            if self.database is None:
                self.logger.error("Database not connected")
                return False

            existing_collections = await self.database.list_collection_names()
            blog_collections = [
                "blog_websites",
                "blog_posts",
                "blog_categories",
                "blog_comments",
                "blog_website_members",
                "blog_analytics",
            ]

            for collection_name in blog_collections:
                if collection_name in existing_collections:
                    self.logger.warning("Collection %s already exists", collection_name)

            self.logger.info("Blog migration validation passed")
            return True

        except Exception as e:
            self.logger.error("Blog migration validation failed: %s", e, exc_info=True)
            return False

    @property
    def database(self):
        """Get database instance."""
        return db_manager.database

    async def up(self) -> Dict[str, Any]:
        """Execute the migration to create blog collections."""
        collections_affected = []
        records_processed = 0
        rollback_data = {}

        try:
            self.logger.info("Starting blog collections migration")

            # Create blog_websites collection
            await self._create_blog_websites_collection()
            collections_affected.append("blog_websites")

            # Create blog_posts collection
            await self._create_blog_posts_collection()
            collections_affected.append("blog_posts")

            # Create blog_categories collection
            await self._create_blog_categories_collection()
            collections_affected.append("blog_categories")

            # Create blog_comments collection
            await self._create_blog_comments_collection()
            collections_affected.append("blog_comments")

            # Create blog_website_members collection
            await self._create_blog_website_members_collection()
            collections_affected.append("blog_website_members")

            # Create blog_analytics collection
            await self._create_blog_analytics_collection()
            collections_affected.append("blog_analytics")

            # Create all indexes
            await self._create_all_indexes()

            # Store rollback data
            rollback_data = {
                "collections_created": collections_affected,
                "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.logger.info("Blog collections migration completed successfully")

            return {
                "collections_affected": collections_affected,
                "records_processed": records_processed,
                "rollback_data": rollback_data,
            }

        except Exception as e:
            self.logger.error("Blog collections migration failed: %s", e, exc_info=True)
            raise Exception(f"Migration failed: {str(e)}")

    async def down(self) -> Dict[str, Any]:
        """Rollback the migration by dropping created collections."""
        collections_dropped = []

        try:
            self.logger.info("Starting blog collections migration rollback")

            # Drop blog collections
            blog_collections = [
                "blog_websites",
                "blog_posts",
                "blog_categories",
                "blog_comments",
                "blog_website_members",
                "blog_analytics",
            ]

            for collection_name in blog_collections:
                try:
                    await self.database.drop_collection(collection_name)
                    collections_dropped.append(collection_name)
                    self.logger.info("Dropped collection: %s", collection_name)
                except Exception as e:
                    self.logger.warning("Failed to drop collection %s: %s", collection_name, e)

            self.logger.info("Blog collections migration rollback completed")

            return {"collections_dropped": collections_dropped}

        except Exception as e:
            self.logger.error("Migration rollback failed: %s", e, exc_info=True)
            raise Exception(f"Rollback failed: {str(e)}")

    async def _create_blog_websites_collection(self):
        """Create the blog_websites collection with proper schema."""
        try:
            # Create collection
            websites_collection = db_manager.get_collection("blog_websites")

            # Create a sample document to establish schema (will be removed)
            sample_doc = {
                "_schema_version": "1.0.0",
                "website_id": f"website_{uuid.uuid4().hex[:16]}",
                "name": "Sample Blog",
                "slug": f"sample-blog-{uuid.uuid4().hex[:8]}",
                "description": "A sample blog website",
                "owner_id": "sample_owner",
                "is_active": True,
                "is_public": True,
                "allow_comments": True,
                "require_comment_approval": True,
                "allow_guest_comments": True,
                "seo_title": "Sample Blog - Welcome",
                "seo_description": "Welcome to our sample blog",
                "google_analytics_id": None,
                "post_count": 0,
                "total_views": 0,
                "monthly_views": 0,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "last_post_at": None,
            }

            await websites_collection.insert_one(sample_doc)
            await websites_collection.delete_one({"website_id": sample_doc["website_id"]})

            self.logger.info("Created blog_websites collection")

        except Exception as e:
            self.logger.error("Failed to create blog_websites collection: %s", e, exc_info=True)
            raise

    async def _create_blog_posts_collection(self):
        """Create the blog_posts collection with website-partitioned schema."""
        try:
            posts_collection = db_manager.get_collection("blog_posts")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "post_id": f"post_{uuid.uuid4().hex[:16]}",
                "website_id": f"website_{uuid.uuid4().hex[:16]}",
                "title": "Sample Blog Post",
                "slug": f"sample-post-{uuid.uuid4().hex[:8]}",
                "content": "# Sample Content\n\nThis is a sample blog post.",
                "excerpt": "A sample blog post excerpt",
                "featured_image": None,
                "author_id": "sample_author",
                "status": "draft",
                "published_at": None,
                "updated_at": datetime.now(timezone.utc),
                "categories": ["sample-category"],
                "tags": ["sample", "blog"],
                "seo_title": "Sample Blog Post",
                "seo_description": "This is a sample blog post",
                "seo_keywords": ["sample", "blog", "post"],
                "reading_time": 1,
                "word_count": 25,
                "view_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "is_featured": False,
                "is_pinned": False,
                "scheduled_publish_at": None,
                "revision_history": [],
            }

            await posts_collection.insert_one(sample_doc)
            await posts_collection.delete_one({"post_id": sample_doc["post_id"]})

            self.logger.info("Created blog_posts collection")

        except Exception as e:
            self.logger.error("Failed to create blog_posts collection: %s", e, exc_info=True)
            raise

    async def _create_blog_categories_collection(self):
        """Create the blog_categories collection with website-partitioned schema."""
        try:
            categories_collection = db_manager.get_collection("blog_categories")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "category_id": f"category_{uuid.uuid4().hex[:16]}",
                "website_id": f"website_{uuid.uuid4().hex[:16]}",
                "name": "Sample Category",
                "slug": f"sample-category-{uuid.uuid4().hex[:8]}",
                "description": "A sample blog category",
                "parent_id": None,
                "post_count": 0,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            await categories_collection.insert_one(sample_doc)
            await categories_collection.delete_one({"category_id": sample_doc["category_id"]})

            self.logger.info("Created blog_categories collection")

        except Exception as e:
            self.logger.error("Failed to create blog_categories collection: %s", e, exc_info=True)
            raise

    async def _create_blog_comments_collection(self):
        """Create the blog_comments collection with website-partitioned schema."""
        try:
            comments_collection = db_manager.get_collection("blog_comments")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "comment_id": f"comment_{uuid.uuid4().hex[:16]}",
                "website_id": f"website_{uuid.uuid4().hex[:16]}",
                "post_id": f"post_{uuid.uuid4().hex[:16]}",
                "author_id": None,
                "author_name": "Sample Guest",
                "author_email": "guest@example.com",
                "content": "This is a sample comment",
                "parent_id": None,
                "status": "pending",
                "is_approved": False,
                "moderated_by": None,
                "moderated_at": None,
                "likes": 0,
                "ip_address": "127.0.0.1",
                "user_agent": "Sample User Agent",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            await comments_collection.insert_one(sample_doc)
            await comments_collection.delete_one({"comment_id": sample_doc["comment_id"]})

            self.logger.info("Created blog_comments collection")

        except Exception as e:
            self.logger.error("Failed to create blog_comments collection: %s", e, exc_info=True)
            raise

    async def _create_blog_website_members_collection(self):
        """Create the blog_website_members collection for team management."""
        try:
            members_collection = db_manager.get_collection("blog_website_members")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "member_id": f"member_{uuid.uuid4().hex[:16]}",
                "website_id": f"website_{uuid.uuid4().hex[:16]}",
                "user_id": "sample_user",
                "role": "editor",
                "invited_by": "sample_owner",
                "invited_at": datetime.now(timezone.utc),
                "joined_at": datetime.now(timezone.utc),
                "is_active": True,
            }

            await members_collection.insert_one(sample_doc)
            await members_collection.delete_one({"member_id": sample_doc["member_id"]})

            self.logger.info("Created blog_website_members collection")

        except Exception as e:
            self.logger.error("Failed to create blog_website_members collection: %s", e, exc_info=True)
            raise

    async def _create_blog_analytics_collection(self):
        """Create the blog_analytics collection for website analytics."""
        try:
            analytics_collection = db_manager.get_collection("blog_analytics")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "analytics_id": f"analytics_{uuid.uuid4().hex[:16]}",
                "website_id": f"website_{uuid.uuid4().hex[:16]}",
                "post_id": None,
                "date": datetime.now(timezone.utc).date(),
                "views": 0,
                "unique_views": 0,
                "likes": 0,
                "comments": 0,
                "shares": {},
                "referrer_sources": {},
                "device_types": {},
                "countries": {},
                "top_pages": [],
            }

            await analytics_collection.insert_one(sample_doc)
            await analytics_collection.delete_one({"analytics_id": sample_doc["analytics_id"]})

            self.logger.info("Created blog_analytics collection")

        except Exception as e:
            self.logger.error("Failed to create blog_analytics collection: %s", e, exc_info=True)
            raise

    async def _create_all_indexes(self):
        """Create all necessary indexes for blog collections."""
        try:
            self.logger.info("Creating indexes for blog collections")

            # Blog websites collection indexes
            websites_collection = db_manager.get_collection("blog_websites")
            await websites_collection.create_index("website_id", unique=True)
            await websites_collection.create_index("slug", unique=True)
            await websites_collection.create_index("owner_id")
            await websites_collection.create_index("is_active")
            await websites_collection.create_index("is_public")
            await websites_collection.create_index("created_at")
            await websites_collection.create_index("last_post_at")

            # Blog posts collection indexes (website-partitioned)
            posts_collection = db_manager.get_collection("blog_posts")
            await posts_collection.create_index("post_id", unique=True)
            await posts_collection.create_index([("website_id", 1), ("slug", 1)], unique=True)
            await posts_collection.create_index([("website_id", 1), ("status", 1), ("published_at", -1)])
            await posts_collection.create_index([("website_id", 1), ("author_id", 1), ("published_at", -1)])
            await posts_collection.create_index([("website_id", 1), ("categories", 1), ("published_at", -1)])
            await posts_collection.create_index([("website_id", 1), ("tags", 1), ("published_at", -1)])
            await posts_collection.create_index([("website_id", 1), ("is_featured", 1), ("published_at", -1)])
            await posts_collection.create_index([("website_id", 1), ("view_count", -1)])
            await posts_collection.create_index("published_at", -1)  # Global recent posts
            await posts_collection.create_index("updated_at")

            # Blog categories collection indexes (website-partitioned)
            categories_collection = db_manager.get_collection("blog_categories")
            await categories_collection.create_index("category_id", unique=True)
            await categories_collection.create_index([("website_id", 1), ("slug", 1)], unique=True)
            await categories_collection.create_index([("website_id", 1), ("parent_id", 1)])
            await categories_collection.create_index([("website_id", 1), ("post_count", -1)])

            # Blog comments collection indexes (website-partitioned)
            comments_collection = db_manager.get_collection("blog_comments")
            await comments_collection.create_index("comment_id", unique=True)
            await comments_collection.create_index([("website_id", 1), ("post_id", 1), ("status", 1), ("created_at", -1)])
            await comments_collection.create_index([("website_id", 1), ("status", 1), ("created_at", -1)])
            await comments_collection.create_index([("website_id", 1), ("author_id", 1), ("created_at", -1)])
            await comments_collection.create_index([("post_id", 1), ("parent_id", 1)])
            await comments_collection.create_index("created_at")

            # Blog website members collection indexes
            members_collection = db_manager.get_collection("blog_website_members")
            await members_collection.create_index("member_id", unique=True)
            await members_collection.create_index([("website_id", 1), ("user_id", 1)], unique=True)
            await members_collection.create_index([("user_id", 1), ("is_active", 1)])
            await members_collection.create_index([("website_id", 1), ("role", 1)])

            # Blog analytics collection indexes
            analytics_collection = db_manager.get_collection("blog_analytics")
            await analytics_collection.create_index("analytics_id", unique=True)
            await analytics_collection.create_index([("website_id", 1), ("date", -1)])
            await analytics_collection.create_index([("website_id", 1), ("post_id", 1), ("date", -1)])
            await analytics_collection.create_index("date")

            self.logger.info("All blog collection indexes created successfully")

        except Exception as e:
            self.logger.error("Failed to create blog collection indexes: %s", e, exc_info=True)
            raise