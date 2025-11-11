"""
Club Manager for handling multi-tenant club operations.

This module provides the ClubManager class for managing clubs, verticals, and members
with university-level data isolation.
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
from second_brain_database.models.club_models import (
    ClubDocument,
    ClubMemberDocument,
    ClubRole,
    UniversityDocument,
    VerticalDocument,
    UniversityStatus,
)

logger = get_logger(prefix="[ClubManager]")


class ClubManager:
    """
    Manager for club operations with university-level isolation.

    Handles university creation, club management, member operations, and
    university-level permissions.
    """

    def __init__(self, db_manager=None, redis_manager=None):
        self.db = db_manager
        self.redis = redis_manager or globals().get("redis_manager")
        # Collections will be initialized lazily
        self._universities_collection = None
        self._clubs_collection = None
        self._verticals_collection = None
        self._members_collection = None
        self._analytics_collection = None
        self.logger = logger

    @property
    def universities_collection(self):
        if self._universities_collection is None:
            if self.db is None:
                self.db = globals()["db_manager"]
            self._universities_collection = self.db.get_collection("universities")
        return self._universities_collection

    @property
    def clubs_collection(self):
        if self._clubs_collection is None:
            if self.db is None:
                self.db = globals()["db_manager"]
            self._clubs_collection = self.db.get_collection("clubs")
        return self._clubs_collection

    @property
    def verticals_collection(self):
        if self._verticals_collection is None:
            if self.db is None:
                self.db = globals()["db_manager"]
            self._verticals_collection = self.db.get_collection("club_verticals")
        return self._verticals_collection

    @property
    def members_collection(self):
        if self._members_collection is None:
            if self.db is None:
                self.db = globals()["db_manager"]
            self._members_collection = self.db.get_collection("club_members")
        return self._members_collection

    @property
    def analytics_collection(self):
        if self._analytics_collection is None:
            if self.db is None:
                self.db = globals()["db_manager"]
            self._analytics_collection = self.db.get_collection("club_analytics")
        return self._analytics_collection

    async def create_university(
        self,
        name: str,
        domain: str,
        created_by: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        website: Optional[str] = None,
        logo_url: Optional[str] = None
    ) -> UniversityDocument:
        """Create a new university."""
        try:
            # Check if domain already exists
            existing = await self.universities_collection.find_one({"domain": domain.lower()})
            if existing:
                raise ValueError(f"University with domain '{domain}' already exists")

            # Generate unique ID
            university_id = f"university_{uuid.uuid4().hex[:16]}"

            # Create university document
            university_doc = UniversityDocument(
                university_id=university_id,
                name=name,
                domain=domain.lower(),
                description=description,
                location=location,
                website=website,
                logo_url=logo_url,
                is_verified=False,
                admin_approved=False,
                status=UniversityStatus.PENDING,
                created_by=created_by,
                club_count=0,
                total_members=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            # Insert university
            await self.universities_collection.insert_one(university_doc.model_dump(by_alias=True))

            self.logger.info("Created university: %s for user %s", university_id, created_by)
            return university_doc

        except Exception as e:
            self.logger.error("Failed to create university: %s", e, exc_info=True)
            raise

    async def approve_university(self, university_id: str, approved_by: str) -> UniversityDocument:
        """Approve a university (admin only)."""
        try:
            # Update university
            update_data = {
                "admin_approved": True,
                "status": UniversityStatus.VERIFIED,
                "approved_by": approved_by,
                "approved_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            result = await self.universities_collection.update_one(
                {"university_id": university_id},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise ValueError(f"University {university_id} not found")

            # Get updated university
            university = await self.universities_collection.find_one({"university_id": university_id})
            university_doc = UniversityDocument(**university)

            # Clear cache
            await self._clear_university_cache(university_id)

            self.logger.info("Approved university: %s by admin %s", university_id, approved_by)
            return university_doc

        except Exception as e:
            self.logger.error("Failed to approve university: %s", e, exc_info=True)
            raise

    async def create_club(
        self,
        owner_id: str,
        university_id: str,
        name: str,
        category: str,
        description: Optional[str] = None,
        **kwargs
    ) -> ClubDocument:
        """Create a new club within a university."""
        try:
            # Verify university exists and is approved
            university = await self.universities_collection.find_one({
                "university_id": university_id,
                "admin_approved": True
            })
            if not university:
                raise ValueError(f"University {university_id} not found or not approved")

            # Generate unique slug
            base_slug = self._generate_slug(name)
            slug = await self._ensure_unique_club_slug(university_id, base_slug)

            # Generate unique ID
            club_id = f"club_{uuid.uuid4().hex[:16]}"

            # Create club document
            club_doc = ClubDocument(
                club_id=club_id,
                name=name,
                slug=slug,
                description=description,
                category=category,
                university_id=university_id,
                owner_id=owner_id,
                logo_url=kwargs.get("logo_url"),
                banner_url=kwargs.get("banner_url"),
                website_url=kwargs.get("website_url"),
                social_links=kwargs.get("social_links", {}),
                max_members=kwargs.get("max_members"),
                tags=kwargs.get("tags", []),
                member_count=1,  # Owner counts as member
                vertical_count=0,
                is_active=True,
                is_public=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            # Insert club
            await self.clubs_collection.insert_one(club_doc.model_dump(by_alias=True))

            # Create owner membership
            member_doc = ClubMemberDocument(
                member_id=f"member_{uuid.uuid4().hex[:16]}",
                club_id=club_id,
                user_id=owner_id,
                role=ClubRole.OWNER,
                invited_by=owner_id,
                invited_at=datetime.now(timezone.utc),
                joined_at=datetime.now(timezone.utc),
                is_active=True
            )

            await self.members_collection.insert_one(member_doc.model_dump(by_alias=True))

            # Update university club count
            await self.universities_collection.update_one(
                {"university_id": university_id},
                {"$inc": {"club_count": 1, "total_members": 1}}
            )

            self.logger.info("Created club: %s in university %s for user %s", club_id, university_id, owner_id)
            return club_doc

        except Exception as e:
            self.logger.error("Failed to create club: %s", e, exc_info=True)
            raise

    async def create_vertical(
        self,
        club_id: str,
        name: str,
        lead_id: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs
    ) -> VerticalDocument:
        """Create a new vertical within a club."""
        try:
            # Verify club exists
            club = await self.clubs_collection.find_one({"club_id": club_id, "is_active": True})
            if not club:
                raise ValueError(f"Club {club_id} not found or inactive")

            # If lead specified, verify they are club member
            if lead_id:
                member = await self.members_collection.find_one({
                    "club_id": club_id,
                    "user_id": lead_id,
                    "is_active": True
                })
                if not member:
                    raise ValueError(f"User {lead_id} is not an active member of club {club_id}")

            # Generate unique ID
            vertical_id = f"vertical_{uuid.uuid4().hex[:16]}"

            # Create vertical document
            vertical_doc = VerticalDocument(
                vertical_id=vertical_id,
                club_id=club_id,
                name=name,
                description=description,
                lead_id=lead_id,
                member_count=0,
                max_members=kwargs.get("max_members"),
                color=kwargs.get("color"),
                icon=kwargs.get("icon"),
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            # Insert vertical
            await self.verticals_collection.insert_one(vertical_doc.model_dump(by_alias=True))

            # Update club vertical count
            await self.clubs_collection.update_one(
                {"club_id": club_id},
                {"$inc": {"vertical_count": 1}}
            )

            # Clear club cache
            await self._clear_club_cache(club_id)

            self.logger.info("Created vertical: %s in club %s", vertical_id, club_id)
            return vertical_doc

        except Exception as e:
            self.logger.error("Failed to create vertical: %s", e, exc_info=True)
            raise

    async def invite_member(
        self,
        club_id: str,
        user_id: str,
        role: ClubRole,
        invited_by: str,
        vertical_id: Optional[str] = None,
        message: Optional[str] = None
    ) -> ClubMemberDocument:
        """Invite a user to join a club."""
        try:
            # Verify club exists and is active
            club = await self.clubs_collection.find_one({"club_id": club_id, "is_active": True})
            if not club:
                raise ValueError(f"Club {club_id} not found or inactive")

            # Check if user is already a member
            existing = await self.members_collection.find_one({
                "club_id": club_id,
                "user_id": user_id
            })
            if existing:
                if existing["is_active"]:
                    raise ValueError(f"User {user_id} is already a member of club {club_id}")
                else:
                    # Reactivate membership
                    await self.members_collection.update_one(
                        {"member_id": existing["member_id"]},
                        {
                            "$set": {
                                "role": role,
                                "vertical_id": vertical_id,
                                "invited_by": invited_by,
                                "invited_at": datetime.now(timezone.utc),
                                "is_active": True,
                                "is_alumni": False,
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                    member = await self.members_collection.find_one({"member_id": existing["member_id"]})
                    member_doc = ClubMemberDocument(**member)

                    # Update club member count
                    await self.clubs_collection.update_one(
                        {"club_id": club_id},
                        {"$inc": {"member_count": 1}}
                    )

                    self.logger.info("Reactivated membership: %s in club %s", member_doc.member_id, club_id)
                    return member_doc

            # Check member limit
            if club.get("max_members") and club["member_count"] >= club["max_members"]:
                raise ValueError(f"Club {club_id} has reached maximum member limit")

            # If vertical specified, verify it exists
            if vertical_id:
                vertical = await self.verticals_collection.find_one({
                    "vertical_id": vertical_id,
                    "club_id": club_id,
                    "is_active": True
                })
                if not vertical:
                    raise ValueError(f"Vertical {vertical_id} not found in club {club_id}")

            # Create membership
            member_doc = ClubMemberDocument(
                member_id=f"member_{uuid.uuid4().hex[:16]}",
                club_id=club_id,
                user_id=user_id,
                role=role,
                vertical_id=vertical_id,
                invited_by=invited_by,
                invited_at=datetime.now(timezone.utc),
                is_active=False,  # Not active until accepted
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            await self.members_collection.insert_one(member_doc.model_dump(by_alias=True))

            # TODO: Send invitation notification
            # await self._send_invitation_notification(member_doc, message)

            self.logger.info("Invited user %s to club %s with role %s", user_id, club_id, role.value)
            return member_doc

        except Exception as e:
            self.logger.error("Failed to invite member: %s", e, exc_info=True)
            raise

    async def accept_invitation(self, member_id: str, user_id: str) -> ClubMemberDocument:
        """Accept a club invitation."""
        try:
            # Find and verify membership
            membership = await self.members_collection.find_one({
                "member_id": member_id,
                "user_id": user_id,
                "is_active": False
            })
            if not membership:
                raise ValueError(f"Invitation {member_id} not found or already accepted")

            # Update membership
            update_data = {
                "is_active": True,
                "joined_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            result = await self.members_collection.update_one(
                {"member_id": member_id},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise ValueError(f"Failed to accept invitation {member_id}")

            # Get updated membership
            member = await self.members_collection.find_one({"member_id": member_id})
            member_doc = ClubMemberDocument(**member)

            # Update club member count
            await self.clubs_collection.update_one(
                {"club_id": member_doc.club_id},
                {"$inc": {"member_count": 1}}
            )

            # Update university member count
            club = await self.clubs_collection.find_one({"club_id": member_doc.club_id})
            await self.universities_collection.update_one(
                {"university_id": club["university_id"]},
                {"$inc": {"total_members": 1}}
            )

            # If assigned to vertical, update vertical member count
            if member_doc.vertical_id:
                await self.verticals_collection.update_one(
                    {"vertical_id": member_doc.vertical_id},
                    {"$inc": {"member_count": 1}}
                )

            # Clear caches
            await self._clear_club_cache(member_doc.club_id)

            # TODO: Send acceptance notification
            # await self._send_acceptance_notification(member_doc)

            self.logger.info("Accepted invitation: %s for user %s in club %s",
                           member_id, user_id, member_doc.club_id)
            return member_doc

        except Exception as e:
            self.logger.error("Failed to accept invitation: %s", e, exc_info=True)
            raise

    async def get_user_clubs(self, user_id: str) -> List[ClubDocument]:
        """Get all clubs where user is a member."""
        try:
            # Get clubs where user is owner
            owned_clubs = []
            async for club in self.clubs_collection.find({"owner_id": user_id, "is_active": True}):
                owned_clubs.append(ClubDocument(**club))

            # Get clubs where user is a member
            member_clubs = []
            async for membership in self.members_collection.find({
                "user_id": user_id,
                "is_active": True
            }):
                club = await self.clubs_collection.find_one({
                    "club_id": membership["club_id"],
                    "is_active": True
                })
                if club and club not in owned_clubs:
                    member_clubs.append(ClubDocument(**club))

            return owned_clubs + member_clubs

        except Exception as e:
            self.logger.error("Failed to get user clubs for %s: %s", user_id, e, exc_info=True)
            raise

    async def get_club_by_slug(self, university_id: str, slug: str) -> Optional[ClubDocument]:
        """Get club by slug within university."""
        try:
            # Check cache first
            cache_key = f"club:university:{university_id}:slug:{slug}"
            cached = await self.redis.get(cache_key)
            if cached:
                return ClubDocument.parse_raw(cached)

            # Query database
            club = await self.clubs_collection.find_one({
                "university_id": university_id,
                "slug": slug,
                "is_active": True
            })

            if club:
                club_doc = ClubDocument(**club)
                # Cache for 1 hour
                await self.redis.setex(cache_key, 3600, club_doc.model_dump_json())
                return club_doc

            return None

        except Exception as e:
            self.logger.error("Failed to get club by slug: %s", e, exc_info=True)
            raise

    async def check_club_access(
        self,
        user_id: str,
        club_id: str,
        required_role: ClubRole = ClubRole.MEMBER
    ) -> Optional[ClubMemberDocument]:
        """Check if user has access to club with required role."""
        try:
            # Check if user is owner
            club = await self.clubs_collection.find_one({
                "club_id": club_id,
                "owner_id": user_id,
                "is_active": True
            })
            if club:
                return ClubMemberDocument(
                    member_id=f"owner_{club_id}",
                    club_id=club_id,
                    user_id=user_id,
                    role=ClubRole.OWNER,
                    invited_by=user_id,
                    invited_at=club["created_at"],
                    joined_at=club["created_at"],
                    is_active=True
                )

            # Check membership
            membership = await self.members_collection.find_one({
                "club_id": club_id,
                "user_id": user_id,
                "is_active": True
            })

            if membership:
                member_doc = ClubMemberDocument(**membership)
                # Check role hierarchy
                role_hierarchy = {
                    ClubRole.MEMBER: 0,
                    ClubRole.LEAD: 1,
                    ClubRole.ADMIN: 2,
                    ClubRole.OWNER: 3
                }

                user_level = role_hierarchy.get(member_doc.role, 0)
                required_level = role_hierarchy.get(required_role, 0)

                if user_level >= required_level:
                    return member_doc

            return None

        except Exception as e:
            self.logger.error("Failed to check club access: %s", e, exc_info=True)
            raise

    async def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        import re
        # Convert to lowercase, replace spaces and special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[\s_-]+', '-', slug)
        return slug.strip('-')

    async def _ensure_unique_club_slug(self, university_id: str, base_slug: str) -> str:
        """Ensure club slug is unique within university."""
        slug = base_slug
        counter = 1

        while await self.clubs_collection.find_one({
            "university_id": university_id,
            "slug": slug
        }):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    async def _clear_university_cache(self, university_id: str):
        """Clear all cache keys for a university."""
        try:
            pattern = f"university:{university_id}:*"
            # Note: In production, you'd want to use Redis SCAN or a more sophisticated cache clearing
            await self.redis.delete(pattern)
        except Exception as e:
            self.logger.warning("Failed to clear university cache: %s", e)

    async def _clear_club_cache(self, club_id: str):
        """Clear all cache keys for a club."""
        try:
            pattern = f"club:{club_id}:*"
            await self.redis.delete(pattern)
        except Exception as e:
            self.logger.warning("Failed to clear club cache: %s", e)