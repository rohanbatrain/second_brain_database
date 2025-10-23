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
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from second_brain_database.managers.family_manager import (
    AccountFrozen,
    AdminActionError,
    BackupAdminError,
    FamilyError,
    FamilyLimitExceeded,
    FamilyNotFound,
    InsufficientPermissions,
    InvalidRelationship,
    InvitationNotFound,
    MultipleAdminsRequired,
    RateLimitExceeded,
    TokenRequestNotFound,
    ValidationError,
    family_manager,
)
from second_brain_database.utils.error_handling import (
    ErrorContext, ErrorSeverity, create_user_friendly_error, sanitize_sensitive_data
)
from second_brain_database.utils.error_monitoring import record_error_event
from second_brain_database.managers.family_audit_manager import (
    FamilyAuditError,
    ComplianceReportError,
    family_audit_manager,
)
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.routes.family.models import (
    AdminActionLogEntry,
    AdminActionRequest,
    AdminActionResponse,
    AdminActionsLogRequest,
    AdminActionsLogResponse,
    BackupAdminRequest,
    BackupAdminResponse,
    CreateFamilyRequest,
    CreateTokenRequestRequest,
    FamilyLimitsResponse,
    FamilyResponse,
    FreezeAccountRequest,
    InitiateRecoveryRequest,
    InviteMemberRequest,
    InvitationResponse,
    LimitEnforcementResponse,
    MarkNotificationsReadRequest,
    NotificationListResponse,
    NotificationPreferencesResponse,
    ReceivedInvitationResponse,
    RecoveryInitiationResponse,
    RecoveryVerificationResponse,
    RespondToInvitationRequest,
    ReviewTokenRequestRequest,
    SBDAccountResponse,
    TokenRequestResponse,
    UpdateNotificationPreferencesRequest,
    UpdateFamilyLimitsRequest,
    UpdateFamilyLimitsResponse,
    UpdateSpendingPermissionsRequest,
    UsageTrackingResponse,
    VerifyRecoveryRequest,
    ModifyRelationshipRequest,
    ModifyRelationshipResponse,
    RelationshipDetailsResponse,
)
from second_brain_database.models.family_models import DenyPurchaseRequest, FamilyMemberResponse, PurchaseRequestResponse

# Import health check router
from second_brain_database.routes.family.health import router as health_router

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
    
    # Create error context for comprehensive error handling
    error_context = ErrorContext(
        operation="create_family_api",
        user_id=user_id,
        request_id=getattr(request.state, "request_id", None) if hasattr(request, "state") else None,
        ip_address=getattr(request.client, "host", "unknown") if request.client else "unknown",
        metadata={
            "family_name": family_request.name,
            "endpoint": "/family/create"
        }
    )
    
    try:
        # Pass request context for rate limiting and security
        request_context = {
            "request": request,
            "request_id": error_context.request_id,
            "ip_address": error_context.ip_address
        }
        
        family_data = await family_manager.create_family(
            user_id, 
            family_request.name,
            request_context
        )
        
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
        # Record error for monitoring
        await record_error_event(e, error_context, ErrorSeverity.HIGH)
        
        logger.warning("Family creation failed - limit exceeded for user %s: %s", user_id, e)
        
        # Check if error has user-friendly response from error handling system
        if hasattr(e, 'user_friendly_response'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.user_friendly_response['error']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "FAMILY_LIMIT_EXCEEDED",
                    "message": str(e),
                    "upgrade_required": True
                }
            )
            
    except ValidationError as e:
        # Record error for monitoring
        await record_error_event(e, error_context, ErrorSeverity.MEDIUM)
        
        logger.warning("Family creation failed - validation error for user %s: %s", user_id, e)
        
        # Create user-friendly error response
        user_friendly_error = create_user_friendly_error(e, error_context)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=user_friendly_error['error']
        )
        
    except RateLimitExceeded as e:
        # Record error for monitoring
        await record_error_event(e, error_context, ErrorSeverity.HIGH)
        
        logger.warning("Family creation failed - rate limit exceeded for user %s: %s", user_id, e)
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": "You are creating families too quickly. Please wait and try again.",
                "retry_after": 3600  # 1 hour
            }
        )
        
    except FamilyError as e:
        # Record error for monitoring
        await record_error_event(e, error_context, ErrorSeverity.HIGH)
        
        logger.error("Family creation failed for user %s: %s", user_id, e)
        
        # Check if error has user-friendly response from error handling system
        if hasattr(e, 'user_friendly_response'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.user_friendly_response['error']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "FAMILY_CREATION_FAILED",
                    "message": str(e)
                }
            )
            
    except Exception as e:
        # Record unexpected error for monitoring
        await record_error_event(e, error_context, ErrorSeverity.CRITICAL)
        
        logger.error("Unexpected error in family creation for user %s: %s", user_id, e, exc_info=True)
        
        # Create user-friendly error response for unexpected errors
        user_friendly_error = create_user_friendly_error(e, error_context)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=user_friendly_error['error']
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


