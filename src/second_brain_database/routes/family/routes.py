"""
Family management routes for user relationships and shared resources.

This module provides REST API endpoints for family management including:
- Family creation and management
- Member invitations and relationship management
- SBD token account integration
- Family limits and usage tracking

All endpoints require authentication and follow the established security patterns.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from second_brain_database.managers.family_manager import (
    FamilyError,
    FamilyLimitExceeded,
    FamilyNotFound,
    InsufficientPermissions,
    InvalidRelationship,
    InvitationNotFound,
    family_manager,
)
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.routes.family.models import (
    CreateFamilyRequest,
    FamilyLimitsResponse,
    FamilyResponse,
    InviteMemberRequest,
    InvitationResponse,
    RespondToInvitationRequest,
)

logger = get_logger(prefix="[Family Routes]")

router = APIRouter(prefix="/family", tags=["Family"])


@router.post("/create", response_model=FamilyResponse, status_code=status.HTTP_201_CREATED)
async def create_family(
    request: Request,
    family_request: CreateFamilyRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> FamilyResponse:
    """
    Create a new family with the current user as administrator.
    
    The user automatically becomes the family administrator and can invite other members.
    A virtual SBD token account is created for the family with the format "family_[name]".
    
    **Rate Limiting:** 5 requests per hour per user
    
    **Requirements:**
    - User must not have reached their maximum family limit
    - Family name must be unique (if provided)
    
    **Returns:**
    - Family information including ID, name, and SBD account details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, 
        f"family_create_{user_id}", 
        rate_limit_requests=5, 
        rate_limit_period=3600
    )
    
    try:
        family_data = await family_manager.create_family(user_id, family_request.name)
        
        logger.info("Family created successfully: %s by user %s", 
                   family_data["family_id"], user_id)
        
        return FamilyResponse(
            family_id=family_data["family_id"],
            name=family_data["name"],
            admin_user_ids=family_data["admin_user_ids"],
            member_count=family_data["member_count"],
            created_at=family_data["created_at"],
            is_admin=True,
            sbd_account=family_data["sbd_account"],
            usage_stats={
                "current_members": family_data["member_count"],
                "max_members_allowed": 5,  # Default limit
                "can_add_members": True
            }
        )
        
    except FamilyLimitExceeded as e:
        logger.warning("Family creation failed - limit exceeded for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "FAMILY_LIMIT_EXCEEDED",
                "message": str(e),
                "upgrade_required": True
            }
        )
    except FamilyError as e:
        logger.error("Family creation failed for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "FAMILY_CREATION_FAILED",
                "message": str(e)
            }
        )


@router.get("/my-families", response_model=List[FamilyResponse])
async def get_my_families(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> List[FamilyResponse]:
    """
    Get all families that the current user belongs to.
    
    Returns comprehensive family information including the user's role,
    SBD account details, and member statistics.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Returns:**
    - List of families with detailed information
    - Empty list if user belongs to no families
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_list_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        families = await family_manager.get_user_families(user_id)
        
        logger.debug("Retrieved %d families for user %s", len(families), user_id)
        
        family_responses = []
        for family in families:
            family_responses.append(FamilyResponse(
                family_id=family["family_id"],
                name=family["name"],
                admin_user_ids=family["admin_user_ids"],
                member_count=family["member_count"],
                created_at=family["created_at"],
                is_admin=family["is_admin"],
                sbd_account=family["sbd_account"],
                usage_stats={
                    "current_members": family["member_count"],
                    "max_members_allowed": 5,  # Default limit
                    "can_add_members": family["is_admin"]
                }
            ))
        
        return family_responses
        
    except FamilyError as e:
        logger.error("Failed to get families for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "FAMILY_RETRIEVAL_FAILED",
                "message": "Failed to retrieve family information"
            }
        )


@router.post("/{family_id}/invite", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_family_member(
    request: Request,
    family_id: str,
    invite_request: InviteMemberRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> InvitationResponse:
    """
    Invite a user to join a family by email address.
    
    Sends an email invitation to the specified user with accept/decline links.
    Only family administrators can send invitations.
    
    **Rate Limiting:** 10 invitations per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Family must not have reached member limit
    - Invitee must exist in the system
    - Invitee must not already be a family member
    
    **Returns:**
    - Invitation details including expiration time
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_invite_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        invitation_data = await family_manager.invite_member(
            family_id, user_id, invite_request.email, invite_request.relationship_type
        )
        
        logger.info("Family invitation sent: %s to %s for family %s", 
                   invitation_data["invitation_id"], invite_request.email, family_id)
        
        return InvitationResponse(
            invitation_id=invitation_data["invitation_id"],
            family_name=invitation_data["family_name"],
            inviter_username=current_user["username"],
            relationship_type=invitation_data["relationship_type"],
            status="pending",
            expires_at=invitation_data["expires_at"],
            created_at=invitation_data["expires_at"]  # Using expires_at as placeholder
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for invitation: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for family invitation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except InvalidRelationship as e:
        logger.warning("Invalid relationship type in invitation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_RELATIONSHIP",
                "message": str(e)
            }
        )
    except FamilyLimitExceeded as e:
        logger.warning("Family member limit exceeded: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "MEMBER_LIMIT_EXCEEDED",
                "message": str(e),
                "upgrade_required": True
            }
        )
    except FamilyError as e:
        logger.error("Family invitation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVITATION_FAILED",
                "message": str(e)
            }
        )


@router.post("/invitation/{invitation_id}/respond")
async def respond_to_invitation(
    request: Request,
    invitation_id: str,
    response_request: RespondToInvitationRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Respond to a family invitation (accept or decline).
    
    Only the invited user can respond to their own invitations.
    Accepting creates a bidirectional family relationship.
    
    **Rate Limiting:** 20 responses per hour per user
    
    **Requirements:**
    - User must be the invitation recipient
    - Invitation must be pending and not expired
    
    **Returns:**
    - Response status and family information (if accepted)
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_invitation_response_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        response_data = await family_manager.respond_to_invitation(
            invitation_id, user_id, response_request.action
        )
        
        logger.info("Family invitation %s: %s by user %s", 
                   response_request.action, invitation_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "action": response_request.action,
                "message": response_data["message"],
                "data": response_data
            },
            status_code=status.HTTP_200_OK
        )
        
    except InvitationNotFound as e:
        logger.warning("Invitation not found or expired: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "INVITATION_NOT_FOUND",
                "message": str(e)
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for invitation response: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Family invitation response failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "RESPONSE_FAILED",
                "message": str(e)
            }
        )


@router.get("/limits", response_model=FamilyLimitsResponse)
async def get_family_limits(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> FamilyLimitsResponse:
    """
    Get the current user's family limits and usage information.
    
    Returns information about family creation limits, member limits,
    and current usage statistics for billing integration.
    
    **Rate Limiting:** 30 requests per hour per user
    
    **Returns:**
    - Current limits and usage statistics
    - Upgrade requirements and recommendations
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_limits_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )
    
    try:
        limits_data = await family_manager.check_family_limits(user_id)
        
        logger.debug("Retrieved family limits for user %s", user_id)
        
        return FamilyLimitsResponse(
            max_families_allowed=limits_data["max_families_allowed"],
            max_members_per_family=limits_data["max_members_per_family"],
            current_families=limits_data["current_families"],
            families_usage=limits_data["families_usage"],
            can_create_family=limits_data["can_create_family"],
            upgrade_required=limits_data["upgrade_required"]
        )
        
    except FamilyError as e:
        logger.error("Failed to get family limits for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "LIMITS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve family limits"
            }
        )