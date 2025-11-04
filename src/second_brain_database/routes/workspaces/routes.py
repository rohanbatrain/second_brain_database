"""
API routes for the Teams/Workspaces feature.

This module provides REST API endpoints for workspace management including:
- Workspace creation and management
- Member management and role assignments (RBAC)

All endpoints require authentication and follow established security patterns.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query

from second_brain_database.managers.workspace_manager import (
    workspace_manager,
    WorkspaceError,
    WorkspaceNotFound,
    InsufficientPermissions,
    UserAlreadyMember,
    UserNotMember,
    OwnerCannotBeRemoved
)
from second_brain_database.routes.auth.dependencies import get_current_user_dep
from second_brain_database.managers.team_wallet_manager import (
    team_wallet_manager,
    TeamWalletError,
    WorkspaceNotFound,
    InsufficientPermissions
)
from second_brain_database.managers.security_manager import security_manager
from pydantic import BaseModel, Field

# --- Pydantic Models for API Requests & Responses ---

class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    members: List[dict]
    settings: dict
    created_at: str
    updated_at: str
    wallet_initialized: Optional[bool] = None

class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class AddMemberRequest(BaseModel):
    user_id_to_add: str
    role: str = Field(..., pattern="^(admin|editor|viewer)$")

class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|editor|viewer)$")

class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    settings: Optional[dict] = None

# Team Wallet Models

class TeamWalletResponse(BaseModel):
    workspace_id: str
    account_username: str
    balance: int
    is_frozen: bool
    frozen_by: Optional[str] = None
    frozen_at: Optional[str] = None
    user_permissions: dict
    notification_settings: dict
    recent_transactions: list

class CreateTokenRequestRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount of tokens to request")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for the request")

class TokenRequestResponse(BaseModel):
    request_id: str
    requester_username: str
    amount: int
    reason: str
    status: str
    auto_approved: bool
    created_at: str
    expires_at: str
    admin_comments: Optional[str] = None

class ReviewTokenRequestRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|deny)$")
    comments: Optional[str] = Field(None, max_length=500)

class UpdateSpendingPermissionsRequest(BaseModel):
    user_id: str
    spending_limit: int = Field(..., ge=-1)  # -1 means unlimited
    can_spend: bool

class FreezeAccountRequest(BaseModel):
    action: str = Field(..., pattern="^(freeze|unfreeze)$")
    reason: Optional[str] = Field(None, min_length=5, max_length=500)

class UpdateWalletPermissionsRequest(BaseModel):
    member_permissions: Dict[str, Dict[str, Any]] = Field(..., description="Dictionary mapping user_id to their permissions")

class WalletPermissionsResponse(BaseModel):
    permissions: Dict[str, Any]

# --- Router Setup ---

router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"]
)


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    req: CreateWorkspaceRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Create a new workspace.

    The user who creates the workspace is automatically assigned as the owner and an admin.
    The team wallet is automatically initialized for immediate use.
    """
    user_id = str(current_user["_id"])
    try:
        workspace_data = await workspace_manager.create_workspace(
            user_id=user_id,
            name=req.name,
            description=req.description
        )

        # Auto-initialize team wallet for the new workspace
        try:
            await team_wallet_manager.initialize_team_wallet(workspace_data["workspace_id"], user_id)
            workspace_data["wallet_initialized"] = True
        except Exception as wallet_error:
            # Log wallet initialization failure but don't fail workspace creation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to auto-initialize wallet for workspace {workspace_data['workspace_id']}: {str(wallet_error)}")
            workspace_data["wallet_initialized"] = False

        # Convert datetime objects to ISO 8601 strings for the response
        workspace_data['created_at'] = workspace_data['created_at'].isoformat()
        workspace_data['updated_at'] = workspace_data['updated_at'].isoformat()
        return WorkspaceResponse(**workspace_data)
    except WorkspaceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


@router.get("", response_model=List[WorkspaceResponse])
async def get_my_workspaces(current_user: dict = Depends(get_current_user_dep)):
    """Get all workspaces the current user is a member of."""
    user_id = str(current_user["_id"])
    workspaces = await workspace_manager.get_workspaces_for_user(user_id)
    # Convert datetime objects for response and check wallet status
    for ws in workspaces:
        ws['created_at'] = ws['created_at'].isoformat()
        ws['updated_at'] = ws['updated_at'].isoformat()
        # Check if wallet is initialized
        ws['wallet_initialized'] = bool(ws.get('sbd_account', {}).get('account_username'))
    return workspaces