@router.get(
    "/wallet/purchase-requests",
    response_model=List[PurchaseRequestResponse],
    tags=["Family Wallet"],
    summary="Get pending purchase requests",
)
async def get_purchase_requests(
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get purchase requests for a family.
    - Admins can see all requests for their family.
    - Members can only see their own requests.
    """
    user_id = str(current_user["_id"])
    try:
        requests = await family_manager.get_purchase_requests(family_id=family_id, user_id=user_id)
        return requests
    except FamilyError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/wallet/purchase-requests/{request_id}/approve",
    response_model=PurchaseRequestResponse,
    tags=["Family Wallet"],
    summary="Approve a purchase request",
)
async def approve_purchase_request(
    request_id: str,
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Approve a family member's purchase request.
    - Only admins can approve requests.
    - Approving a request will trigger the purchase and deduct tokens from the family wallet.
    """
    admin_id = str(current_user["_id"])
    req_id = str(uuid.uuid4())
    request_context = {
        "request": request,
        "request_id": req_id,
        "ip_address": request.client.host,
    }
    try:
        approved_request = await family_manager.approve_purchase_request(
            request_id=request_id, admin_id=admin_id, request_context=request_context
        )
        return approved_request
    except InsufficientPermissions as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FamilyError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/wallet/purchase-requests/{request_id}/deny",
    response_model=PurchaseRequestResponse,
    tags=["Family Wallet"],
    summary="Deny a purchase request",
)
async def deny_purchase_request(
    request_id: str,
    request: Request,
    body: DenyPurchaseRequest,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Deny a family member's purchase request.
    - Only admins can deny requests.
    """
    admin_id = str(current_user["_id"])
    req_id = str(uuid.uuid4())
    request_context = {
        "request": request,
        "request_id": req_id,
        "ip_address": request.client.host,
    }
    try:
        denied_request = await family_manager.deny_purchase_request(
            request_id=request_id, admin_id=admin_id, reason=body.reason, request_context=request_context
        )
        return denied_request
    except InsufficientPermissions as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FamilyError as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/my-invitations",
    response_model=List[ReceivedInvitationResponse],
    summary="Get received family invitations",
    description="""
    Retrieve all family invitations received by the current authenticated user.
    
    This endpoint returns invitations where the current user is the invitee,
    matching either by user ID or email address. Useful for implementing an
    in-app "Received Invitations" screen where users can see pending family
    invitations and accept/decline them directly.
    
    **Key Features:**
    - Returns invitations sent TO the authenticated user
    - Includes complete family and inviter information
    - Supports filtering by invitation status
    - Sorted by creation date (newest first)
    
    **Use Cases:**
    - Display pending family invitations in mobile app
    - Show invitation history (accepted/declined/expired)
    - Implement in-app invitation management
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Next Steps:**
    After retrieving invitations, users can:
    - Accept: POST /family/invitations/{invitation_id}/respond with action="accept"
    - Decline: POST /family/invitations/{invitation_id}/respond with action="decline"
    
    **Response Details:**
    - `invitation_id`: Use this to accept/decline the invitation
    - `family_id`: ID of the family you're invited to join
    - `family_name`: Human-readable name of the family
    - `inviter_username`: Who sent you the invitation
    - `relationship_type`: Your proposed role (parent, child, sibling, etc.)
    - `status`: Current state (pending, accepted, declined, expired, cancelled)
    - `expires_at`: When invitation becomes invalid
    - `invitation_token`: Optional token for email-based acceptance
    """,
    responses={
        200: {
            "description": "Successfully retrieved invitations",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "invitation_id": "inv_abc123xyz789",
                            "family_id": "fam_def456uvw012",
                            "family_name": "Johnson Family",
                            "inviter_user_id": "user_123abc",
                            "inviter_username": "john_johnson",
                            "relationship_type": "child",
                            "status": "pending",
                            "expires_at": "2025-10-28T14:30:00Z",
                            "created_at": "2025-10-21T14:30:00Z",
                            "invitation_token": "tok_xyz789abc123"
                        }
                    ]
                }
            }
        },
        401: {
            "description": "Unauthorized - Invalid or missing authentication token"
        },
        429: {
            "description": "Rate limit exceeded - Too many requests"
        },
        500: {
            "description": "Internal server error - Failed to retrieve invitations"
        }
    },
    tags=["Family Invitations"]
)
async def get_my_invitations(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
    status: Optional[str] = Query(
        None,
        description="Filter by invitation status",
        example="pending",
        pattern="^(pending|accepted|declined|expired|cancelled)$"
    ),
) -> List[ReceivedInvitationResponse]:
    """
    Get invitations received by the current authenticated user.

    Returns a list of invitations sent to the user (by invitee_user_id or invitee_email).
    Includes complete family and inviter information for each invitation.
    """
    user_id = str(current_user["_id"])
    user_email = current_user.get("email")

    # Validate status parameter
    if status and status not in ["pending", "accepted", "declined", "expired", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_STATUS_FILTER",
                "message": f"Invalid status '{status}'. Must be one of: pending, accepted, declined, expired, cancelled"
            }
        )

    # Rate limit: 60 requests per hour for listing received invitations (increased)
    await security_manager.check_rate_limit(
        request,
        f"received_invitations_{user_id}",
        rate_limit_requests=60,
        rate_limit_period=3600
    )

    try:
        invitations = await family_manager.get_received_invitations(
            user_id=user_id,
            user_email=user_email,
            status_filter=status
        )
        
        # Filter invitations based on required conditions:
        # 1. Has recipient info (invitee_email OR invitee_username)
        # 2. Has inviter OR family info (inviter_username not "Unknown" OR family_name not "Unknown Family")
        # 3. Not in bad expired state: if expired and status is not pending, skip it
        
        filtered_invitations = []
        for invitation in invitations:
            # Check recipient info
            invitee_email = invitation.get("invitee_email") or ""
            invitee_username = invitation.get("invitee_username") or ""
            has_recipient_info = (invitee_email.strip() != "") or (invitee_username.strip() != "")
            
            # Check inviter OR family info
            inviter_username = invitation.get("inviter_username", "Unknown")
            family_name = invitation.get("family_name", "Unknown Family")
            has_inviter_or_family_info = (
                (inviter_username and inviter_username != "Unknown") or
                (family_name and family_name != "Unknown Family")
            )
            
            # Check expired state
            invitation_status = invitation.get("status", "")
            expires_at = invitation.get("expires_at")
            is_expired = False
            if expires_at:
                from datetime import datetime, timezone
                # Handle both aware and naive datetimes
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                is_expired = datetime.now(timezone.utc) > expires_at
            
            # If expired and status is not pending, skip this invitation
            if is_expired and invitation_status != "pending":
                logger.debug("Skipping invitation %s: expired with non-pending status %s", 
                           invitation.get("invitation_id"), invitation_status)
                continue
            
            # Apply all required conditions
            if not (has_recipient_info and has_inviter_or_family_info):
                logger.debug("Skipping invitation %s: missing required fields (recipient=%s, inviter/family=%s)", 
                           invitation.get("invitation_id"), has_recipient_info, has_inviter_or_family_info)
                continue
            
            filtered_invitations.append(invitation)
        
        logger.info(
            "User %s retrieved %d received invitations (%d passed validation, status_filter=%s)",
            user_id, len(filtered_invitations), len(invitations), status or "all"
        )
        
        return [ReceivedInvitationResponse(**inv) for inv in filtered_invitations]
        
    except FamilyError as e:
        logger.error(
            "Failed to fetch received invitations for user %s: %s",
            user_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "FAILED_TO_FETCH_INVITATIONS",
                "message": "Unable to retrieve family invitations. Please try again later."
            }
        )
    except Exception as e:
        logger.error(
            "Unexpected error fetching received invitations for user %s: %s",
            user_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later."
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
            invitee_email=invitation_data.get("invitee_email"),
            invitee_username=invitation_data.get("invitee_username"),
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
    status_filter: Optional[str] = None,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> List[InvitationResponse]:
    """
    Get all invitations for a family.
    
    Only family administrators can view invitation details.
    Non-admin family members will receive an empty list.
    Optionally filter by status (pending, accepted, declined, expired).
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must be a member of the family
    
    **Returns:**
    - List of family invitations with details (admins only)
    - Empty list for non-admin members
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
        invitations = await family_manager.get_family_invitations(family_id, user_id, status_filter)
        
        logger.debug("Retrieved %d invitations for family %s", len(invitations), family_id)
        
        invitation_responses = []
        for invitation in invitations:
            # Filter invitations based on required conditions:
            # 1. Has recipient info (invitee_email OR invitee_username)
            invitee_email = invitation.get("invitee_email") or ""
            invitee_username = invitation.get("invitee_username") or ""
            has_recipient_info = (invitee_email.strip() != "") or (invitee_username.strip() != "")
            
            # 2. Has inviter OR family info (inviter_username not "Unknown" OR family_name not "Unknown Family")
            inviter_username = invitation.get("inviter_username", "Unknown")
            family_name = invitation.get("family_name", "Unknown Family")
            has_inviter_or_family_info = (
                (inviter_username and inviter_username != "Unknown") or
                (family_name and family_name != "Unknown Family")
            )
            
            # 3. Not in bad expired state: if expired and status is not pending, skip it
            invitation_status = invitation.get("status", "")
            expires_at = invitation.get("expires_at")
            is_expired = False
            if expires_at:
                from datetime import datetime, timezone
                # Handle both aware and naive datetimes
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                is_expired = datetime.now(timezone.utc) > expires_at
            
            # If expired and status is not pending, skip this invitation
            if is_expired and invitation_status != "pending":
                logger.debug("Skipping invitation %s: expired with non-pending status %s", 
                           invitation["invitation_id"], invitation_status)
                continue
            
            # Apply all required conditions
            if not (has_recipient_info and has_inviter_or_family_info):
                logger.debug("Skipping invitation %s: missing required fields (recipient=%s, inviter/family=%s)", 
                           invitation["invitation_id"], has_recipient_info, has_inviter_or_family_info)
                continue
            
            invitation_responses.append(InvitationResponse(
                invitation_id=invitation["invitation_id"],
                family_name=family_name,
                inviter_username=inviter_username,
                invitee_email=invitation.get("invitee_email"),
                invitee_username=invitation.get("invitee_username"),
                relationship_type=invitation["relationship_type"],
                status=invitation["status"],
                expires_at=invitation["expires_at"],
                created_at=invitation["created_at"]
            ))
        
        logger.info("Filtered invitations: %d out of %d passed validation for family %s", 
                   len(invitation_responses), len(invitations), family_id)
        
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
        logger.info("User %s does not have admin permissions to view invitations for family %s, returning empty list", user_id, family_id)
        # Return empty list instead of 403 to allow graceful handling in client
        return []
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


@router.post("/{family_id}/members/{user_id}/admin", response_model=AdminActionResponse)
async def manage_admin_role(
    request: Request,
    family_id: str,
    user_id: str,
    admin_request: AdminActionRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> AdminActionResponse:
    """
    Promote a member to admin or demote an admin to member.
    
    Only family administrators can perform admin role changes.
    Prevents demoting the last administrator to ensure family continuity.
    
    **Rate Limiting:** 5 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Target user must be a family member
    - Cannot demote the last administrator
    - Cannot promote someone who is already an admin
    
    **Returns:**
    - Admin action confirmation and details
    """
    admin_user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"admin_action_{admin_user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )
    
    try:
        if admin_request.action == "promote":
            result = await family_manager.promote_to_admin(
                family_id, admin_user_id, user_id, {"request": request}
            )
            
            # Get user info for response
            target_user = await family_manager._get_user_by_id(user_id)
            
            logger.info("User promoted to admin: %s by %s in family %s", 
                       user_id, admin_user_id, family_id)
            
            return AdminActionResponse(
                family_id=result["family_id"],
                target_user_id=result["target_user_id"],
                target_username=target_user.get("username", "Unknown"),
                action=result["action"],
                new_role=result["new_role"],
                performed_by=result["promoted_by"],
                performed_by_username=current_user["username"],
                performed_at=result["promoted_at"],
                message=result["message"],
                transaction_safe=result["transaction_safe"]
            )
            
        elif admin_request.action == "demote":
            result = await family_manager.demote_from_admin(
                family_id, admin_user_id, user_id, {"request": request}
            )
            
            # Get user info for response
            target_user = await family_manager._get_user_by_id(user_id)
            
            logger.info("Admin demoted to member: %s by %s in family %s", 
                       user_id, admin_user_id, family_id)
            
            return AdminActionResponse(
                family_id=result["family_id"],
                target_user_id=result["target_user_id"],
                target_username=target_user.get("username", "Unknown"),
                action=result["action"],
                new_role=result["new_role"],
                performed_by=result["demoted_by"],
                performed_by_username=current_user["username"],
                performed_at=result["demoted_at"],
                message=result["message"],
                transaction_safe=result["transaction_safe"]
            )
            
    except FamilyNotFound:
        logger.warning("Family not found for admin action: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for admin action: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except AdminActionError as e:
        logger.warning("Admin action validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ADMIN_ACTION_ERROR",
                "message": str(e)
            }
        )
    except MultipleAdminsRequired as e:
        logger.warning("Multiple admins required for action: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "MULTIPLE_ADMINS_REQUIRED",
                "message": str(e),
                "minimum_admins_required": 2
            }
        )
    except FamilyError as e:
        logger.error("Admin action failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ADMIN_ACTION_FAILED",
                "message": str(e)
            }
        )


