"""
Tenant management routes for multi-tenancy support.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.dependencies import get_current_user_dep
from second_brain_database.routes.auth.services.auth.login import create_access_token
from second_brain_database.routes.tenants.models import (
    AddTenantMemberRequest,
    CreateTenantRequest,
    SwitchTenantRequest,
    TenantMemberResponse,
    TenantMemberRole,
    TenantPlan,
    TenantResponse,
    UpdateTenantRequest,
)

logger = get_logger(prefix="[Tenant Routes]")

router = APIRouter(prefix="/tenants", tags=["tenants"])


# Plan-based resource limits
PLAN_LIMITS = {
    TenantPlan.FREE: {
        "max_users": settings.FREE_PLAN_MAX_USERS,
        "max_storage_gb": 1,
        "max_api_calls_per_day": 1000,
    },
    TenantPlan.PRO: {
        "max_users": settings.PRO_PLAN_MAX_USERS,
        "max_storage_gb": 50,
        "max_api_calls_per_day": 50000,
    },
    TenantPlan.ENTERPRISE: {
        "max_users": settings.ENTERPRISE_PLAN_MAX_USERS,
        "max_storage_gb": -1,  # unlimited
        "max_api_calls_per_day": -1,  # unlimited
    },
}


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    req: CreateTenantRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Create a new tenant.
    
    The current user becomes the owner of the new tenant.
    """
    try:
        tenants_collection = db_manager.get_collection("tenants")
        users_collection = db_manager.get_collection("users")
        
        # Check if slug is already taken
        existing = await tenants_collection.find_one({"slug": req.slug})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tenant slug '{req.slug}' is already taken"
            )
        
        # Get plan limits
        limits = PLAN_LIMITS.get(req.plan, PLAN_LIMITS[TenantPlan.FREE])
        
        # Create tenant document
        tenant_id = f"tenant_{req.slug}"
        tenant_doc = {
            "_id": tenant_id,
            "tenant_id": tenant_id,
            "name": req.name,
            "slug": req.slug,
            "plan": req.plan.value,
            "description": req.description,
            "owner_user_id": str(current_user["_id"]),
            "member_count": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            **limits,
        }
        
        await tenants_collection.insert_one(tenant_doc)
        logger.info(f"Created tenant: {tenant_id} by user {current_user['username']}")
        
        # Add tenant membership to user
        await users_collection.update_one(
            {"_id": current_user["_id"]},
            {
                "$push": {
                    "tenant_memberships": {
                        "tenant_id": tenant_id,
                        "role": TenantMemberRole.OWNER.value,
                        "joined_at": datetime.utcnow(),
                    }
                }
            }
        )
        
        return {
            "success": True,
            "data": TenantResponse(**tenant_doc).dict(),
            "message": f"Tenant '{req.name}' created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create tenant: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tenant"
        )


@router.get("/current", response_model=dict)
async def get_current_tenant(current_user: dict = Depends(get_current_user_dep)):
    """Get current tenant information."""
    try:
        tenant_id = current_user.get("current_tenant_id")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active tenant"
            )
        
        tenants_collection = db_manager.get_collection("tenants")
        tenant = await tenants_collection.find_one({"tenant_id": tenant_id})
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        return {
            "success": True,
            "data": TenantResponse(**tenant).dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get current tenant: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get current tenant"
        )


@router.post("/switch", response_model=dict)
async def switch_tenant(
    req: SwitchTenantRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Switch to a different tenant.
    
    Returns a new JWT token with the updated primary tenant.
    """
    try:
        # Verify user has access to target tenant
        tenant_memberships = current_user.get("tenant_memberships", [])
        has_access = any(
            membership.get("tenant_id") == req.tenant_id
            for membership in tenant_memberships
        )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to tenant"
            )
        
        # Update user's primary tenant
        users_collection = db_manager.get_collection("users")
        await users_collection.update_one(
            {"_id": current_user["_id"]},
            {"$set": {"primary_tenant_id": req.tenant_id}}
        )
        
        logger.info(
            f"User {current_user['username']} switched to tenant {req.tenant_id}"
        )
        
        # Generate new JWT with updated tenant
        new_token = await create_access_token({"sub": current_user["username"]})
        
        return {
            "success": True,
            "access_token": new_token,
            "token_type": "bearer",
            "message": "Tenant switched successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to switch tenant: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to switch tenant"
        )


@router.get("/my", response_model=dict)
async def get_my_tenants(current_user: dict = Depends(get_current_user_dep)):
    """Get all tenants user has access to."""
    try:
        tenant_memberships = current_user.get("tenant_memberships", [])
        tenant_ids = [m.get("tenant_id") for m in tenant_memberships]
        
        tenants_collection = db_manager.get_collection("tenants")
        tenants = await tenants_collection.find(
            {"tenant_id": {"$in": tenant_ids}}
        ).to_list(length=100)
        
        # Add user's role to each tenant
        for tenant in tenants:
            membership = next(
                (m for m in tenant_memberships if m.get("tenant_id") == tenant["tenant_id"]),
                None
            )
            tenant["user_role"] = membership.get("role") if membership else None
        
        return {
            "success": True,
            "data": [TenantResponse(**t).dict() for t in tenants]
        }
        
    except Exception as e:
        logger.error(f"Failed to get user tenants: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tenants"
        )


@router.get("/{tenant_id}", response_model=dict)
async def get_tenant(
    tenant_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """Get tenant information by ID."""
    try:
        # Verify user has access
        tenant_memberships = current_user.get("tenant_memberships", [])
        has_access = any(
            m.get("tenant_id") == tenant_id for m in tenant_memberships
        )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to tenant"
            )
        
        tenants_collection = db_manager.get_collection("tenants")
        tenant = await tenants_collection.find_one({"tenant_id": tenant_id})
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        return {
            "success": True,
            "data": TenantResponse(**tenant).dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tenant"
        )


@router.put("/{tenant_id}", response_model=dict)
async def update_tenant(
    tenant_id: str,
    req: UpdateTenantRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """Update tenant information. Requires owner or admin role."""
    try:
        # Verify user has admin access
        tenant_memberships = current_user.get("tenant_memberships", [])
        membership = next(
            (m for m in tenant_memberships if m.get("tenant_id") == tenant_id),
            None
        )
        
        if not membership or membership.get("role") not in [
            TenantMemberRole.OWNER.value,
            TenantMemberRole.ADMIN.value
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requires owner or admin role"
            )
        
        # Build update document
        update_data = {"updated_at": datetime.utcnow()}
        if req.name:
            update_data["name"] = req.name
        if req.description is not None:
            update_data["description"] = req.description
        if req.plan:
            update_data["plan"] = req.plan.value
            # Update limits based on new plan
            limits = PLAN_LIMITS.get(req.plan, PLAN_LIMITS[TenantPlan.FREE])
            update_data.update(limits)
        
        tenants_collection = db_manager.get_collection("tenants")
        result = await tenants_collection.update_one(
            {"tenant_id": tenant_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        logger.info(f"Updated tenant {tenant_id} by user {current_user['username']}")
        
        # Get updated tenant
        tenant = await tenants_collection.find_one({"tenant_id": tenant_id})
        
        return {
            "success": True,
            "data": TenantResponse(**tenant).dict(),
            "message": "Tenant updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update tenant: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tenant"
        )