@router.get("/diagnostic", response_model=Dict[str, Any])
async def get_workspace_diagnostic(current_user: dict = Depends(get_current_user_dep)):
    """
    Diagnostic endpoint to help debug workspace access issues.

    Returns information about user's workspaces and helps identify
    why certain workspace IDs might not be accessible.
    """
    user_id = str(current_user["_id"])

    # Get user's workspaces
    user_workspaces = await workspace_manager.get_workspaces_for_user(user_id)

    # Get all workspaces in the system (for admin debugging)
    all_workspaces_cursor = workspace_manager.workspaces_collection.find({})
    all_workspaces = await all_workspaces_cursor.to_list(length=None)

    # Format user workspaces
    formatted_user_workspaces = []
    for ws in user_workspaces:
        formatted_user_workspaces.append({
            "workspace_id": ws["workspace_id"],
            "name": ws.get("name", "Unnamed"),
            "role": workspace_manager.get_user_role(user_id, ws),
            "member_count": len(ws.get("members", [])),
            "wallet_initialized": bool(ws.get('sbd_account', {}).get('account_username')),
            "created_at": ws['created_at'].isoformat() if hasattr(ws['created_at'], 'isoformat') else str(ws['created_at'])
        })

    # Format all workspaces (summary only)
    formatted_all_workspaces = []
    for ws in all_workspaces:
        formatted_all_workspaces.append({
            "workspace_id": ws["workspace_id"],
            "name": ws.get("name", "Unnamed"),
            "owner_id": ws.get("owner_id"),
            "member_count": len(ws.get("members", [])),
            "has_wallet": bool(ws.get('sbd_account', {}).get('account_username'))
        })

    return {
        "user_id": user_id,
        "user_workspaces": formatted_user_workspaces,
        "total_user_workspaces": len(user_workspaces),
        "total_system_workspaces": len(all_workspaces),
        "diagnostic_info": {
            "message": "If your app is getting 404 errors for workspace access, check if the workspace_id exists in user_workspaces above",
            "common_issues": [
                "App using cached workspace ID from previous session",
                "Workspace was deleted but app still references it",
                "User not a member of the workspace",
                "Workspace ID typo or corruption"
            ]
        }
    }


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """Get details for a single workspace."""
    user_id = str(current_user["_id"])
    try:
        workspace = await workspace_manager.get_workspace_by_id(workspace_id, user_id)
        workspace['created_at'] = workspace['created_at'].isoformat()
        workspace['updated_at'] = workspace['updated_at'].isoformat()
        # Check if wallet is initialized
        workspace['wallet_initialized'] = bool(workspace.get('sbd_account', {}).get('account_username'))
        return workspace
    except (WorkspaceNotFound, InsufficientPermissions) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": e.error_code, "message": str(e)})


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    req: UpdateWorkspaceRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """Update a workspace's details. (Requires admin privileges)."""
    admin_user_id = str(current_user["_id"])
    try:
        workspace = await workspace_manager.update_workspace(
            workspace_id=workspace_id,
            admin_user_id=admin_user_id,
            name=req.name,
            description=req.description,
            settings=req.settings
        )
        workspace['created_at'] = workspace['created_at'].isoformat()
        workspace['updated_at'] = workspace['updated_at'].isoformat()
        # Check if wallet is initialized
        workspace['wallet_initialized'] = bool(workspace.get('sbd_account', {}).get('account_username'))
        return workspace
    except (WorkspaceNotFound, InsufficientPermissions) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """Delete a workspace. (Requires owner privileges)."""
    admin_user_id = str(current_user["_id"])
    try:
        deleted = await workspace_manager.delete_workspace(
            workspace_id=workspace_id,
            admin_user_id=admin_user_id
        )
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except (WorkspaceNotFound, InsufficientPermissions) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})


@router.post("/{workspace_id}/members", response_model=WorkspaceResponse)
async def add_workspace_member(
    workspace_id: str,
    req: AddMemberRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """Add a new member to a workspace. (Requires admin privileges)."""
    admin_user_id = str(current_user["_id"])
    try:
        workspace = await workspace_manager.add_member(
            workspace_id=workspace_id,
            admin_user_id=admin_user_id,
            user_id_to_add=req.user_id_to_add,
            role=req.role
        )
        workspace['created_at'] = workspace['created_at'].isoformat()
        workspace['updated_at'] = workspace['updated_at'].isoformat()
        # Check if wallet is initialized
        workspace['wallet_initialized'] = bool(workspace.get('sbd_account', {}).get('account_username'))
        return workspace
    except (WorkspaceNotFound, InsufficientPermissions, UserAlreadyMember) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})