@router.post("/{family_id}/members/{user_id}/backup-admin", response_model=BackupAdminResponse)
async def manage_backup_admin(
    request: Request,
    family_id: str,
    user_id: str,
    backup_request: BackupAdminRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> BackupAdminResponse:
    """
    Designate or remove a backup administrator.
    
    Backup administrators can be promoted to full admin status in case
    of emergency or if all current admins become unavailable.
    
    **Rate Limiting:** 5 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Target user must be a family member
    - Target user cannot already be an admin
    
    **Returns:**
    - Backup admin action confirmation and details
    """
    admin_user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"backup_admin_{admin_user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )
    
    try:
        if backup_request.action == "designate":
            result = await family_manager.designate_backup_admin(
                family_id, admin_user_id, user_id, {"request": request}
            )
            
            # Get user info for response
            target_user = await family_manager._get_user_by_id(user_id)
            
            logger.info("Backup admin designated: %s by %s in family %s", 
                       user_id, admin_user_id, family_id)
            
            return BackupAdminResponse(
                family_id=result["family_id"],
                backup_user_id=result["backup_user_id"],
                backup_username=target_user.get("username", "Unknown"),
                action=result["action"],
                role=result["role"],
                performed_by=result["designated_by"],
                performed_by_username=current_user["username"],
                performed_at=result["designated_at"],
                message=result["message"],
                transaction_safe=result["transaction_safe"]
            )
            
        elif backup_request.action == "remove":
            result = await family_manager.remove_backup_admin(
                family_id, admin_user_id, user_id, {"request": request}
            )
            
            # Get user info for response
            target_user = await family_manager._get_user_by_id(user_id)
            
            logger.info("Backup admin removed: %s by %s in family %s", 
                       user_id, admin_user_id, family_id)
            
            return BackupAdminResponse(
                family_id=result["family_id"],
                backup_user_id=result["backup_user_id"],
                backup_username=target_user.get("username", "Unknown"),
                action=result["action"],
                role=result["role"],
                performed_by=result["removed_by"],
                performed_by_username=current_user["username"],
                performed_at=result["removed_at"],
                message=result["message"],
                transaction_safe=result["transaction_safe"]
            )
            
    except FamilyNotFound:
        logger.warning("Family not found for backup admin action: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for backup admin action: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except family_manager.BackupAdminError as e:
        logger.warning("Backup admin action validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "BACKUP_ADMIN_ERROR",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Backup admin action failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "BACKUP_ADMIN_ACTION_FAILED",
                "message": str(e)
            }
        )


@router.get("/{family_id}/admin-actions", response_model=AdminActionsLogResponse)
async def get_admin_actions_log(
    request: Request,
    family_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> AdminActionsLogResponse:
    """
    Get the admin actions log for a family.
    
    Returns a paginated list of all administrative actions performed
    in the family, including promotions, demotions, and backup admin changes.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    
    **Returns:**
    - Paginated list of admin actions with details
    """
    admin_user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"admin_log_{admin_user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    # Validate pagination parameters
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_LIMIT",
                "message": "Limit must be between 1 and 100"
            }
        )
    
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_OFFSET",
                "message": "Offset must be non-negative"
            }
        )
    
    try:
        result = await family_manager.get_admin_actions_log(
            family_id, admin_user_id, limit, offset
        )
        
        logger.debug("Retrieved admin actions log for family %s", family_id)
        
        # Convert to response model
        log_entries = []
        for action in result["actions"]:
            log_entries.append(AdminActionLogEntry(
                action_id=action["action_id"],
                family_id=action["family_id"],
                admin_user_id=action["admin_user_id"],
                admin_username=action["admin_username"],
                target_user_id=action["target_user_id"],
                target_username=action["target_username"],
                action_type=action["action_type"],
                details=action["details"],
                created_at=action["created_at"],
                ip_address=action.get("ip_address"),
                user_agent=action.get("user_agent")
            ))
        
        return AdminActionsLogResponse(
            family_id=result["family_id"],
            actions=log_entries,
            pagination=result["pagination"]
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for admin actions log: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for admin actions log: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get admin actions log: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ADMIN_LOG_RETRIEVAL_FAILED",
                "message": "Failed to retrieve admin actions log"
            }
        )


@router.get("/limits", response_model=FamilyLimitsResponse)
async def get_family_limits(
    request: Request,
    include_billing_metrics: bool = False,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> FamilyLimitsResponse:
    """
    Get the current user's family limits and usage information.
    
    Returns comprehensive information about family creation limits, member limits,
    current usage statistics, and billing integration data.
    
    **Rate Limiting:** 30 requests per hour per user
    
    **Parameters:**
    - include_billing_metrics: Include detailed billing metrics in response
    
    **Returns:**
    - Current limits and usage statistics
    - Detailed limit status and enforcement information
    - Upgrade requirements and recommendations
    - Optional billing metrics for usage tracking
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
        # Get comprehensive limits data with billing metrics if requested
        limits_data = await family_manager.check_family_limits(
            user_id, 
            include_billing_metrics=include_billing_metrics
        )
        
        logger.debug(
            "Retrieved family limits for user %s (billing_metrics=%s)", 
            user_id, include_billing_metrics
        )
        
        return FamilyLimitsResponse(
            max_families_allowed=limits_data["max_families_allowed"],
            max_members_per_family=limits_data["max_members_per_family"],
            current_families=limits_data["current_families"],
            families_usage=limits_data["families_usage"],
            can_create_family=limits_data["can_create_family"],
            upgrade_required=limits_data["upgrade_required"],
            limit_status=limits_data["limit_status"],
            billing_metrics=limits_data.get("billing_metrics"),
            upgrade_messaging=limits_data["upgrade_messaging"]
        )
        
    except FamilyError as e:
        logger.error("Failed to get family limits for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "LIMITS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve family limits",
                "context": {"user_id": user_id}
            }
        )


@router.get("/usage-tracking", response_model=UsageTrackingResponse)
async def get_usage_tracking_data(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = "daily",
    current_user: dict = Depends(enforce_all_lockdowns)
) -> UsageTrackingResponse:
    """
    Get family usage tracking data for billing integration.
    
    Returns detailed usage metrics over a specified time period for billing
    and analytics purposes. This endpoint provides comprehensive data about
    family creation, member additions, and usage patterns.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Parameters:**
    - start_date: Start date in ISO format (defaults to 30 days ago)
    - end_date: End date in ISO format (defaults to now)
    - granularity: Data granularity - "daily", "weekly", or "monthly"
    
    **Returns:**
    - Usage tracking data and metrics
    - Peak usage statistics
    - Billing recommendations
    - Historical usage patterns
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting for usage tracking (more restrictive)
    await security_manager.check_rate_limit(
        request,
        f"family_usage_tracking_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        from datetime import datetime, timezone, timedelta
        
        # Parse date parameters
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_DATE_FORMAT",
                        "message": "start_date must be in ISO format"
                    }
                )
        else:
            start_dt = datetime.now(timezone.utc) - timedelta(days=30)
            
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_DATE_FORMAT",
                        "message": "end_date must be in ISO format"
                    }
                )
        else:
            end_dt = datetime.now(timezone.utc)
        
        # Validate granularity
        if granularity not in ["daily", "weekly", "monthly"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_GRANULARITY",
                    "message": "granularity must be 'daily', 'weekly', or 'monthly'"
                }
            )
        
        # Get usage tracking data
        usage_data = await family_manager.get_usage_tracking_data(
            user_id, start_dt, end_dt, granularity
        )
        
        logger.debug(
            "Retrieved usage tracking data for user %s (period: %s to %s, granularity: %s)", 
            user_id, start_dt.isoformat(), end_dt.isoformat(), granularity
        )
        
        return UsageTrackingResponse(**usage_data)
        
    except FamilyError as e:
        logger.error("Failed to get usage tracking data for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "USAGE_TRACKING_FAILED",
                "message": "Failed to retrieve usage tracking data",
                "context": {"user_id": user_id}
            }
        )


@router.put("/limits", response_model=UpdateFamilyLimitsResponse)
async def update_family_limits(
    request: Request,
    limits_update: UpdateFamilyLimitsRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> UpdateFamilyLimitsResponse:
    """
    Update family limits for the current user.
    
    This endpoint allows updating family limits, typically used by billing
    systems or administrators to adjust user limits based on subscription changes.
    
    **Rate Limiting:** 5 requests per hour per user
    
    **Parameters:**
    - max_families_allowed: New maximum families allowed
    - max_members_per_family: New maximum members per family
    - validate_existing: Whether to validate existing families against new limits
    
    **Returns:**
    - Updated limits information
    - Validation results for existing families
    - Enforcement status
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting for limit updates (more restrictive)
    await security_manager.check_rate_limit(
        request,
        f"family_limits_update_{user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )
    
    try:
        # Prepare new limits dict
        new_limits = {}
        if limits_update.max_families_allowed is not None:
            new_limits["max_families_allowed"] = limits_update.max_families_allowed
        if limits_update.max_members_per_family is not None:
            new_limits["max_members_per_family"] = limits_update.max_members_per_family
        
        # Update family limits
        update_result = await family_manager.update_family_limits(
            user_id,
            new_limits,
            updated_by=user_id,
            reason="User-initiated limits update"
        )
        
        logger.info(
            "Updated family limits for user %s: families=%d, members=%d", 
            user_id, limits_update.max_families_allowed, limits_update.max_members_per_family
        )
        
        return UpdateFamilyLimitsResponse(**update_result)
        
    except FamilyError as e:
        logger.error("Failed to update family limits for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "LIMITS_UPDATE_FAILED",
                "message": str(e),
                "context": {"user_id": user_id}
            }
        )


@router.get("/limits/enforcement", response_model=LimitEnforcementResponse)
async def get_limit_enforcement_status(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> LimitEnforcementResponse:
    """
    Get detailed limit enforcement status and validation results.
    
    Returns comprehensive information about current limit enforcement,
    including validation results for existing families and grace periods.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Returns:**
    - Current enforcement status
    - Validation results for existing families
    - Grace period information
    - Compliance recommendations
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_limit_enforcement_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        # Get limit enforcement status
        enforcement_status = await family_manager.get_limit_enforcement_status(user_id)
        
        logger.debug("Retrieved limit enforcement status for user %s", user_id)
        
        return LimitEnforcementResponse(**enforcement_status)
        
    except FamilyError as e:
        logger.error("Failed to get limit enforcement status for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ENFORCEMENT_STATUS_FAILED",
                "message": "Failed to retrieve limit enforcement status",
                "context": {"user_id": user_id}
            }
        )


