"""
Family management routes for user relationships and shared resources.

This module provides REST API endpoints for family management including:
- Family creation and management
- Member invitations and relationship management
- SBD token account integration
- Family limits and usage tracking

All endpoints require authentication and follow the established security patterns.
"""

from typing import List, Optional

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
    Invite a user to join a family by email address or username.
    
    Sends an email invitation to the specified user with accept/decline links.
    Only family administrators can send invitations.
    
    **Rate Limiting:** 10 invitations per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Family must not have reached member limit
    - Invitee must exist in the system (by email or username)
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
            family_id, user_id, invite_request.identifier, invite_request.relationship_type,
            invite_request.identifier_type, {"request": request}
        )
        
        logger.info("Family invitation sent: %s to %s (%s) for family %s", 
                   invitation_data["invitation_id"], invite_request.identifier, 
                   invite_request.identifier_type, family_id)
        
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


@router.get("/invitation/{invitation_token}/accept")
async def accept_invitation_by_token(
    request: Request,
    invitation_token: str
) -> JSONResponse:
    """
    Accept a family invitation using the email token link.
    
    This endpoint is accessed via email links and doesn't require authentication.
    The token provides the necessary security and user identification.
    
    **Rate Limiting:** 10 requests per hour per IP
    
    **Returns:**
    - Success message and family information
    - Redirect information for the user to log in
    """
    # Apply IP-based rate limiting for unauthenticated endpoint
    await security_manager.check_rate_limit(
        request,
        f"invitation_accept_token_{request.client.host}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        response_data = await family_manager.respond_to_invitation_by_token(
            invitation_token, "accept"
        )
        
        logger.info("Family invitation accepted via token: %s", invitation_token[:8] + "...")
        
        return JSONResponse(
            content={
                "status": "success",
                "action": "accepted",
                "message": response_data["message"],
                "family_id": response_data.get("family_id"),
                "redirect_url": "/login?message=invitation_accepted",
                "data": response_data
            },
            status_code=status.HTTP_200_OK
        )
        
    except InvitationNotFound as e:
        logger.warning("Invitation token not found or expired: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "INVITATION_NOT_FOUND",
                "message": str(e),
                "redirect_url": "/login?error=invitation_invalid"
            }
        )
    except FamilyError as e:
        logger.error("Family invitation acceptance failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVITATION_FAILED",
                "message": str(e),
                "redirect_url": "/login?error=invitation_failed"
            }
        )


@router.get("/invitation/{invitation_token}/decline")
async def decline_invitation_by_token(
    request: Request,
    invitation_token: str
) -> JSONResponse:
    """
    Decline a family invitation using the email token link.
    
    This endpoint is accessed via email links and doesn't require authentication.
    The token provides the necessary security and user identification.
    
    **Rate Limiting:** 10 requests per hour per IP
    
    **Returns:**
    - Success message confirming the decline
    """
    # Apply IP-based rate limiting for unauthenticated endpoint
    await security_manager.check_rate_limit(
        request,
        f"invitation_decline_token_{request.client.host}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        response_data = await family_manager.respond_to_invitation_by_token(
            invitation_token, "decline"
        )
        
        logger.info("Family invitation declined via token: %s", invitation_token[:8] + "...")
        
        return JSONResponse(
            content={
                "status": "success",
                "action": "declined",
                "message": response_data["message"],
                "redirect_url": "/login?message=invitation_declined"
            },
            status_code=status.HTTP_200_OK
        )
        
    except InvitationNotFound as e:
        logger.warning("Invitation token not found or expired: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "INVITATION_NOT_FOUND",
                "message": str(e),
                "redirect_url": "/login?error=invitation_invalid"
            }
        )
    except FamilyError as e:
        logger.error("Family invitation decline failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVITATION_FAILED",
                "message": str(e),
                "redirect_url": "/login?error=invitation_failed"
            }
        )


