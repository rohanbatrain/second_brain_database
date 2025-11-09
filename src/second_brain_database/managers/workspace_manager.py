"""
Workspace Manager for handling team creation, member management, and permissions.

This module provides the WorkspaceManager class, which manages workspace creation,
member invitations, and role-based access control (RBAC), following the established
patterns in the codebase for dependency injection, custom error handling, and security.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.workspace_models import WorkspaceDocument, WorkspaceMember

# Protocols for dependency injection (can be expanded later)
# from second_brain_database.managers.family_manager import DatabaseManagerProtocol, SecurityManagerProtocol

logger = get_logger(prefix="[WorkspaceManager]")

# --- Custom Exception Hierarchy for Workspaces ---


class WorkspaceError(Exception):
    """Base exception for workspace-related errors."""

    def __init__(self, message: str, error_code: str = "WORKSPACE_ERROR", context: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}


class WorkspaceNotFound(WorkspaceError):
    """Raised when a workspace is not found."""

    def __init__(self, message: str = "Workspace not found."):
        super().__init__(message, "WORKSPACE_NOT_FOUND")


class InsufficientPermissions(WorkspaceError):
    """Raised when a user lacks the required permissions for an operation."""

    def __init__(self, message: str = "You do not have sufficient permissions to perform this action."):
        super().__init__(message, "INSUFFICIENT_PERMISSIONS")


class UserAlreadyMember(WorkspaceError):
    """Raised when trying to add a user who is already a member."""

    def __init__(self, message: str = "User is already a member of this workspace."):
        super().__init__(message, "USER_ALREADY_MEMBER")


class UserNotMember(WorkspaceError):
    """Raised when trying to modify a user who is not a member."""

    def __init__(self, message: str = "User is not a member of this workspace."):
        super().__init__(message, "USER_NOT_MEMBER")


class OwnerCannotBeRemoved(WorkspaceError):
    """Raised when attempting to remove the owner of a workspace."""

    def __init__(self, message: str = "The owner of the workspace cannot be removed."):
        super().__init__(message, "OWNER_CANNOT_BE_REMOVED")


class WorkspaceManager:
    """
    Manages all business logic for the Teams/Workspaces feature.
    """

    def __init__(self, db_manager_instance: Any = None):
        """
        Initialize WorkspaceManager with dependency injection.
        Args:
            db_manager_instance: Database manager for data operations.
        """
        self.db = db_manager_instance or db_manager
        self.logger = logger
        self.logger.debug("WorkspaceManager initialized.")

    @property
    def workspaces_collection(self):
        """Lazy-loads the workspaces collection to ensure DB is connected."""
        return self.db.get_collection("workspaces")

    # --- Public Methods (API Facing) ---

    async def create_workspace(self, user_id: str, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Creates a new workspace with the user as the owner."""
        self.logger.info(f"Attempting to create workspace '{name}' for user {user_id}")

        # The user who creates the workspace is the owner and initial admin.
        owner_as_member = WorkspaceMember(user_id=user_id, role="admin", joined_at=datetime.now(timezone.utc))

        workspace_doc = WorkspaceDocument(
            workspace_id=f"ws_{uuid.uuid4().hex[:16]}",
            name=name,
            description=description,
            owner_id=user_id,
            members=[owner_as_member],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Insert the workspace into the database
        result = await self.workspaces_collection.insert_one(workspace_doc.model_dump(by_alias=True))
        if not result.inserted_id:
            raise WorkspaceError("Failed to create workspace in database")

        self.logger.info(f"Successfully created workspace {workspace_doc.workspace_id} for user {user_id}")
        return workspace_doc.model_dump()

    async def get_workspaces_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves all workspaces a user is a member of."""
        cursor = self.workspaces_collection.find({"members.user_id": user_id})
        workspaces = await cursor.to_list(length=None)
        return workspaces

    async def get_workspace_by_id(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """Retrieves a single workspace if the user is a member."""
        workspace = await self._find_workspace_if_member(workspace_id, user_id)
        return workspace

    async def add_member(self, workspace_id: str, admin_user_id: str, user_id_to_add: str, role: str) -> Dict[str, Any]:
        """Adds a new member to a workspace."""
        workspace = await self._find_workspace_if_admin(workspace_id, admin_user_id)

        if any(member["user_id"] == user_id_to_add for member in workspace["members"]):
            raise UserAlreadyMember()

        new_member = WorkspaceMember(user_id=user_id_to_add, role=role, joined_at=datetime.now(timezone.utc))

        result = await self.workspaces_collection.update_one(
            {"workspace_id": workspace_id}, {"$push": {"members": new_member.model_dump(by_alias=True)}}
        )

        if result.modified_count == 0:
            raise WorkspaceError("Failed to add member to workspace.")

        workspace["members"].append(new_member.model_dump())
        return workspace

    async def remove_member(self, workspace_id: str, admin_user_id: str, user_id_to_remove: str) -> Dict[str, Any]:
        """Removes a member from a workspace."""
        workspace = await self._find_workspace_if_admin(workspace_id, admin_user_id)

        if workspace["owner_id"] == user_id_to_remove:
            raise OwnerCannotBeRemoved()

        result = await self.workspaces_collection.update_one(
            {"workspace_id": workspace_id}, {"$pull": {"members": {"user_id": user_id_to_remove}}}
        )

        if result.modified_count == 0:
            raise UserNotMember()

        workspace["members"] = [m for m in workspace["members"] if m["user_id"] != user_id_to_remove]
        return workspace

    async def update_member_role(
        self, workspace_id: str, admin_user_id: str, user_id_to_update: str, new_role: str
    ) -> Dict[str, Any]:
        """Updates a member's role in a workspace."""
        workspace = await self._find_workspace_if_admin(workspace_id, admin_user_id)

        # Check if the user to update is a member
        member_found = False
        for member in workspace["members"]:
            if member["user_id"] == user_id_to_update:
                member_found = True
                break

        if not member_found:
            raise UserNotMember()

        # Prevent changing owner's role
        if workspace["owner_id"] == user_id_to_update:
            raise OwnerCannotBeRemoved("Cannot change the workspace owner's role.")

        # Update the member's role
        result = await self.workspaces_collection.update_one(
            {"workspace_id": workspace_id, "members.user_id": user_id_to_update},
            {"$set": {"members.$.role": new_role, "updated_at": datetime.now(timezone.utc)}},
        )

        if result.modified_count == 0:
            raise WorkspaceError("Failed to update member role.")

        # Return updated workspace
        updated_workspace = await self.workspaces_collection.find_one({"workspace_id": workspace_id})
        return updated_workspace

    async def update_workspace(
        self,
        workspace_id: str,
        admin_user_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Updates a workspace's details."""
        workspace = await self._find_workspace_if_admin(workspace_id, admin_user_id)

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if settings is not None:
            update_data["settings"] = settings

        if not update_data:
            return workspace  # No changes to make

        update_data["updated_at"] = datetime.now(timezone.utc)

        result = await self.workspaces_collection.update_one({"workspace_id": workspace_id}, {"$set": update_data})

        if result.modified_count == 0:
            raise WorkspaceError("Failed to update workspace.")

        # Return updated workspace
        updated_workspace = await self.workspaces_collection.find_one({"workspace_id": workspace_id})
        return updated_workspace

    async def delete_workspace(self, workspace_id: str, admin_user_id: str) -> bool:
        """Deletes a workspace. Only the owner can delete the workspace."""
        workspace = await self.workspaces_collection.find_one({"workspace_id": workspace_id})
        if not workspace:
            raise WorkspaceNotFound()

        if workspace["owner_id"] != admin_user_id:
            raise InsufficientPermissions("Only the workspace owner can delete the workspace.")

        result = await self.workspaces_collection.delete_one({"workspace_id": workspace_id})
        return result.deleted_count > 0

    # --- Private Helper & Security Methods ---

    async def _find_workspace_if_member(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """Finds a workspace and verifies the user is a member."""
        workspace = await self.workspaces_collection.find_one(
            {"workspace_id": workspace_id, "members.user_id": user_id}
        )
        if not workspace:
            # Check if workspace exists at all to give a more specific error
            if await self.workspaces_collection.count_documents({"workspace_id": workspace_id}) > 0:
                raise InsufficientPermissions("You are not a member of this workspace.")
            else:
                raise WorkspaceNotFound()
        return workspace

    async def _find_workspace_if_admin(self, workspace_id: str, user_id: str) -> Dict[str, Any]:
        """Finds a workspace and verifies the user is an admin."""
        workspace = await self.workspaces_collection.find_one({"workspace_id": workspace_id})
        if not workspace:
            raise WorkspaceNotFound()

        user_role = self.get_user_role(user_id, workspace)
        if user_role != "admin":
            raise InsufficientPermissions("This action requires admin privileges.")

        return workspace

    def get_user_role(self, user_id: str, workspace: Dict[str, Any]) -> Optional[str]:
        """Gets a user's role within a specific workspace document."""
        for member in workspace.get("members", []):
            if member["user_id"] == user_id:
                return member["role"]
        return None


# Global WorkspaceManager instance
workspace_manager = WorkspaceManager()