@router.post("/{family_id}/account/freeze")
async def freeze_family_account(
    request: Request,
    family_id: str,
    freeze_request: FreezeAccountRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Freeze or unfreeze the family SBD account.
    
    Only family administrators can freeze/unfreeze the account.
    Freezing prevents all spending from the family account while allowing deposits.
    
    **Rate Limiting:** 5 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Account must not already be in the requested state
    
    **Returns:**
    - Freeze/unfreeze confirmation and status
    """
    admin_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_freeze_{admin_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )
    
    try:
        if freeze_request.action == "freeze":
            if not freeze_request.reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "REASON_REQUIRED",
                        "message": "Reason is required when freezing an account"
                    }
                )
            
            result = await family_manager.freeze_family_account(
                family_id, admin_id, freeze_request.reason
            )
            
            logger.info("Family account frozen: %s by admin %s, reason: %s", 
                       family_id, admin_id, freeze_request.reason)
            
            return JSONResponse(
                content={
                    "status": "success",
                    "action": "frozen",
                    "message": "Family account has been frozen successfully",
                    "frozen_by": admin_id,
                    "frozen_by_username": current_user["username"],
                    "frozen_at": result["frozen_at"].isoformat(),
                    "reason": result["freeze_reason"],
                    "data": result
                },
                status_code=status.HTTP_200_OK
            )
            
        elif freeze_request.action == "unfreeze":
            result = await family_manager.unfreeze_family_account(family_id, admin_id)
            
            logger.info("Family account unfrozen: %s by admin %s", family_id, admin_id)
            
            return JSONResponse(
                content={
                    "status": "success",
                    "action": "unfrozen",
                    "message": "Family account has been unfrozen successfully",
                    "unfrozen_by": admin_id,
                    "unfrozen_by_username": current_user["username"],
                    "unfrozen_at": result["unfrozen_at"].isoformat(),
                    "data": result
                },
                status_code=status.HTTP_200_OK
            )
            
    except FamilyNotFound:
        logger.warning("Family not found for freeze action: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for freeze action: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Family freeze action failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "FREEZE_ACTION_FAILED",
                "message": str(e)
            }
        )


@router.post("/{family_id}/account/emergency-unfreeze")
async def initiate_emergency_unfreeze(
    request: Request,
    family_id: str,
    emergency_request: dict,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Initiate an emergency unfreeze request for the family account.
    
    Emergency unfreeze allows family members to collaborate to unfreeze an account
    when administrators are unavailable. Requires approval from multiple family members.
    
    **Rate Limiting:** 2 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    - Account must be frozen
    - No other emergency request pending
    
    **Returns:**
    - Emergency request details and approval requirements
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"emergency_unfreeze_{user_id}",
        rate_limit_requests=2,
        rate_limit_period=3600
    )
    
    try:
        reason = emergency_request.get("reason", "Emergency situation")
        
        result = await family_manager.initiate_emergency_unfreeze(
            family_id, user_id, reason
        )
        
        logger.info("Emergency unfreeze initiated: %s by user %s for family %s", 
                   result["request_id"], user_id, family_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Emergency unfreeze request created successfully",
                "request_id": result["request_id"],
                "required_approvals": result["required_approvals"],
                "current_approvals": result["current_approvals"],
                "expires_at": result["expires_at"].isoformat(),
                "data": result
            },
            status_code=status.HTTP_201_CREATED
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for emergency unfreeze: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for emergency unfreeze: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Emergency unfreeze initiation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "EMERGENCY_UNFREEZE_FAILED",
                "message": str(e)
            }
        )


@router.post("/emergency-unfreeze/{request_id}/approve")
async def approve_emergency_unfreeze(
    request: Request,
    request_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Approve an emergency unfreeze request.
    
    Family members can approve emergency unfreeze requests. When enough approvals
    are collected, the account is automatically unfrozen.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    - Request must be pending and not expired
    - User must not have already approved or rejected
    
    **Returns:**
    - Approval status and execution result if threshold met
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"emergency_approve_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        result = await family_manager.approve_emergency_unfreeze(request_id, user_id)
        
        logger.info("Emergency unfreeze approved: %s by user %s", request_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": result.get("message", "Emergency unfreeze approved"),
                "approved": result["approved"],
                "current_approvals": result["current_approvals"],
                "required_approvals": result["required_approvals"],
                "threshold_met": result["threshold_met"],
                "executed": result.get("executed", False),
                "data": result
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyError as e:
        logger.error("Emergency unfreeze approval failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "APPROVAL_FAILED",
                "message": str(e)
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for emergency approval: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )


@router.post("/emergency-unfreeze/{request_id}/reject")
async def reject_emergency_unfreeze(
    request: Request,
    request_id: str,
    rejection_data: dict,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Reject an emergency unfreeze request.
    
    Family members can reject emergency unfreeze requests with an optional reason.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    - Request must be pending and not expired
    - User must not have already approved or rejected
    
    **Returns:**
    - Rejection confirmation
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"emergency_reject_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        reason = rejection_data.get("reason", "No reason provided")
        
        result = await family_manager.reject_emergency_unfreeze(request_id, user_id, reason)
        
        logger.info("Emergency unfreeze rejected: %s by user %s", request_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": result["message"],
                "rejected": result["rejected"],
                "reason": result["reason"],
                "data": result
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyError as e:
        logger.error("Emergency unfreeze rejection failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "REJECTION_FAILED",
                "message": str(e)
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for emergency rejection: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )


@router.get("/{family_id}/emergency-unfreeze")
async def get_emergency_unfreeze_requests(
    request: Request,
    family_id: str,
    status: Optional[str] = None,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Get emergency unfreeze requests for a family.
    
    Returns all emergency unfreeze requests with optional status filtering.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    
    **Returns:**
    - List of emergency requests with details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"emergency_requests_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        requests = await family_manager.get_emergency_unfreeze_requests(
            family_id, user_id, status
        )
        
        logger.debug("Retrieved %d emergency requests for family %s", len(requests), family_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "count": len(requests),
                "requests": requests
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for emergency requests: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for emergency requests: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get emergency requests: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "REQUESTS_RETRIEVAL_FAILED",
                "message": str(e)
            }
        )


# Notification endpoints

@router.get("/{family_id}/notifications", response_model=NotificationListResponse)
async def get_family_notifications(
    request: Request,
    family_id: str,
    limit: int = 20,
    offset: int = 0,
    status_filter: Optional[str] = None,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> NotificationListResponse:
    """
    Get family notifications for the current user with pagination and filtering.
    
    Retrieves notifications sent to the current user for the specified family.
    Supports pagination and filtering by read/unread status.
    
    **Rate Limiting:** 30 requests per minute per user
    
    **Query Parameters:**
    - `limit`: Maximum number of notifications to return (default: 20, max: 100)
    - `offset`: Number of notifications to skip for pagination (default: 0)
    - `status_filter`: Filter by status ("read", "unread", "pending", "sent", "archived")
    
    **Returns:**
    - List of notifications with pagination metadata
    - Unread count for the user
    - Pagination information for next/previous pages
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, 
        f"family_notifications_{user_id}", 
        rate_limit_requests=30,
        rate_limit_period=60
    )
    
    # Validate parameters
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 20
    if offset < 0:
        offset = 0
    
    valid_status_filters = {"read", "unread", "pending", "sent", "archived"}
    if status_filter and status_filter not in valid_status_filters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_STATUS_FILTER",
                "message": f"Status filter must be one of: {', '.join(valid_status_filters)}"
            }
        )
    
    try:
        result = await family_manager.get_family_notifications(
            family_id=family_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
            status_filter=status_filter
        )
        
        logger.info(
            "Retrieved %d notifications for user %s in family %s",
            len(result["notifications"]), user_id, family_id
        )
        
        return NotificationListResponse(**result)
        
    except FamilyNotFound:
        logger.warning("Family not found for notifications: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for notifications: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get family notifications: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "NOTIFICATIONS_RETRIEVAL_FAILED",
                "message": str(e)
            }
        )


@router.post("/{family_id}/notifications/mark-read")
async def mark_notifications_read(
    request: Request,
    family_id: str,
    mark_request: MarkNotificationsReadRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Mark specific notifications as read for the current user.
    
    Updates the read status of specified notifications and decrements the user's
    unread notification count accordingly.
    
    **Rate Limiting:** 20 requests per minute per user
    
    **Request Body:**
    - `notification_ids`: List of notification IDs to mark as read
    
    **Returns:**
    - Number of notifications successfully marked as read
    - List of updated notification IDs
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, 
        f"mark_notifications_read_{user_id}", 
        rate_limit_requests=20,
        rate_limit_period=60
    )
    
    # Validate request
    if not mark_request.notification_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "EMPTY_NOTIFICATION_LIST",
                "message": "At least one notification ID is required"
            }
        )
    
    if len(mark_request.notification_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "TOO_MANY_NOTIFICATIONS",
                "message": "Cannot mark more than 50 notifications at once"
            }
        )
    
    try:
        result = await family_manager.mark_notifications_read(
            family_id=family_id,
            user_id=user_id,
            notification_ids=mark_request.notification_ids
        )
        
        logger.info(
            "Marked %d notifications as read for user %s in family %s",
            result["marked_count"], user_id, family_id
        )
        
        return JSONResponse(
            content={
                "message": f"Successfully marked {result['marked_count']} notifications as read",
                "marked_count": result["marked_count"],
                "updated_notifications": result["updated_notifications"]
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for marking notifications: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for marking notifications: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to mark notifications as read: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "MARK_READ_FAILED",
                "message": str(e)
            }
        )


@router.post("/{family_id}/notifications/mark-all-read")
async def mark_all_notifications_read(
    request: Request,
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Mark all notifications as read for the current user in the specified family.
    
    Updates all unread notifications for the user in the family and resets
    their unread notification count to zero.
    
    **Rate Limiting:** 10 requests per minute per user
    
    **Returns:**
    - Number of notifications marked as read
    - Confirmation message
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, 
        f"mark_all_notifications_read_{user_id}", 
        rate_limit_requests=10,
        rate_limit_period=60
    )
    
    try:
        result = await family_manager.mark_all_notifications_read(
            family_id=family_id,
            user_id=user_id
        )
        
        logger.info(
            "Marked all %d notifications as read for user %s in family %s",
            result["marked_count"], user_id, family_id
        )
        
        return JSONResponse(
            content={
                "message": f"Successfully marked all {result['marked_count']} notifications as read",
                "marked_count": result["marked_count"]
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for marking all notifications: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for marking all notifications: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to mark all notifications as read: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "MARK_ALL_READ_FAILED",
                "message": str(e)
            }
        )