@router.delete("/{workspace_id}/members/{user_id}", response_model=WorkspaceResponse)
async def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """Remove a member from a workspace. (Requires admin privileges)."""
    admin_user_id = str(current_user["_id"])
    try:
        workspace = await workspace_manager.remove_member(
            workspace_id=workspace_id,
            admin_user_id=admin_user_id,
            user_id_to_remove=user_id
        )
        workspace['created_at'] = workspace['created_at'].isoformat()
        workspace['updated_at'] = workspace['updated_at'].isoformat()
        # Check if wallet is initialized
        workspace['wallet_initialized'] = bool(workspace.get('sbd_account', {}).get('account_username'))
        return workspace
    except (WorkspaceNotFound, InsufficientPermissions, UserNotMember) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})


@router.put("/{workspace_id}/members/{user_id_to_update}", response_model=WorkspaceResponse)
async def update_workspace_member_role(
    workspace_id: str,
    user_id_to_update: str,
    req: UpdateMemberRoleRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """Update a member's role in a workspace. (Requires admin privileges)."""
    admin_user_id = str(current_user["_id"])
    try:
        workspace = await workspace_manager.update_member_role(
            workspace_id=workspace_id,
            admin_user_id=admin_user_id,
            user_id_to_update=user_id_to_update,
            new_role=req.role
        )
        workspace['created_at'] = workspace['created_at'].isoformat()
        workspace['updated_at'] = workspace['updated_at'].isoformat()
        # Check if wallet is initialized
        workspace['wallet_initialized'] = bool(workspace.get('sbd_account', {}).get('account_username'))
        return workspace
    except (WorkspaceNotFound, InsufficientPermissions, UserNotMember, OwnerCannotBeRemoved) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})


# Team Wallet Endpoints

@router.post("/{workspace_id}/wallet/initialize", response_model=dict)
async def initialize_team_wallet(
    request: Request,
    workspace_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Initialize SBD wallet for a workspace.

    Creates a virtual account and sets up initial permissions.
    Only workspace admins can initialize the wallet.
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_wallet_init_{user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )

    try:
        result = await team_wallet_manager.initialize_team_wallet(workspace_id, user_id)
        return result
    except WorkspaceNotFound:
        # Log detailed information for debugging workspace access issues
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Workspace not found in initialize_team_wallet: workspace_id={workspace_id}, user_id={user_id}")

        # Check if workspace exists but user is not a member
        try:
            workspace = await workspace_manager.workspaces_collection.find_one({"workspace_id": workspace_id})
            if workspace:
                logger.info(f"Workspace {workspace_id} exists but user {user_id} is not a member")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "You are not a member of this workspace"})
            else:
                logger.info(f"Workspace {workspace_id} does not exist in database")
        except Exception as check_error:
            logger.error(f"Error checking workspace existence: {str(check_error)}")

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "Only workspace admins can initialize the wallet"})
    except Exception as e:
        if hasattr(e, 'error_code') and e.error_code == "WALLET_ALREADY_EXISTS":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