@router.get("/{family_id}/invitations", response_model=List[InvitationResponse])
async def get_family_invitations(
    request: Request,
    family_id: str,
    status: Optional[str] = None,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> List[InvitationResponse]:
    """
    Get all invitations for a family.
    
    Only family administrators can view invitations.
    Optionally filter by status (pending, accepted, declined, expired).
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    
    **Returns:**
    - List of family invitations with details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_invitations_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        invitations = await family_manager.get_family_invitations(family_id, user_id, status)
        
        logger.debug("Retrieved %d invitations for family %s", len(invitations), family_id)
        
        invitation_responses = []
        for invitation in invitations:
            invitation_responses.append(InvitationResponse(
                invitation_id=invitation["invitation_id"],
                family_name="",  # Will be filled by the response model
                inviter_username=invitation["inviter_username"],
                relationship_type=invitation["relationship_type"],
                status=invitation["status"],
                expires_at=invitation["expires_at"],
                created_at=invitation["created_at"]
            ))
        
        return invitation_responses
        
    except FamilyNotFound:
        logger.warning("Family not found for invitations: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for viewing invitations: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get family invitations: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INVITATIONS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve invitations"
            }
        )


@router.post("/{family_id}/invitations/{invitation_id}/resend")
async def resend_invitation(
    request: Request,
    family_id: str,
    invitation_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Resend a family invitation email.
    
    Only family administrators can resend invitations.
    Can only resend pending, non-expired invitations.
    
    **Rate Limiting:** 5 resends per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Invitation must be pending and not expired
    
    **Returns:**
    - Resend confirmation and status
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"invitation_resend_{user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )
    
    try:
        resend_data = await family_manager.resend_invitation(invitation_id, user_id)
        
        logger.info("Invitation resent: %s by admin %s", invitation_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": resend_data["message"],
                "email_sent": resend_data["email_sent"],
                "resent_at": resend_data["resent_at"].isoformat()
            },
            status_code=status.HTTP_200_OK
        )
        
    except InvitationNotFound as e:
        logger.warning("Invitation not found for resend: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "INVITATION_NOT_FOUND",
                "message": str(e)
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for invitation resend: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to resend invitation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "RESEND_FAILED",
                "message": str(e)
            }
        )


@router.delete("/{family_id}/invitations/{invitation_id}")
async def cancel_invitation(
    request: Request,
    family_id: str,
    invitation_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Cancel a pending family invitation.
    
    Only family administrators can cancel invitations.
    Can only cancel pending invitations.
    
    **Rate Limiting:** 10 cancellations per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Invitation must be pending
    
    **Returns:**
    - Cancellation confirmation
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"invitation_cancel_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        cancel_data = await family_manager.cancel_invitation(invitation_id, user_id)
        
        logger.info("Invitation cancelled: %s by admin %s", invitation_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": cancel_data["message"],
                "cancelled_at": cancel_data["cancelled_at"].isoformat()
            },
            status_code=status.HTTP_200_OK
        )
        
    except InvitationNotFound as e:
        logger.warning("Invitation not found for cancellation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "INVITATION_NOT_FOUND",
                "message": str(e)
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for invitation cancellation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to cancel invitation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "CANCELLATION_FAILED",
                "message": str(e)
            }
        )


@router.post("/admin/cleanup-expired-invitations")
async def cleanup_expired_invitations(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Clean up expired family invitations (admin only).
    
    This endpoint manually triggers the cleanup of expired invitations.
    Normally this would be handled by a scheduled task.
    
    **Rate Limiting:** 2 requests per hour per user
    
    **Requirements:**
    - User must be authenticated (no specific admin check for now)
    
    **Returns:**
    - Cleanup statistics and results
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"invitation_cleanup_{user_id}",
        rate_limit_requests=2,
        rate_limit_period=3600
    )
    
    try:
        cleanup_data = await family_manager.cleanup_expired_invitations()
        
        logger.info("Manual invitation cleanup triggered by user %s", user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Invitation cleanup completed",
                "expired_count": cleanup_data["expired_count"],
                "cleaned_count": cleanup_data["cleaned_count"],
                "total_processed": cleanup_data["total_processed"],
                "timestamp": cleanup_data["timestamp"].isoformat()
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyError as e:
        logger.error("Failed to cleanup expired invitations: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "CLEANUP_FAILED",
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