@router.get("/notifications/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> NotificationPreferencesResponse:
    """
    Get notification preferences for the current user.
    
    Retrieves the user's notification delivery preferences and current
    unread notification count across all families.
    
    **Rate Limiting:** 30 requests per minute per user
    
    **Returns:**
    - Current notification preferences (email, push, SMS)
    - Unread notification count
    - Last checked timestamp
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, 
        f"get_notification_preferences_{user_id}", 
        rate_limit_requests=30,
        rate_limit_period=60
    )
    
    try:
        result = await family_manager.get_notification_preferences(user_id=user_id)
        
        logger.debug("Retrieved notification preferences for user %s", user_id)
        
        return NotificationPreferencesResponse(**result)
        
    except FamilyError as e:
        logger.error("Failed to get notification preferences: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "PREFERENCES_RETRIEVAL_FAILED",
                "message": str(e)
            }
        )


@router.put("/notifications/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    request: Request,
    preferences_request: UpdateNotificationPreferencesRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> NotificationPreferencesResponse:
    """
    Update notification preferences for the current user.
    
    Updates the user's notification delivery preferences for email, push notifications,
    and SMS notifications across all family notifications.
    
    **Rate Limiting:** 10 requests per minute per user
    
    **Request Body:**
    - `preferences`: Dictionary of preference settings
      - `email_notifications`: Enable/disable email notifications
      - `push_notifications`: Enable/disable push notifications  
      - `sms_notifications`: Enable/disable SMS notifications
    
    **Returns:**
    - Updated notification preferences
    - Current unread notification count
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, 
        f"update_notification_preferences_{user_id}", 
        rate_limit_requests=10,
        rate_limit_period=60
    )
    
    try:
        # Build preferences dict from individual fields
        preferences = {}
        if preferences_request.email_notifications is not None:
            preferences["email_notifications"] = preferences_request.email_notifications
        if preferences_request.push_notifications is not None:
            preferences["push_notifications"] = preferences_request.push_notifications
        if preferences_request.sms_notifications is not None:
            preferences["sms_notifications"] = preferences_request.sms_notifications
        
        result = await family_manager.update_notification_preferences(
            user_id=user_id,
            preferences=preferences
        )
        
        logger.info(
            "Updated notification preferences for user %s: %s",
            user_id, preferences
        )
        
        # Get full preferences including unread count
        full_result = await family_manager.get_notification_preferences(user_id=user_id)
        
        return NotificationPreferencesResponse(**full_result)
        
    except ValidationError as e:
        logger.warning("Invalid notification preferences: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_PREFERENCES",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to update notification preferences: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "PREFERENCES_UPDATE_FAILED",
                "message": str(e)
            }
        )


# Token Request Endpoints

@router.post("/{family_id}/token-requests", response_model=TokenRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_token_request(
    request: Request,
    family_id: str,
    token_request: CreateTokenRequestRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> TokenRequestResponse:
    """
    Create a token request from the family account.
    
    Family members can request tokens from the shared family account.
    Requests under the auto-approval threshold are processed immediately.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    - Family account must not be frozen
    - Amount must be positive
    - Reason must be at least 5 characters
    
    **Returns:**
    - Token request details including status and expiration
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"token_request_create_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        request_data = await family_manager.create_token_request(
            family_id=family_id,
            user_id=user_id,
            amount=token_request.amount,
            reason=token_request.reason,
            request_context={"request": request}
        )
        
        logger.info(
            "Token request created: %s for %d tokens by user %s in family %s",
            request_data["request_id"], token_request.amount, user_id, family_id
        )
        
        return TokenRequestResponse(
            request_id=request_data["request_id"],
            requester_username=current_user["username"],
            amount=request_data["amount"],
            reason=request_data["reason"],
            status=request_data["status"],
            auto_approved=request_data["auto_approved"],
            created_at=request_data["created_at"],
            expires_at=request_data["expires_at"],
            admin_comments=None
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for token request: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for token request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except AccountFrozen as e:
        logger.warning("Token request blocked - account frozen: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "ACCOUNT_FROZEN",
                "message": str(e),
                "frozen_by": e.context.get("frozen_by"),
                "frozen_at": e.context.get("frozen_at")
            }
        )
    except ValidationError as e:
        logger.warning("Invalid token request data: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": str(e),
                "field": e.context.get("field"),
                "value": e.context.get("value")
            }
        )
    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded for token request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e),
                "retry_after": e.context.get("window_seconds", 3600)
            }
        )
    except FamilyError as e:
        logger.error("Failed to create token request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "TOKEN_REQUEST_FAILED",
                "message": str(e)
            }
        )


@router.get("/{family_id}/token-requests/pending", response_model=List[TokenRequestResponse])
async def get_pending_token_requests(
    request: Request,
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> List[TokenRequestResponse]:
    """
    Get all pending token requests for a family (admin only).
    
    Returns all pending token requests that require admin approval.
    Only family administrators can access this endpoint.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    
    **Returns:**
    - List of pending token requests with requester information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"pending_token_requests_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        pending_requests = await family_manager.get_pending_token_requests(family_id, user_id)
        
        logger.debug("Retrieved %d pending token requests for family %s", len(pending_requests), family_id)
        
        response_requests = []
        for req in pending_requests:
            response_requests.append(TokenRequestResponse(
                request_id=req["request_id"],
                requester_username=req["requester_username"],
                from_user_id=req.get("requester_user_id"),
                from_username=req.get("requester_username"),
                amount=req["amount"],
                reason=req["reason"],
                status=req["status"],
                auto_approved=req["auto_approved"],
                created_at=req["created_at"],
                expires_at=req["expires_at"],
                admin_comments=None
            ))
        
        return response_requests
        
    except FamilyNotFound:
        logger.warning("Family not found for pending requests: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for pending requests: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get pending token requests: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "REQUESTS_RETRIEVAL_FAILED",
                "message": str(e)
            }
        )


@router.post("/{family_id}/token-requests/{request_id}/review")
async def review_token_request(
    request: Request,
    family_id: str,
    request_id: str,
    review_request: ReviewTokenRequestRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Review a token request (approve or deny) - admin only.
    
    Family administrators can approve or deny pending token requests.
    Approved requests automatically transfer tokens to the requester.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Request must be in pending status
    - Request must not be expired
    
    **Returns:**
    - Review confirmation and updated request status
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"token_request_review_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        review_data = await family_manager.review_token_request(
            request_id=request_id,
            admin_id=user_id,
            action=review_request.action,
            comments=review_request.comments,
            request_context={"request": request}
        )
        
        logger.info(
            "Token request %s: %s by admin %s (amount: %d)",
            review_request.action, request_id, user_id, review_data["amount"]
        )
        
        return JSONResponse(
            content={
                "status": "success",
                "action": review_data["action"],
                "request_id": review_data["request_id"],
                "new_status": review_data["status"],
                "reviewed_by": review_data["reviewed_by"],
                "admin_comments": review_data["admin_comments"],
                "reviewed_at": review_data["reviewed_at"].isoformat(),
                "processed_at": review_data["processed_at"].isoformat() if review_data["processed_at"] else None,
                "amount": review_data["amount"],
                "requester_user_id": review_data["requester_user_id"]
            },
            status_code=status.HTTP_200_OK
        )
        
    except TokenRequestNotFound as e:
        logger.warning("Token request not found for review: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "TOKEN_REQUEST_NOT_FOUND",
                "message": str(e),
                "request_id": e.context.get("request_id"),
                "status": e.context.get("status")
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for token request review: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except ValidationError as e:
        logger.warning("Invalid token request review data: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": str(e),
                "field": e.context.get("field"),
                "value": e.context.get("value")
            }
        )
    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded for token request review: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e),
                "retry_after": e.context.get("window_seconds", 3600)
            }
        )
    except FamilyError as e:
        logger.error("Failed to review token request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "REVIEW_FAILED",
                "message": str(e)
            }
        )


@router.get("/{family_id}/token-requests/my-requests", response_model=List[TokenRequestResponse])
async def get_my_token_requests(
    request: Request,
    family_id: str,
    limit: int = 20,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> List[TokenRequestResponse]:
    """
    Get the current user's token request history for a family.
    
    Returns the user's token requests in reverse chronological order,
    including pending, approved, denied, and expired requests.
    
    **Rate Limiting:** 30 requests per hour per user
    
    **Query Parameters:**
    - `limit`: Maximum number of requests to return (default: 20, max: 100)
    
    **Requirements:**
    - User must be a family member
    
    **Returns:**
    - List of user's token requests with status and admin comments
    """
    user_id = str(current_user["_id"])
    
    # Validate limit parameter
    if limit > 100:
        limit = 100
    elif limit < 1:
        limit = 20
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"my_token_requests_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )
    
    try:
        user_requests = await family_manager.get_user_token_requests(family_id, user_id, limit)
        
        logger.debug("Retrieved %d token requests for user %s in family %s", 
                    len(user_requests), user_id, family_id)
        
        response_requests = []
        for req in user_requests:
            response_requests.append(TokenRequestResponse(
                request_id=req["request_id"],
                requester_username=current_user["username"],
                amount=req["amount"],
                reason=req["reason"],
                status=req["status"],
                auto_approved=req["auto_approved"],
                created_at=req["created_at"],
                expires_at=req["expires_at"],
                admin_comments=req.get("admin_comments")
            ))
        
        return response_requests
        
    except FamilyNotFound:
        logger.warning("Family not found for user requests: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for user requests: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get user token requests: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "REQUESTS_RETRIEVAL_FAILED",
                "message": str(e)
            }
        )


