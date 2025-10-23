"""
API routes for the Teams/Workspaces feature.

This module provides REST API endpoints for workspace management including:
- Workspace creation and management
- Member management and role assignments (RBAC)

All endpoints require authentication and follow established security patterns.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

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

class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class AddMemberRequest(BaseModel):
    user_id_to_add: str
    role: str = Field(..., pattern="^(admin|editor|viewer)$")

class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    settings: Optional[dict] = None

# --- Router Setup ---

router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"]
)


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    req: CreateWorkspaceRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Create a new workspace.

    The user who creates the workspace is automatically assigned as the owner and an admin.
    """
    user_id = str(current_user["_id"])
    try:
        workspace_data = await workspace_manager.create_workspace(
            user_id=user_id,
            name=req.name,
            description=req.description
        )
        # Convert datetime objects to ISO 8601 strings for the response
        workspace_data['created_at'] = workspace_data['created_at'].isoformat()
        workspace_data['updated_at'] = workspace_data['updated_at'].isoformat()
        return WorkspaceResponse(**workspace_data)
    except WorkspaceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)})


@router.get("/", response_model=List[WorkspaceResponse])
async def get_my_workspaces(current_user: dict = Depends(get_current_user_dep)):
    """Get all workspaces the current user is a member of."""
    user_id = str(current_user["_id"])
    workspaces = await workspace_manager.get_workspaces_for_user(user_id)
    # Convert datetime objects for response
    for ws in workspaces:
        ws['created_at'] = ws['created_at'].isoformat()
        ws['updated_at'] = ws['updated_at'].isoformat()
    return workspaces


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
        return workspace
    except (WorkspaceNotFound, InsufficientPermissions, UserAlreadyMember) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})


@router.delete("/{workspace_id}/members/{user_id_to_remove}", response_model=WorkspaceResponse)
async def remove_workspace_member(
    workspace_id: str,
    user_id_to_remove: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """Remove a member from a workspace. (Requires admin privileges)."""
    admin_user_id = str(current_user["_id"])
    try:
        workspace = await workspace_manager.remove_member(
            workspace_id=workspace_id,
            admin_user_id=admin_user_id,
            user_id_to_remove=user_id_to_remove
        )
        workspace['created_at'] = workspace['created_at'].isoformat()
        workspace['updated_at'] = workspace['updated_at'].isoformat()
        return workspace
    except (WorkspaceNotFound, InsufficientPermissions, UserNotMember, OwnerCannotBeRemoved) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": e.error_code, "message": str(e)})