# Alias endpoint for Flutter compatibility
@router.post("/{workspace_id}/wallet/init", response_model=dict, deprecated=True)
async def initialize_team_wallet_alias(
    request: Request,
    workspace_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    DEPRECATED: Use /wallet/initialize instead.

    This endpoint is maintained for Flutter app compatibility.
    Will be removed in a future version.
    """
    return await initialize_team_wallet(request, workspace_id, current_user)


@router.get("/{workspace_id}/wallet", response_model=TeamWalletResponse)
async def get_team_wallet(
    request: Request,
    workspace_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get team wallet information including balance and permissions.

    Returns comprehensive wallet details for workspace members.
    If wallet is not initialized, attempts to initialize it automatically.
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_wallet_get_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )

    try:
        wallet_data = await team_wallet_manager.get_team_wallet_info(workspace_id, user_id)
        # Convert datetime objects to ISO strings
        if wallet_data.get("frozen_at") and hasattr(wallet_data["frozen_at"], 'isoformat'):
            wallet_data["frozen_at"] = wallet_data["frozen_at"].isoformat()
        for tx in wallet_data.get("recent_transactions", []):
            if tx.get("timestamp") and hasattr(tx["timestamp"], 'isoformat'):
                tx["timestamp"] = tx["timestamp"].isoformat()
        return TeamWalletResponse(**wallet_data)
    except WorkspaceNotFound:
        # Log detailed information for debugging workspace access issues
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Workspace not found in get_team_wallet: workspace_id={workspace_id}, user_id={user_id}")

        # Check if workspace exists but user is not a member
        try:
            workspace = await workspace_manager.workspaces_collection.find_one({"workspace_id": workspace_id})
            if workspace:
                logger.info(f"Workspace {workspace_id} exists but user {user_id} is not a member")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "You are not a member of this workspace"})
            else:
                logger.info(f"Workspace {workspace_id} does not exist in database")
        except Exception as check_error:
            logger.error(f"Error checking workspace existence: {str(check_error)}")

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "You are not a workspace member"})
    except TeamWalletError as e:
        error_code = getattr(e, 'error_code', 'TEAM_WALLET_ERROR')
        if error_code == "WALLET_NOT_INITIALIZED":
            # Try to auto-initialize the wallet for existing workspaces
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Wallet not initialized for workspace {workspace_id}, attempting auto-initialization")
            try:
                await team_wallet_manager.initialize_team_wallet(workspace_id, user_id)
                # Now try to get the wallet info again
                wallet_data = await team_wallet_manager.get_team_wallet_info(workspace_id, user_id)
                # Convert datetime objects to ISO strings
                if wallet_data.get("frozen_at") and hasattr(wallet_data["frozen_at"], 'isoformat'):
                    wallet_data["frozen_at"] = wallet_data["frozen_at"].isoformat()
                for tx in wallet_data.get("recent_transactions", []):
                    if tx.get("timestamp") and hasattr(tx["timestamp"], 'isoformat'):
                        tx["timestamp"] = tx["timestamp"].isoformat()
                return TeamWalletResponse(**wallet_data)
            except Exception as init_error:
                logger.error(f"Failed to auto-initialize wallet for workspace {workspace_id}: {str(init_error)}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error_code, "message": "Team wallet not initialized and auto-initialization failed"})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error_code, "message": str(e)})
    except Exception as e:
        # Log the full exception for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error in get_team_wallet for workspace {workspace_id}, user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred"})


@router.post("/{workspace_id}/wallet/token-requests", response_model=TokenRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_token_request(
    request: Request,
    workspace_id: str,
    token_request: CreateTokenRequestRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Create a token request from the team account.

    Workspace members can request tokens from the shared account.
    Requests under the auto-approval threshold are processed immediately.
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_token_request_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )

    try:
        request_data = await team_wallet_manager.create_token_request(
            workspace_id=workspace_id,
            user_id=user_id,
            amount=token_request.amount,
            reason=token_request.reason
        )
        # Convert datetime objects to ISO strings
        request_data["created_at"] = request_data["created_at"].isoformat()
        request_data["expires_at"] = request_data["expires_at"].isoformat()
        return TokenRequestResponse(**request_data)
    except WorkspaceNotFound:
        # Log detailed information for debugging workspace access issues
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Workspace not found in create_token_request: workspace_id={workspace_id}, user_id={user_id}")

        # Check if workspace exists but user is not a member
        try:
            workspace = await workspace_manager.workspaces_collection.find_one({"workspace_id": workspace_id})
            if workspace:
                logger.info(f"Workspace {workspace_id} exists but user {user_id} is not a member")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "You are not a member of this workspace"})
            else:
                logger.info(f"Workspace {workspace_id} does not exist in database")
        except Exception as check_error:
            logger.error(f"Error checking workspace existence: {str(check_error)}")

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "You are not a workspace member"})
    except Exception as e:
        error_code = getattr(e, 'error_code', 'INTERNAL_SERVER_ERROR')
        if error_code in ["WALLET_NOT_INITIALIZED", "ACCOUNT_FROZEN", "VALIDATION_ERROR"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error_code, "message": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


@router.get("/{workspace_id}/wallet/token-requests/pending", response_model=List[TokenRequestResponse])
async def get_pending_token_requests(
    request: Request,
    workspace_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get all pending token requests for a workspace (admin only).

    Returns all pending token requests that require admin approval.
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_pending_requests_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )

    try:
        pending_requests = await team_wallet_manager.get_pending_token_requests(workspace_id, user_id)
        return pending_requests
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "Only workspace admins can view pending requests"})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


# Alias endpoint for Flutter compatibility
@router.get("/{workspace_id}/wallet/requests", response_model=List[TokenRequestResponse], deprecated=True)
async def get_token_requests_alias(
    request: Request,
    workspace_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    DEPRECATED: Use /wallet/token-requests/pending instead.

    This endpoint is maintained for Flutter app compatibility.
    Will be removed in a future version.
    """
    return await get_pending_token_requests(request, workspace_id, current_user)


@router.post("/{workspace_id}/wallet/token-requests/{request_id}/review")
async def review_token_request(
    request: Request,
    workspace_id: str,
    request_id: str,
    review_request: ReviewTokenRequestRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Review a token request (approve or deny) - admin only.

    Workspace administrators can approve or deny pending token requests.
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_token_review_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )

    try:
        result = await team_wallet_manager.review_token_request(
            request_id=request_id,
            admin_id=user_id,
            action=review_request.action,
            comments=review_request.comments
        )
        if result.get("processed_at"):
            result["processed_at"] = result["processed_at"].isoformat()
        return result
    except Exception as e:
        # Enhanced error logging for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error reviewing token request {request_id} for workspace {workspace_id} by user {user_id}: {str(e)}", exc_info=True)

        error_code = getattr(e, 'error_code', 'INTERNAL_SERVER_ERROR')
        if error_code in ["TOKEN_REQUEST_NOT_FOUND", "VALIDATION_ERROR"]:
            logger.warning(f"Token request review failed with 400 error: {error_code} - {str(e)}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error_code, "message": str(e)})
        elif error_code == "INSUFFICIENT_PERMISSIONS":
            logger.warning(f"Token request review failed with 403 error: user {user_id} not authorized for workspace {workspace_id}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": error_code, "message": str(e)})
        logger.error(f"Token request review failed with 500 error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


@router.put("/{workspace_id}/wallet/permissions", response_model=WalletPermissionsResponse)
async def update_spending_permissions(
    request: Request,
    workspace_id: str,
    permissions: UpdateWalletPermissionsRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Update spending permissions for workspace members.

    Only workspace admins can modify spending permissions.
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_wallet_permissions_{user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )

    try:
        updated_permissions = {}
        for member_user_id, member_perms in permissions.member_permissions.items():
            result = await team_wallet_manager.update_spending_permissions(
                workspace_id=workspace_id,
                admin_id=user_id,
                user_id=member_user_id,
                permissions=member_perms
            )
            updated_permissions[member_user_id] = result

        return WalletPermissionsResponse(permissions=updated_permissions)
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "Only workspace admins can modify spending permissions"})
    except Exception as e:
        error_code = getattr(e, 'error_code', 'INTERNAL_SERVER_ERROR')
        if error_code in ["WALLET_NOT_INITIALIZED", "VALIDATION_ERROR"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error_code, "message": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


# Alias endpoint for Flutter compatibility
@router.put("/{workspace_id}/wallet/settings", response_model=WalletPermissionsResponse, deprecated=True)
async def update_wallet_settings_alias(
    request: Request,
    workspace_id: str,
    permissions: UpdateWalletPermissionsRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    DEPRECATED: Use /wallet/permissions instead.

    This endpoint is maintained for Flutter app compatibility.
    Will be removed in a future version.
    """
    return await update_spending_permissions(request, workspace_id, permissions, current_user)


@router.post("/{workspace_id}/wallet/freeze")
async def freeze_unfreeze_account(
    request: Request,
    workspace_id: str,
    freeze_request: FreezeAccountRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Freeze or unfreeze the team account.

    Only workspace admins can freeze/unfreeze the account.
    """
    admin_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_wallet_freeze_{admin_id}",
        rate_limit_requests=3,
        rate_limit_period=3600
    )

    try:
        if freeze_request.action == "freeze":
            result = await team_wallet_manager.freeze_team_account(
                workspace_id, admin_id, freeze_request.reason or "Administrative freeze"
            )
        else:
            result = await team_wallet_manager.unfreeze_team_account(workspace_id, admin_id)

        if result.get("frozen_at"):
            result["frozen_at"] = result["frozen_at"].isoformat()
        if result.get("unfrozen_at"):
            result["unfrozen_at"] = result["unfrozen_at"].isoformat()

        return result
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "Only workspace admins can freeze/unfreeze accounts"})
    except Exception as e:
        error_code = getattr(e, 'error_code', 'INTERNAL_SERVER_ERROR')
        if error_code in ["ACCOUNT_FROZEN"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error_code, "message": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


# --- Compliance and Audit Endpoints ---

@router.get("/{workspace_id}/wallet/audit", response_model=List[Dict[str, Any]])
async def get_team_audit_trail(
    request: Request,
    workspace_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get audit trail for compliance and monitoring.

    Only workspace admins can access audit trails.
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_audit_access_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )

    try:
        audit_trail = await team_wallet_manager.get_team_audit_trail(
            workspace_id=workspace_id,
            admin_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        return audit_trail
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "Only workspace admins can access audit trails"})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