@router.post("/admin/cleanup-expired-token-requests")
async def cleanup_expired_token_requests(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Clean up expired token requests (admin utility).
    
    This endpoint manually triggers the cleanup of expired token requests.
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
        f"token_request_cleanup_{user_id}",
        rate_limit_requests=2,
        rate_limit_period=3600
    )
    
    try:
        cleanup_data = await family_manager.cleanup_expired_token_requests()
        
        logger.info("Manual token request cleanup triggered by user %s", user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Token request cleanup completed",
                "expired_count": cleanup_data["expired_count"],
                "cleanup_timestamp": cleanup_data["cleanup_timestamp"].isoformat(),
                "requests_processed": cleanup_data["requests_processed"]
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyError as e:
        logger.error("Failed to cleanup expired token requests: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "CLEANUP_FAILED",
                "message": str(e)
            }
        )


# Family Member Management Endpoints

@router.get("/{family_id}", response_model=FamilyResponse)
async def get_family_details(
    request: Request,
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> FamilyResponse:
    """
    Get detailed information about a specific family.
    
    Returns comprehensive family information including member count,
    SBD account details, and the user's role in the family.
    
    **Rate Limiting:** 30 requests per hour per user
    
    **Requirements:**
    - User must be a member of the family
    
    **Returns:**
    - Detailed family information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_details_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )
    
    try:
        family_data = await family_manager.get_family_details(family_id, user_id)
        
        logger.debug("Retrieved family details for %s by user %s", family_id, user_id)
        
        return FamilyResponse(
            family_id=family_data["family_id"],
            name=family_data["name"],
            admin_user_ids=family_data["admin_user_ids"],
            member_count=family_data["member_count"],
            created_at=family_data["created_at"],
            is_admin=family_data["is_admin"],
            sbd_account=family_data["sbd_account"],
            usage_stats=family_data["usage_stats"]
        )
        
    except FamilyNotFound:
        logger.warning("Family not found: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for family details: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get family details: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "FAMILY_DETAILS_FAILED",
                "message": "Failed to retrieve family details"
            }
        )


@router.get("/{family_id}/members", response_model=List[FamilyMemberResponse])
async def get_family_members(
    request: Request,
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> List[FamilyMemberResponse]:
    """
    Get all members of a family with their relationship information.
    
    Returns detailed member information including relationships,
    roles, and spending permissions.
    
    **Rate Limiting:** 3600 requests per hour per user
    
    **Requirements:**
    - User must be a member of the family
    
    **Returns:**
    - List of family members with detailed information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_members_{user_id}",
        rate_limit_requests=3600,
        rate_limit_period=3600
    )
    
    try:
        members_data = await family_manager.get_family_members(family_id, user_id)
        
        logger.debug("Retrieved %d members for family %s", len(members_data), family_id)
        
        member_responses = []
        for member in members_data:
            # Extract primary relationship from the current user's perspective
            # If the current user has a relationship with this member, use it; otherwise use a default
            primary_relationship = "member"  # Default fallback
            if member.get("relationships"):
                # Find relationship with the current user (if any)
                for rel in member["relationships"]:
                    if rel.get("related_user_id") == user_id:
                        primary_relationship = rel.get("relationship_type", "member")
                        break
                # If no direct relationship with current user, use the first relationship
                if primary_relationship == "member" and member["relationships"]:
                    primary_relationship = member["relationships"][0].get("relationship_type", "member")
            
            member_responses.append(FamilyMemberResponse(
                user_id=member["user_id"],
                username=member["username"],
                email=member["email"],
                relationship_type=primary_relationship,
                role=member["role"],
                joined_at=member["joined_at"],
                spending_permissions=member["spending_permissions"]
            ))
        
        return member_responses
        
    except FamilyNotFound:
        logger.warning("Family not found for members: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for family members: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get family members: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "MEMBERS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve family members"
            }
        )


@router.delete("/{family_id}/members/{member_id}")
async def remove_family_member(
    request: Request,
    family_id: str,
    member_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Remove a member from the family.
    
    Only family administrators can remove members.
    Removes all bidirectional relationships and cleans up permissions.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Cannot remove the last administrator
    - Target user must be a family member
    
    **Returns:**
    - Removal confirmation and cleanup details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"remove_member_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        removal_data = await family_manager.remove_family_member(
            family_id, user_id, member_id, {"request": request}
        )
        
        logger.info("Family member removed: %s from %s by admin %s", 
                   member_id, family_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": removal_data["message"],
                "removed_user_id": removal_data["removed_user_id"],
                "removed_username": removal_data["removed_username"],
                "relationships_cleaned": removal_data["relationships_cleaned"],
                "permissions_revoked": removal_data["permissions_revoked"],
                "removed_at": removal_data["removed_at"].isoformat(),
                "transaction_safe": removal_data["transaction_safe"]
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for member removal: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for member removal: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except MultipleAdminsRequired as e:
        logger.warning("Cannot remove last admin: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "MULTIPLE_ADMINS_REQUIRED",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to remove family member: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "MEMBER_REMOVAL_FAILED",
                "message": str(e)
            }
        )


# Relationship Management Endpoints

@router.put("/{family_id}/relationships", response_model=ModifyRelationshipResponse)
async def modify_family_relationship(
    request: Request,
    family_id: str,
    relationship_request: ModifyRelationshipRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> ModifyRelationshipResponse:
    """
    Modify the relationship type between two family members.
    
    Only family administrators can modify relationships. This updates both
    sides of the bidirectional relationship and notifies affected users.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Both users must be family members
    - Relationship must exist and be active
    - New relationship type must be valid
    
    **Returns:**
    - Updated relationship information including old and new types
    """
    admin_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"modify_relationship_{admin_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        result = await family_manager.modify_relationship_type(
            family_id, 
            admin_id, 
            relationship_request.user_a_id,
            relationship_request.user_b_id,
            relationship_request.new_relationship_type,
            {"request": request}
        )
        
        logger.info("Family relationship modified: %s between %s and %s by admin %s", 
                   result["relationship_id"], relationship_request.user_a_id, 
                   relationship_request.user_b_id, admin_id)
        
        return ModifyRelationshipResponse(
            relationship_id=result["relationship_id"],
            family_id=result["family_id"],
            user_a_id=result["user_a_id"],
            user_b_id=result["user_b_id"],
            old_relationship_type=result["old_relationship_type"],
            new_relationship_type=result["new_relationship_type"],
            new_reciprocal_type=result["new_reciprocal_type"],
            modified_by=result["modified_by"],
            modified_at=result["modified_at"],
            transaction_safe=result["transaction_safe"]
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for relationship modification: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for relationship modification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except InvalidRelationship as e:
        logger.warning("Invalid relationship type in modification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_RELATIONSHIP",
                "message": str(e),
                "valid_types": list(e.context.get("valid_types", []))
            }
        )
    except ValidationError as e:
        logger.warning("Validation error in relationship modification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": str(e),
                "field": e.context.get("field"),
                "constraint": e.context.get("constraint")
            }
        )
    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded for relationship modification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e),
                "retry_after": e.context.get("window_seconds", 3600)
            }
        )
    except TransactionError as e:
        logger.error("Transaction error in relationship modification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "TRANSACTION_ERROR",
                "message": "Failed to modify relationship due to database error",
                "rollback_successful": e.context.get("rollback_successful", False)
            }
        )
    except FamilyError as e:
        logger.error("Failed to modify family relationship: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "RELATIONSHIP_MODIFICATION_FAILED",
                "message": str(e)
            }
        )


