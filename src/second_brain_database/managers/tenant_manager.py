"""
Tenant Manager for multi-tenancy operations.

This module provides the TenantManager class for managing tenants,
memberships, and tenant-scoped operations following established
manager patterns in the codebase.
"""

import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.tenant_models import (
    CreateTenantRequest,
    InviteUserToTenantRequest,
    TenantDocument,
    TenantMembershipDocument,
    UpdateMembershipRequest,
    UpdateTenantRequest,
)

logger = get_logger(prefix="[Tenant Manager]")


class TenantManager:
    """Manager for tenant operations and multi-tenancy."""

    def __init__(self):
        """Initialize the TenantManager."""
        self.tenants_collection_name = "tenants"
        self.memberships_collection_name = "tenant_memberships"

    async def create_tenant(
        self, request: CreateTenantRequest, owner_user_id: str
    ) -> Dict[str, Any]:
        """
        Create a new tenant.

        Args:
            request: Tenant creation request
            owner_user_id: ID of the user who will own the tenant

        Returns:
            Dict containing the created tenant information

        Raises:
            ValueError: If slug is already taken
            PyMongoError: If database operation fails
        """
        logger.info("Creating tenant: %s for owner: %s", request.name, owner_user_id)

        try:
            # Generate tenant ID
            tenant_id = f"tenant_{secrets.token_hex(8)}"

            # Generate slug if not provided
            slug = request.slug or self._generate_slug(request.name)

            # Check if slug is unique
            tenants_collection = db_manager.get_collection(self.tenants_collection_name)
            existing = await tenants_collection.find_one({"slug": slug})
            if existing:
                raise ValueError(f"Tenant slug '{slug}' is already taken")

            # Get plan limits
            plan_limits = self._get_plan_limits(request.plan)

            # Create tenant document
            now = datetime.utcnow()
            tenant_doc = {
                "tenant_id": tenant_id,
                "name": request.name,
                "slug": slug,
                "plan": request.plan,
                "status": "active",
                "description": request.description,
                "owner_user_id": owner_user_id,
                "settings": {
                    "max_users": plan_limits["max_users"],
                    "max_storage_gb": plan_limits["max_storage_gb"],
                    "features_enabled": plan_limits["features_enabled"],
                    "custom_domain": None,
                },
                "billing": {
                    "subscription_id": None,
                    "current_period_start": now,
                    "current_period_end": None,
                },
                "member_count": 1,  # Owner is the first member
                "created_at": now,
                "updated_at": now,
            }

            # Insert tenant
            await tenants_collection.insert_one(tenant_doc)

            # Create owner membership
            await self._create_membership(
                tenant_id=tenant_id,
                user_id=owner_user_id,
                role="owner",
                status="active",
                invited_by=None,
            )

            # Update user's primary tenant if not set
            await self._set_user_primary_tenant_if_needed(owner_user_id, tenant_id)

            logger.info("Successfully created tenant: %s (ID: %s)", request.name, tenant_id)
            return tenant_doc

        except DuplicateKeyError as e:
            logger.error("Duplicate key error creating tenant: %s", e)
            raise ValueError("Tenant with this slug already exists")
        except Exception as e:
            logger.error("Failed to create tenant: %s", e, exc_info=True)
            raise

    async def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant by ID.

        Args:
            tenant_id: The tenant ID

        Returns:
            Tenant document or None if not found
        """
        try:
            tenants_collection = db_manager.get_collection(self.tenants_collection_name)
            tenant = await tenants_collection.find_one({"tenant_id": tenant_id})
            return tenant
        except Exception as e:
            logger.error("Failed to get tenant %s: %s", tenant_id, e)
            return None

    async def get_user_tenants(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all tenants a user belongs to.

        Args:
            user_id: The user ID

        Returns:
            List of tenant documents with membership information
        """
        try:
            # Get user's memberships
            memberships_collection = db_manager.get_collection(self.memberships_collection_name)
            memberships = await memberships_collection.find(
                {"user_id": user_id, "status": "active"}
            ).to_list(length=None)

            if not memberships:
                return []

            # Get tenant details
            tenant_ids = [m["tenant_id"] for m in memberships]
            tenants_collection = db_manager.get_collection(self.tenants_collection_name)
            tenants = await tenants_collection.find({"tenant_id": {"$in": tenant_ids}}).to_list(length=None)

            # Combine tenant and membership info
            membership_map = {m["tenant_id"]: m for m in memberships}
            for tenant in tenants:
                membership = membership_map.get(tenant["tenant_id"])
                if membership:
                    tenant["user_role"] = membership["role"]
                    tenant["user_permissions"] = membership["permissions"]

            return tenants

        except Exception as e:
            logger.error("Failed to get tenants for user %s: %s", user_id, e, exc_info=True)
            return []

    async def add_user_to_tenant(
        self, request: InviteUserToTenantRequest, tenant_id: str, invited_by: str
    ) -> Dict[str, Any]:
        """
        Add a user to a tenant.

        Args:
            request: Invitation request
            tenant_id: The tenant ID
            invited_by: ID of the user sending the invitation

        Returns:
            Membership document

        Raises:
            ValueError: If user is already a member or tenant is at capacity
        """
        logger.info("Adding user %s to tenant %s", request.user_id, tenant_id)

        try:
            # Check if user is already a member
            memberships_collection = db_manager.get_collection(self.memberships_collection_name)
            existing = await memberships_collection.find_one(
                {"tenant_id": tenant_id, "user_id": request.user_id}
            )
            if existing:
                raise ValueError("User is already a member of this tenant")

            # Check tenant capacity
            tenant = await self.get_tenant(tenant_id)
            if not tenant:
                raise ValueError("Tenant not found")

            max_users = tenant["settings"]["max_users"]
            if max_users != -1 and tenant["member_count"] >= max_users:
                raise ValueError("Tenant has reached maximum user capacity")

            # Create membership
            membership = await self._create_membership(
                tenant_id=tenant_id,
                user_id=request.user_id,
                role=request.role,
                status="active",
                invited_by=invited_by,
            )

            # Increment member count
            tenants_collection = db_manager.get_collection(self.tenants_collection_name)
            await tenants_collection.update_one(
                {"tenant_id": tenant_id},
                {"$inc": {"member_count": 1}, "$set": {"updated_at": datetime.utcnow()}},
            )

            logger.info("Successfully added user %s to tenant %s", request.user_id, tenant_id)
            return membership

        except Exception as e:
            logger.error("Failed to add user to tenant: %s", e, exc_info=True)
            raise

    async def remove_user_from_tenant(self, tenant_id: str, user_id: str) -> bool:
        """
        Remove a user from a tenant.

        Args:
            tenant_id: The tenant ID
            user_id: The user ID to remove

        Returns:
            True if successful

        Raises:
            ValueError: If user is the owner
        """
        try:
            # Check if user is the owner
            memberships_collection = db_manager.get_collection(self.memberships_collection_name)
            membership = await memberships_collection.find_one(
                {"tenant_id": tenant_id, "user_id": user_id}
            )

            if not membership:
                raise ValueError("User is not a member of this tenant")

            if membership["role"] == "owner":
                raise ValueError("Cannot remove the owner. Transfer ownership first.")

            # Delete membership
            await memberships_collection.delete_one({"membership_id": membership["membership_id"]})

            # Decrement member count
            tenants_collection = db_manager.get_collection(self.tenants_collection_name)
            await tenants_collection.update_one(
                {"tenant_id": tenant_id},
                {"$inc": {"member_count": -1}, "$set": {"updated_at": datetime.utcnow()}},
            )

            logger.info("Successfully removed user %s from tenant %s", user_id, tenant_id)
            return True

        except Exception as e:
            logger.error("Failed to remove user from tenant: %s", e, exc_info=True)
            raise

    async def switch_tenant(self, user_id: str, tenant_id: str) -> bool:
        """
        Switch user's active/primary tenant.

        Args:
            user_id: The user ID
            tenant_id: The tenant ID to switch to

        Returns:
            True if successful

        Raises:
            ValueError: If user is not a member of the tenant
        """
        try:
            # Verify user is a member
            memberships_collection = db_manager.get_collection(self.memberships_collection_name)
            membership = await memberships_collection.find_one(
                {"tenant_id": tenant_id, "user_id": user_id, "status": "active"}
            )

            if not membership:
                raise ValueError("User is not an active member of this tenant")

            # Update user's primary tenant
            users_collection = db_manager.get_collection("users")
            await users_collection.update_one(
                {"_id": ObjectId(user_id)}, {"$set": {"primary_tenant_id": tenant_id}}
            )

            logger.info("User %s switched to tenant %s", user_id, tenant_id)
            return True

        except Exception as e:
            logger.error("Failed to switch tenant: %s", e, exc_info=True)
            raise

    async def get_tenant_limits(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant resource limits based on plan.

        Args:
            tenant_id: The tenant ID

        Returns:
            Dict containing limit information
        """
        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant:
                raise ValueError("Tenant not found")

            return {
                "plan": tenant["plan"],
                "max_users": tenant["settings"]["max_users"],
                "max_storage_gb": tenant["settings"]["max_storage_gb"],
                "current_users": tenant["member_count"],
                "current_storage_gb": 0,  # TODO: Calculate actual storage
                "features_enabled": tenant["settings"]["features_enabled"],
                "can_upgrade": tenant["plan"] != "enterprise",
                "upgrade_required_for": [],
            }

        except Exception as e:
            logger.error("Failed to get tenant limits: %s", e, exc_info=True)
            raise

    # Helper methods

    async def _create_membership(
        self,
        tenant_id: str,
        user_id: str,
        role: str,
        status: str,
        invited_by: Optional[str],
    ) -> Dict[str, Any]:
        """Create a tenant membership."""
        membership_id = f"mem_{secrets.token_hex(8)}"
        now = datetime.utcnow()

        permissions = self._get_role_permissions(role)

        membership_doc = {
            "membership_id": membership_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": role,
            "status": status,
            "permissions": permissions,
            "invited_by": invited_by,
            "invited_at": now if invited_by else None,
            "joined_at": now,
            "created_at": now,
            "updated_at": now,
        }

        memberships_collection = db_manager.get_collection(self.memberships_collection_name)
        await memberships_collection.insert_one(membership_doc)

        return membership_doc

    async def _set_user_primary_tenant_if_needed(self, user_id: str, tenant_id: str) -> None:
        """Set user's primary tenant if not already set."""
        try:
            users_collection = db_manager.get_collection("users")
            user = await users_collection.find_one({"_id": ObjectId(user_id)})

            if user and not user.get("primary_tenant_id"):
                await users_collection.update_one(
                    {"_id": ObjectId(user_id)}, {"$set": {"primary_tenant_id": tenant_id}}
                )
                logger.debug("Set primary tenant for user %s: %s", user_id, tenant_id)

        except Exception as e:
            logger.warning("Failed to set primary tenant for user: %s", e)

    def _generate_slug(self, name: str) -> str:
        """Generate a URL-friendly slug from name."""
        slug = name.lower().strip()
        slug = slug.replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        slug = slug[:50]  # Limit length
        return slug

    def _get_plan_limits(self, plan: str) -> Dict[str, Any]:
        """Get resource limits for a plan."""
        limits = {
            "free": {
                "max_users": settings.FREE_PLAN_MAX_USERS,
                "max_storage_gb": settings.FREE_PLAN_MAX_STORAGE_GB,
                "features_enabled": ["workspaces", "skills", "chat"],
            },
            "pro": {
                "max_users": settings.PRO_PLAN_MAX_USERS,
                "max_storage_gb": settings.PRO_PLAN_MAX_STORAGE_GB,
                "features_enabled": ["workspaces", "families", "skills", "chat", "blog"],
            },
            "enterprise": {
                "max_users": settings.ENTERPRISE_PLAN_MAX_USERS,
                "max_storage_gb": settings.ENTERPRISE_PLAN_MAX_STORAGE_GB,
                "features_enabled": [
                    "workspaces",
                    "families",
                    "skills",
                    "chat",
                    "blog",
                    "ipam",
                    "custom_domain",
                ],
            },
        }
        return limits.get(plan, limits["free"])

    def _get_role_permissions(self, role: str) -> Dict[str, bool]:
        """Get default permissions for a role."""
        permissions = {
            "owner": {
                "can_invite_users": True,
                "can_manage_billing": True,
                "can_access_audit_logs": True,
            },
            "admin": {
                "can_invite_users": True,
                "can_manage_billing": False,
                "can_access_audit_logs": True,
            },
            "member": {
                "can_invite_users": False,
                "can_manage_billing": False,
                "can_access_audit_logs": False,
            },
            "viewer": {
                "can_invite_users": False,
                "can_manage_billing": False,
                "can_access_audit_logs": False,
            },
        }
        return permissions.get(role, permissions["viewer"])


# Global instance
tenant_manager = TenantManager()