@router.get("/{workspace_id}/wallet/compliance-report", response_model=Dict[str, Any])
async def generate_compliance_report(
    request: Request,
    workspace_id: str,
    report_type: str = Query("json", regex="^(json|csv|pdf)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Generate compliance report for regulatory requirements.

    Only workspace admins can generate compliance reports.
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_compliance_report_{user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )

    try:
        report = await team_wallet_manager.generate_compliance_report(
            workspace_id=workspace_id,
            admin_id=user_id,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date
        )
        return report
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "Only workspace admins can generate compliance reports"})
    except Exception as e:
        error_code = getattr(e, 'error_code', 'INTERNAL_SERVER_ERROR')
        if error_code in ["COMPLIANCE_REPORT_ERROR"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error_code, "message": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


# --- Emergency Recovery Endpoints ---

@router.post("/{workspace_id}/wallet/backup-admin", response_model=Dict[str, Any])
async def designate_backup_admin(
    request: Request,
    workspace_id: str,
    backup_admin_request: Dict[str, str],
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Designate a backup admin for emergency recovery operations.

    Only workspace admins can designate backup admins.
    """
    user_id = str(current_user["_id"])
    backup_admin_id = backup_admin_request.get("backup_admin_id")

    if not backup_admin_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "VALIDATION_ERROR", "message": "backup_admin_id is required"})

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_backup_admin_{user_id}",
        rate_limit_requests=3,
        rate_limit_period=3600
    )

    try:
        result = await team_wallet_manager.designate_backup_admin(
            workspace_id=workspace_id,
            admin_id=user_id,
            backup_admin_id=backup_admin_id
        )
        return result
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "Only workspace admins can designate backup admins"})
    except Exception as e:
        error_code = getattr(e, 'error_code', 'INTERNAL_SERVER_ERROR')
        if error_code in ["USER_NOT_MEMBER"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error_code, "message": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


@router.delete("/{workspace_id}/wallet/backup-admin/{backup_admin_id}", response_model=Dict[str, Any])
async def remove_backup_admin(
    request: Request,
    workspace_id: str,
    backup_admin_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Remove a backup admin designation.

    Only workspace admins can remove backup admin designations.
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"team_remove_backup_admin_{user_id}",
        rate_limit_requests=3,
        rate_limit_period=3600
    )

    try:
        result = await team_wallet_manager.remove_backup_admin(
            workspace_id=workspace_id,
            admin_id=user_id,
            backup_admin_id=backup_admin_id
        )
        return result
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "Only workspace admins can remove backup admins"})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


@router.post("/{workspace_id}/wallet/emergency-unfreeze", response_model=Dict[str, Any])
async def emergency_unfreeze_account(
    request: Request,
    workspace_id: str,
    emergency_request: Dict[str, str],
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Emergency unfreeze mechanism for backup admins.

    Only designated backup admins can perform emergency unfreezes.
    """
    user_id = str(current_user["_id"])
    emergency_reason = emergency_request.get("emergency_reason")

    if not emergency_reason or len(emergency_reason.strip()) < 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "VALIDATION_ERROR", "message": "Emergency reason must be at least 10 characters"})

    # Apply rate limiting (stricter for emergency operations)
    await security_manager.check_rate_limit(
        request,
        f"team_emergency_unfreeze_{user_id}",
        rate_limit_requests=1,
        rate_limit_period=3600
    )

    try:
        result = await team_wallet_manager.emergency_unfreeze_account(
            workspace_id=workspace_id,
            backup_admin_id=user_id,
            emergency_reason=emergency_reason.strip()
        )
        return result
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    except InsufficientPermissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "INSUFFICIENT_PERMISSIONS", "message": "Only designated backup admins can perform emergency unfreezes"})
    except Exception as e:
        error_code = getattr(e, 'error_code', 'INTERNAL_SERVER_ERROR')
        if error_code in ["ACCOUNT_FROZEN"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": error_code, "message": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})