@router.get("/{family_id}/relationships", response_model=List[RelationshipDetailsResponse])
async def get_family_relationships(
    request: Request,
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> List[RelationshipDetailsResponse]:
    """
    Get all relationships within a family.
    
    Returns detailed information about all family relationships including
    both users' perspectives and relationship metadata.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    
    **Returns:**
    - List of all family relationships with detailed information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"get_relationships_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        relationships = await family_manager.get_family_relationships(family_id, user_id)
        
        logger.debug("Retrieved %d relationships for family %s", len(relationships), family_id)
        
        relationship_responses = []
        for rel in relationships:
            relationship_responses.append(RelationshipDetailsResponse(
                relationship_id=rel["relationship_id"],
                family_id=rel["family_id"],
                user_a=rel["user_a"],
                user_b=rel["user_b"],
                status=rel["status"],
                created_by=rel["created_by"],
                created_at=rel["created_at"],
                updated_at=rel["updated_at"]
            ))
        
        return relationship_responses
        
    except FamilyNotFound:
        logger.warning("Family not found for relationships: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for viewing relationships: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get family relationships: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "RELATIONSHIPS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve relationships"
            }
        )


@router.put("/{family_id}")
async def update_family_settings(
    request: Request,
    family_id: str,
    family_update: dict,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Update family settings and configuration.
    
    Only family administrators can update family settings.
    Supports updating name, notification settings, and other configurations.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Settings must pass validation
    
    **Returns:**
    - Updated family information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"update_family_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        update_data = await family_manager.update_family_settings(
            family_id, user_id, family_update, {"request": request}
        )
        
        logger.info("Family settings updated: %s by admin %s", family_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": update_data["message"],
                "family_id": update_data["family_id"],
                "updated_fields": update_data["updated_fields"],
                "updated_at": update_data["updated_at"].isoformat(),
                "transaction_safe": update_data["transaction_safe"]
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for settings update: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for family update: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except ValidationError as e:
        logger.warning("Validation error in family update: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to update family settings: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "FAMILY_UPDATE_FAILED",
                "message": str(e)
            }
        )


@router.delete("/{family_id}")
async def delete_family(
    request: Request,
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Delete a family and clean up all associated resources.
    
    Only family administrators can delete families.
    This action is irreversible and cleans up all relationships,
    SBD accounts, and associated data.
    
    **Rate Limiting:** 2 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Family SBD account must be empty or have instructions for remaining tokens
    
    **Returns:**
    - Deletion confirmation and cleanup details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"delete_family_{user_id}",
        rate_limit_requests=2,
        rate_limit_period=3600
    )
    
    try:
        deletion_data = await family_manager.delete_family(
            family_id, user_id, {"request": request}
        )
        
        logger.info("Family deleted: %s by admin %s", family_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": deletion_data["message"],
                "family_id": deletion_data["family_id"],
                "members_notified": deletion_data["members_notified"],
                "relationships_cleaned": deletion_data["relationships_cleaned"],
                "sbd_account_handled": deletion_data["sbd_account_handled"],
                "deleted_at": deletion_data["deleted_at"].isoformat(),
                "transaction_safe": deletion_data["transaction_safe"]
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for deletion: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for family deletion: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except AccountFrozen as e:
        logger.warning("Cannot delete family with non-empty SBD account: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ACCOUNT_NOT_EMPTY",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to delete family: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "FAMILY_DELETION_FAILED",
                "message": str(e)
            }
        )


# SBD Account Management Endpoints

@router.get("/{family_id}/sbd-account", response_model=SBDAccountResponse)
async def get_family_sbd_account(
    request: Request,
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> SBDAccountResponse:
    """
    Get family SBD account details including balance and permissions.
    
    Returns comprehensive SBD account information including current balance,
    spending permissions, recent transactions, and freeze status.
    
    **Rate Limiting:** 30 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    
    **Returns:**
    - Complete SBD account information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"sbd_account_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )
    
    try:
        account_data = await family_manager.get_family_sbd_account(family_id, user_id)
        
        logger.debug("Retrieved SBD account for family %s by user %s", family_id, user_id)
        
        return SBDAccountResponse(
            account_username=account_data["account_username"],
            balance=account_data["balance"],
            is_frozen=account_data["is_frozen"],
            frozen_by=account_data.get("frozen_by"),
            member_permissions=account_data["spending_permissions"],
            recent_transactions=account_data["recent_transactions"]
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for SBD account: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for SBD account: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get SBD account: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "SBD_ACCOUNT_FAILED",
                "message": "Failed to retrieve SBD account information"
            }
        )


@router.put("/{family_id}/spending-permissions/{target_user_id}")
async def update_spending_permissions(
    request: Request,
    family_id: str,
    target_user_id: str,
    permissions_request: UpdateSpendingPermissionsRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Update spending permissions for a family member.
    
    Only family administrators can update spending permissions.
    Controls who can spend from the family SBD account and their limits.
    
    **Rate Limiting:** 15 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Target user must be a family member
    - Spending limits must be valid
    
    **Returns:**
    - Permission update confirmation
    """
    admin_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"update_permissions_{admin_id}",
        rate_limit_requests=15,
        rate_limit_period=3600
    )
    
    try:
        permissions_data = await family_manager.update_spending_permissions(
            family_id, admin_id, target_user_id,
            {
                "spending_limit": permissions_request.spending_limit,
                "can_spend": permissions_request.can_spend
            }
        )
        
        logger.info("Spending permissions updated for user %s in family %s by admin %s", 
                   target_user_id, family_id, admin_id)
        
        return JSONResponse(
            content={
                "new_permissions": permissions_data["new_permissions"]
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for permissions update: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for permissions update: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except ValidationError as e:
        logger.warning("Validation error in permissions update: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to update spending permissions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "PERMISSIONS_UPDATE_FAILED",
                "message": str(e)
            }
        )


@router.get("/{family_id}/sbd-account/transactions")
async def get_family_transactions(
    request: Request,
    family_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Get family SBD account transaction history.
    
    Returns paginated transaction history with family member attribution.
    All family members can view transaction history.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    - Limit must be between 1 and 100
    
    **Returns:**
    - Paginated transaction history with details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_transactions_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    # Validate pagination parameters
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_LIMIT",
                "message": "Limit must be between 1 and 100"
            }
        )
    
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_OFFSET",
                "message": "Offset must be non-negative"
            }
        )
    
    try:
        # family_manager.get_family_transactions expects (family_id, user_id, skip, limit)
        # The route receives (limit, offset) so pass them in the correct order: offset -> skip, limit -> limit
        transactions_data = await family_manager.get_family_transactions(
            family_id, user_id, offset, limit
        )
        
        logger.debug("Retrieved %d transactions for family %s", 
                    len(transactions_data["transactions"]), family_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "family_id": transactions_data["family_id"],
                "account_username": transactions_data["account_username"],
                "current_balance": transactions_data["current_balance"],
                "transactions": transactions_data["transactions"],
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total_count": transactions_data["total_count"],
                    "has_more": transactions_data["has_more"]
                },
                "retrieved_at": transactions_data["retrieved_at"].isoformat()
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for transactions: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for transactions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get family transactions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "TRANSACTIONS_FAILED",
                "message": "Failed to retrieve transaction history"
            }
        )


@router.post("/{family_id}/members/{user_id}/backup-admin", response_model=BackupAdminResponse)
async def manage_backup_admin(
    request: Request,
    family_id: str,
    user_id: str,
    backup_request: BackupAdminRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> BackupAdminResponse:
    """
    Designate or remove backup administrator for account recovery.
    
    Backup administrators are automatically promoted to full admin if all primary
    admins become unavailable, ensuring family continuity.
    
    **Rate Limiting:** 5 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Target user must be a family member
    - Target user cannot already be an admin (for designation)
    - Target user must be a backup admin (for removal)
    
    **Returns:**
    - Backup admin action confirmation and details
    """
    admin_user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"backup_admin_action_{admin_user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )
    
    try:
        if backup_request.action == "designate":
            result = await family_manager.designate_backup_admin(
                family_id, admin_user_id, user_id, {"request": request}
            )
            
            logger.info("Backup admin designated: %s by %s in family %s", 
                       user_id, admin_user_id, family_id)
            
            return BackupAdminResponse(**result)
            
        elif backup_request.action == "remove":
            result = await family_manager.remove_backup_admin(
                family_id, admin_user_id, user_id, {"request": request}
            )
            
            logger.info("Backup admin removed: %s by %s in family %s", 
                       user_id, admin_user_id, family_id)
            
            return BackupAdminResponse(**result)
            
    except FamilyNotFound:
        logger.warning("Family not found for backup admin action: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for backup admin action: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except ValidationError as e:
        logger.warning("Invalid backup admin action: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": str(e)
            }
        )
    except BackupAdminError as e:
        logger.error("Backup admin action failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "BACKUP_ADMIN_ERROR",
                "message": str(e)
            }
        )
    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded for backup admin action: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e)
            }
        )


@router.post("/{family_id}/recovery/initiate", response_model=RecoveryInitiationResponse)
async def initiate_account_recovery(
    request: Request,
    family_id: str,
    recovery_request: InitiateRecoveryRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> RecoveryInitiationResponse:
    """
    Initiate account recovery process when admin accounts are compromised or deleted.
    
    This endpoint starts the recovery process when no active administrators remain.
    If backup administrators exist, they are automatically promoted. Otherwise,
    a multi-member verification process is initiated.
    
    **Rate Limiting:** 2 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    - No active administrators must exist
    - Recovery reason must be provided
    
    **Returns:**
    - Recovery initiation confirmation with process details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"recovery_initiate_{user_id}",
        rate_limit_requests=2,
        rate_limit_period=3600
    )
    
    try:
        result = await family_manager.initiate_account_recovery(
            family_id, user_id, recovery_request.recovery_reason, {"request": request}
        )
        
        logger.info("Account recovery initiated: %s for family %s by %s", 
                   result.get("recovery_id", "auto_promotion"), family_id, user_id)
        
        return RecoveryInitiationResponse(**result)
        
    except FamilyNotFound:
        logger.warning("Family not found for recovery initiation: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for recovery initiation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except ValidationError as e:
        logger.warning("Invalid recovery initiation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": str(e)
            }
        )
    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded for recovery initiation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Recovery initiation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "RECOVERY_INITIATION_FAILED",
                "message": str(e)
            }
        )


@router.post("/recovery/{recovery_id}/verify", response_model=RecoveryVerificationResponse)
async def verify_account_recovery(
    request: Request,
    recovery_id: str,
    verify_request: VerifyRecoveryRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> RecoveryVerificationResponse:
    """
    Verify account recovery request by providing verification code.
    
    Family members must provide verification codes (typically sent via email)
    to confirm the recovery request. Once sufficient verifications are received,
    the most senior family member is automatically promoted to administrator.
    
    **Rate Limiting:** 5 requests per hour per user
    
    **Requirements:**
    - User must be a family member of the recovering family
    - Recovery request must be in pending verification status
    - Valid verification code must be provided
    - User cannot have already verified this recovery request
    
    **Returns:**
    - Verification confirmation and recovery status
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"recovery_verify_{user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )
    
    try:
        result = await family_manager.verify_account_recovery(
            recovery_id, user_id, verify_request.verification_code, {"request": request}
        )
        
        logger.info("Recovery verification provided: %s by %s", recovery_id, user_id)
        
        return RecoveryVerificationResponse(**result)
        
    except ValidationError as e:
        logger.warning("Invalid recovery verification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": str(e)
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for recovery verification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded for recovery verification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Recovery verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "RECOVERY_VERIFICATION_FAILED",
                "message": str(e)
            }
        )

# SBD Token Audit and Compliance Endpoints

@router.get("/{family_id}/sbd-transactions/history")
async def get_family_sbd_transaction_history(
    request: Request,
    family_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    transaction_types: Optional[str] = None,
    include_audit_trail: bool = True,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """
    Get comprehensive family SBD transaction history with audit trails and family context.
    
    This endpoint provides detailed transaction history including:
    - Family member attribution for all transactions
    - Comprehensive audit trail information
    - Transaction context and compliance metadata
    - Filtering by date range and transaction types
    - Pagination support for large datasets
    
    Args:
        family_id: ID of the family
        start_date: Start date filter (ISO format)
        end_date: End date filter (ISO format)
        transaction_types: Comma-separated list of transaction types to filter
        include_audit_trail: Whether to include detailed audit trail information
        limit: Maximum number of transactions to return (max 1000)
        offset: Number of transactions to skip for pagination
        
    Returns:
        Comprehensive transaction history with family context and audit trails
        
    Raises:
        403: If user lacks permission to access family audit information
        404: If family not found
        400: If invalid parameters provided
        500: If audit retrieval fails
    """
    try:
        # Rate limiting
        await security_manager.check_rate_limit(
            request, f"family_audit_history_{current_user['username']}", 
            rate_limit_requests=20, rate_limit_period=300
        )
        
        user_id = str(current_user["_id"])
        
        # Validate and parse parameters
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date:
            try:
                from datetime import datetime
                parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_DATE_FORMAT",
                        "message": "start_date must be in ISO format"
                    }
                )
        
        if end_date:
            try:
                from datetime import datetime
                parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_DATE_FORMAT",
                        "message": "end_date must be in ISO format"
                    }
                )
        
        # Parse transaction types
        parsed_transaction_types = None
        if transaction_types:
            parsed_transaction_types = [t.strip() for t in transaction_types.split(',')]
        
        # Validate limit
        if limit > 1000:
            limit = 1000
        
        # Get transaction history with family context
        result = await family_audit_manager.get_family_transaction_history_with_context(
            family_id=family_id,
            user_id=user_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            transaction_types=parsed_transaction_types,
            include_audit_trail=include_audit_trail,
            limit=limit,
            offset=offset
        )
        
        logger.info(
            "Family SBD transaction history retrieved: %d records for family %s by user %s",
            len(result["transactions"]), family_id, user_id
        )
        
        return JSONResponse(
            content={
                "status": "success",
                "data": result
            }
        )
        
    except FamilyAuditError as e:
        if e.error_code == "INSUFFICIENT_PERMISSIONS":
            logger.warning("Insufficient permissions for transaction history: %s", e)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_PERMISSIONS",
                    "message": str(e)
                }
            )
        elif "not found" in str(e).lower():
            logger.warning("Family not found for transaction history: %s", e)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "FAMILY_NOT_FOUND",
                    "message": str(e)
                }
            )
        else:
            logger.error("Failed to retrieve transaction history: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "AUDIT_RETRIEVAL_FAILED",
                    "message": str(e)
                }
            )
    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded for transaction history: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error("Unexpected error retrieving transaction history: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to retrieve transaction history"
            }
        )


@router.post("/{family_id}/compliance/report")
async def generate_family_compliance_report(
    request: Request,
    family_id: str,
    report_type: str = "comprehensive",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    export_format: str = "json",
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """
    Generate comprehensive compliance report for family SBD transactions.
    
    This endpoint generates detailed compliance reports including:
    - Transaction volume and pattern analysis
    - Family member activity summaries
    - Audit trail integrity verification
    - Compliance flags and risk indicators
    - Regulatory compliance information
    
    Args:
        family_id: ID of the family
        report_type: Type of report (comprehensive, summary, transactions_only)
        start_date: Start date for report period (ISO format)
        end_date: End date for report period (ISO format)
        export_format: Format for export (json, csv, pdf)
        
    Returns:
        Comprehensive compliance report with audit information
        
    Raises:
        403: If user is not family admin
        404: If family not found
        400: If invalid parameters provided
        500: If report generation fails
    """
    try:
        # Rate limiting for compliance reports (more restrictive)
        await security_manager.check_rate_limit(
            request, f"family_compliance_report_{current_user['username']}", 
            rate_limit_requests=5, rate_limit_period=3600
        )
        
        user_id = str(current_user["_id"])
        
        # Validate report type
        valid_report_types = ["comprehensive", "summary", "transactions_only"]
        if report_type not in valid_report_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_REPORT_TYPE",
                    "message": f"report_type must be one of: {', '.join(valid_report_types)}"
                }
            )
        
        # Validate export format
        valid_formats = ["json", "csv", "pdf"]
        if export_format not in valid_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_EXPORT_FORMAT",
                    "message": f"export_format must be one of: {', '.join(valid_formats)}"
                }
            )
        
        # Parse dates
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date:
            try:
                from datetime import datetime
                parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_DATE_FORMAT",
                        "message": "start_date must be in ISO format"
                    }
                )
        
        if end_date:
            try:
                from datetime import datetime
                parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_DATE_FORMAT",
                        "message": "end_date must be in ISO format"
                    }
                )
        
        # Generate compliance report
        report = await family_audit_manager.generate_compliance_report(
            family_id=family_id,
            user_id=user_id,
            report_type=report_type,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            export_format=export_format
        )
        
        logger.info(
            "Compliance report generated: %s for family %s by admin %s",
            report["report_metadata"]["report_id"], family_id, user_id
        )
        
        return JSONResponse(
            content={
                "status": "success",
                "data": report
            }
        )
        
    except ComplianceReportError as e:
        if "admin" in str(e).lower() or "permission" in str(e).lower():
            logger.warning("Insufficient admin permissions for compliance report: %s", e)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_ADMIN_PERMISSIONS",
                    "message": "Only family admins can generate compliance reports"
                }
            )
        elif "not found" in str(e).lower():
            logger.warning("Family not found for compliance report: %s", e)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "FAMILY_NOT_FOUND",
                    "message": str(e)
                }
            )
        else:
            logger.error("Failed to generate compliance report: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "COMPLIANCE_REPORT_FAILED",
                    "message": str(e)
                }
            )
    except FamilyAuditError as e:
        if e.error_code == "INSUFFICIENT_ADMIN_PERMISSIONS":
            logger.warning("Insufficient admin permissions for compliance report: %s", e)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_ADMIN_PERMISSIONS",
                    "message": str(e)
                }
            )
        else:
            logger.error("Audit error generating compliance report: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "AUDIT_ERROR",
                    "message": str(e)
                }
            )
    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded for compliance report: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error("Unexpected error generating compliance report: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to generate compliance report"
            }
        )


@router.get("/{family_id}/audit/integrity-check")
async def verify_audit_trail_integrity(
    request: Request,
    family_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """
    Verify integrity of family audit trail records.
    
    This endpoint performs cryptographic verification of audit trail integrity including:
    - Hash verification for all audit records
    - Detection of corrupted or tampered records
    - Missing audit trail identification
    - Comprehensive integrity reporting
    
    Args:
        family_id: ID of the family
        start_date: Start date for verification period (ISO format)
        end_date: End date for verification period (ISO format)
        
    Returns:
        Audit trail integrity verification results
        
    Raises:
        403: If user is not family admin
        404: If family not found
        400: If invalid parameters provided
        500: If integrity check fails
    """
    try:
        # Rate limiting for integrity checks
        await security_manager.check_rate_limit(
            request, f"family_audit_integrity_{current_user['username']}", 
            rate_limit_requests=10, rate_limit_period=3600
        )
        
        user_id = str(current_user["_id"])
        
        # Verify admin permissions
        try:
            await family_audit_manager._verify_family_admin_permission(family_id, user_id)
        except FamilyAuditError as e:
            if e.error_code == "INSUFFICIENT_ADMIN_PERMISSIONS":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "INSUFFICIENT_ADMIN_PERMISSIONS",
                        "message": "Only family admins can verify audit trail integrity"
                    }
                )
            raise
        
        # Parse dates
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date:
            try:
                from datetime import datetime
                parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_DATE_FORMAT",
                        "message": "start_date must be in ISO format"
                    }
                )
        
        if end_date:
            try:
                from datetime import datetime
                parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_DATE_FORMAT",
                        "message": "end_date must be in ISO format"
                    }
                )
        
        # Set default date range if not provided (last 30 days)
        if not parsed_start_date and not parsed_end_date:
            from datetime import datetime, timedelta, timezone
            parsed_end_date = datetime.now(timezone.utc)
            parsed_start_date = parsed_end_date - timedelta(days=30)
        
        # Perform integrity verification
        integrity_results = await family_audit_manager._verify_audit_trail_integrity(
            family_id, parsed_start_date, parsed_end_date
        )
        
        logger.info(
            "Audit trail integrity check completed for family %s by admin %s: %s",
            family_id, user_id, "PASSED" if integrity_results["integrity_verified"] else "FAILED"
        )
        
        return JSONResponse(
            content={
                "status": "success",
                "data": {
                    "family_id": family_id,
                    "verification_period": {
                        "start_date": parsed_start_date.isoformat() if parsed_start_date else None,
                        "end_date": parsed_end_date.isoformat() if parsed_end_date else None
                    },
                    "integrity_results": integrity_results
                }
            }
        )
        
    except FamilyAuditError as e:
        if e.error_code == "INSUFFICIENT_ADMIN_PERMISSIONS":
            logger.warning("Insufficient admin permissions for integrity check: %s", e)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_ADMIN_PERMISSIONS",
                    "message": str(e)
                }
            )
        elif "not found" in str(e).lower():
            logger.warning("Family not found for integrity check: %s", e)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "FAMILY_NOT_FOUND",
                    "message": str(e)
                }
            )
        else:
            logger.error("Failed to verify audit trail integrity: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "INTEGRITY_CHECK_FAILED",
                    "message": str(e)
                }
            )
    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded for integrity check: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error("Unexpected error during integrity check: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to verify audit trail integrity"
            }
        )