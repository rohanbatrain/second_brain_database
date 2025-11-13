"""
Skill Manager for the Skill Log feature.

Provides comprehensive skill tracking, logging, and analytics functionality
following established codebase patterns.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import ValidationError

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.skill_models import (
    CreateSkillLogRequest,
    CreateSkillRequest,
    SkillAnalyticsStats,
    SkillDocument,
    SkillLogContext,
    SkillLogDocument,
    SkillMetadata,
    SkillRollupStats,
    UpdateSkillRequest,
)


class SkillError(Exception):
    """Base exception for skill-related operations."""

    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class SkillNotFoundError(SkillError):
    """Raised when a skill is not found."""

    def __init__(self, skill_id: str, user_id: str):
        super().__init__(
            f"Skill {skill_id} not found for user {user_id}",
            "SKILL_NOT_FOUND",
            {"skill_id": skill_id, "user_id": user_id}
        )


class SkillValidationError(SkillError):
    """Raised when skill data validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "SKILL_VALIDATION_ERROR", details)


class SkillHierarchyError(SkillError):
    """Raised when hierarchy operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "SKILL_HIERARCHY_ERROR", details)


class SkillManager:
    """
    Unified manager for skill tracking, logging, and analytics.

    Follows established patterns from workspace_manager.py:
    - Dependency injection in __init__
    - Custom exception hierarchy
    - Comprehensive logging
    - Async operations throughout
    """

    def __init__(self, db_manager: Any = None, logging_manager: Any = None):
        """Initialize with dependency injection following codebase patterns."""
        self.db_manager = db_manager or db_manager
        self.logging_manager = logging_manager or get_logger(prefix="[SkillManager]")
        self._collection: Optional[AsyncIOMotorCollection] = None

    @property
    def collection(self) -> AsyncIOMotorCollection:
        """Lazy-loaded collection property following workspace_manager pattern."""
        if self._collection is None:
            self._collection = self.db_manager.get_collection("user_skills")
        return self._collection

    async def _validate_skill_ownership(self, skill_id: str, user_id: str) -> SkillDocument:
        """Validate skill exists and belongs to user."""
        skill_doc = await self.collection.find_one(
            {"skill_id": skill_id, "user_id": user_id, "is_active": True}
        )

        if not skill_doc:
            raise SkillNotFoundError(skill_id, user_id)

        try:
            return SkillDocument(**skill_doc)
        except ValidationError as e:
            self.logging_manager.error(
                "Skill document validation failed",
                extra={
                    "skill_id": skill_id,
                    "user_id": user_id,
                    "validation_errors": e.errors()
                }
            )
            raise SkillValidationError("Invalid skill document structure")

    async def _detect_circular_reference(self, skill_id: str, parent_id: str, user_id: str) -> bool:
        """Detect circular references in skill hierarchy."""
        visited = set()
        current_id = parent_id

        while current_id:
            if current_id in visited:
                return True  # Circular reference detected
            if current_id == skill_id:
                return True  # Would create a cycle

            visited.add(current_id)
            parent_doc = await self.collection.find_one(
                {"skill_id": current_id, "user_id": user_id, "is_active": True},
                {"parent_skill_ids": 1}
            )

            if not parent_doc or not parent_doc.get("parent_skill_ids"):
                break

            # For simplicity, check only first parent (can be extended for multiple)
            current_id = parent_doc["parent_skill_ids"][0] if parent_doc["parent_skill_ids"] else None

        return False

    async def create_skill(self, skill_data: CreateSkillRequest, user_id: str) -> SkillDocument:
        """Create a new skill with validation."""
        self.logging_manager.info(
            "Creating new skill",
            extra={"user_id": user_id, "skill_name": skill_data.name}
        )

        # Validate parent skills exist and belong to user
        if skill_data.parent_skill_ids:
            for parent_id in skill_data.parent_skill_ids:
                await self._validate_skill_ownership(parent_id, user_id)

        # Check for circular references
        skill_id = str(uuid.uuid4())
        for parent_id in skill_data.parent_skill_ids:
            if await self._detect_circular_reference(skill_id, parent_id, user_id):
                raise SkillHierarchyError(
                    f"Linking to parent {parent_id} would create a circular reference"
                )

        # Create skill document
        now = datetime.utcnow()
        skill_doc = SkillDocument(
            skill_id=skill_id,
            user_id=user_id,
            name=skill_data.name,
            description=skill_data.description,
            parent_skill_ids=skill_data.parent_skill_ids,
            tags=skill_data.tags,
            metadata=skill_data.metadata or SkillMetadata(),
            created_at=now,
            updated_at=now,
            is_active=True,
            logs=[]
        )

        try:
            await self.collection.insert_one(skill_doc.model_dump())
            self.logging_manager.info(
                "Skill created successfully",
                extra={"skill_id": skill_id, "user_id": user_id}
            )
            return skill_doc
        except Exception as e:
            self.logging_manager.error(
                "Failed to create skill",
                extra={"skill_id": skill_id, "user_id": user_id, "error": str(e)}
            )
            raise SkillError(f"Failed to create skill: {str(e)}", "SKILL_CREATION_FAILED")

    async def get_skill(self, skill_id: str, user_id: str, include_analytics: bool = False) -> Dict[str, Any]:
        """Get skill with optional analytics."""
        skill_doc = await self._validate_skill_ownership(skill_id, user_id)

        result = skill_doc.model_dump()

        if include_analytics:
            result["analytics"] = await self._compute_skill_analytics(skill_id, user_id)

        # Add computed child_skill_ids
        result["child_skill_ids"] = await self._get_child_skill_ids(skill_id, user_id)

        return result

    async def update_skill(self, skill_id: str, update_data: UpdateSkillRequest, user_id: str) -> SkillDocument:
        """Update an existing skill."""
        self.logging_manager.info(
            "Updating skill",
            extra={"skill_id": skill_id, "user_id": user_id}
        )

        # Validate skill exists
        await self._validate_skill_ownership(skill_id, user_id)

        # Prepare update document
        update_doc = {"$set": {"updated_at": datetime.utcnow()}}

        if update_data.name is not None:
            update_doc["$set"]["name"] = update_data.name
        if update_data.description is not None:
            update_doc["$set"]["description"] = update_data.description
        if update_data.tags is not None:
            update_doc["$set"]["tags"] = update_data.tags
        if update_data.metadata is not None:
            update_doc["$set"]["metadata"] = update_data.metadata.model_dump()

        try:
            result = await self.collection.update_one(
                {"skill_id": skill_id, "user_id": user_id},
                update_doc
            )

            if result.modified_count == 0:
                self.logging_manager.warning(
                    "No changes made to skill",
                    extra={"skill_id": skill_id, "user_id": user_id}
                )

            # Return updated skill
            updated_doc = await self.collection.find_one(
                {"skill_id": skill_id, "user_id": user_id}
            )
            return SkillDocument(**updated_doc)

        except Exception as e:
            self.logging_manager.error(
                "Failed to update skill",
                extra={"skill_id": skill_id, "user_id": user_id, "error": str(e)}
            )
            raise SkillError(f"Failed to update skill: {str(e)}", "SKILL_UPDATE_FAILED")

    async def delete_skill(self, skill_id: str, user_id: str) -> bool:
        """Soft delete a skill."""
        self.logging_manager.info(
            "Soft deleting skill",
            extra={"skill_id": skill_id, "user_id": user_id}
        )

        # Check if skill has children
        child_count = await self.collection.count_documents(
            {"user_id": user_id, "parent_skill_ids": skill_id, "is_active": True}
        )

        if child_count > 0:
            raise SkillHierarchyError(
                f"Cannot delete skill with {child_count} child skills. Unlink children first."
            )

        result = await self.collection.update_one(
            {"skill_id": skill_id, "user_id": user_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )

        if result.modified_count == 0:
            raise SkillNotFoundError(skill_id, user_id)

        self.logging_manager.info(
            "Skill soft deleted",
            extra={"skill_id": skill_id, "user_id": user_id}
        )
        return True

    async def list_skills(self, user_id: str, include_analytics: bool = False,
                         skip: int = 0, limit: int = 50) -> Dict[str, Any]:
        """List user's skills with pagination."""
        query = {"user_id": user_id, "is_active": True}
        total_count = await self.collection.count_documents(query)

        cursor = self.collection.find(query).sort("updated_at", -1).skip(skip).limit(limit)

        skills = []
        async for doc in cursor:
            skill_data = SkillDocument(**doc).model_dump()

            if include_analytics:
                skill_data["analytics"] = await self._compute_skill_analytics(doc["skill_id"], user_id)

            # Add computed child_skill_ids
            skill_data["child_skill_ids"] = await self._get_child_skill_ids(doc["skill_id"], user_id)

            skills.append(skill_data)

        return {
            "skills": skills,
            "total_count": total_count,
            "skip": skip,
            "limit": limit
        }

    async def link_parent_skill(self, skill_id: str, parent_id: str, user_id: str) -> bool:
        """Link a skill to a parent skill."""
        self.logging_manager.info(
            "Linking parent skill",
            extra={"skill_id": skill_id, "parent_id": parent_id, "user_id": user_id}
        )

        # Validate both skills exist
        await self._validate_skill_ownership(skill_id, user_id)
        await self._validate_skill_ownership(parent_id, user_id)

        # Check for circular reference
        if await self._detect_circular_reference(skill_id, parent_id, user_id):
            raise SkillHierarchyError(
                f"Linking to parent {parent_id} would create a circular reference"
            )

        # Prevent self-referencing
        if skill_id == parent_id:
            raise SkillHierarchyError("Cannot link skill to itself")

        result = await self.collection.update_one(
            {"skill_id": skill_id, "user_id": user_id},
            {
                "$addToSet": {"parent_skill_ids": parent_id},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        if result.modified_count == 0:
            raise SkillError("Failed to link parent skill", "LINK_FAILED")

        self.logging_manager.info(
            "Parent skill linked successfully",
            extra={"skill_id": skill_id, "parent_id": parent_id, "user_id": user_id}
        )
        return True

    async def unlink_parent_skill(self, skill_id: str, parent_id: str, user_id: str) -> bool:
        """Unlink a skill from a parent skill."""
        self.logging_manager.info(
            "Unlinking parent skill",
            extra={"skill_id": skill_id, "parent_id": parent_id, "user_id": user_id}
        )

        result = await self.collection.update_one(
            {"skill_id": skill_id, "user_id": user_id},
            {
                "$pull": {"parent_skill_ids": parent_id},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        if result.modified_count == 0:
            raise SkillError("Failed to unlink parent skill", "UNLINK_FAILED")

        self.logging_manager.info(
            "Parent skill unlinked successfully",
            extra={"skill_id": skill_id, "parent_id": parent_id, "user_id": user_id}
        )
        return True

    async def get_skill_tree(self, user_id: str) -> List[Dict[str, Any]]:
        """Get hierarchical tree view of skills."""
        # Get all skills
        all_skills = await self.collection.find(
            {"user_id": user_id, "is_active": True}
        ).to_list(None)

        # Build skill lookup map
        skill_map = {doc["skill_id"]: SkillDocument(**doc) for doc in all_skills}

        # Build tree structure
        root_skills = []
        processed = set()

        def build_tree(skill_id: str) -> Dict[str, Any]:
            if skill_id in processed:
                return None  # Avoid infinite recursion

            processed.add(skill_id)
            skill = skill_map.get(skill_id)
            if not skill:
                return None

            # Get children
            children = []
            for child_id, child_skill in skill_map.items():
                if skill_id in child_skill.parent_skill_ids:
                    child_tree = build_tree(child_id)
                    if child_tree:
                        children.append(child_tree)

            return {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "description": skill.description,
                "children": children
            }

        # Find root skills (no parents)
        for skill in skill_map.values():
            if not skill.parent_skill_ids:
                tree = build_tree(skill.skill_id)
                if tree:
                    root_skills.append(tree)

        return root_skills

    async def add_skill_log(self, skill_id: str, log_data: CreateSkillLogRequest, user_id: str) -> SkillLogDocument:
        """Add a log entry to a skill."""
        self.logging_manager.info(
            "Adding skill log entry",
            extra={"skill_id": skill_id, "user_id": user_id}
        )

        # Validate skill exists
        await self._validate_skill_ownership(skill_id, user_id)

        # Create log entry
        log_entry = SkillLogDocument(
            log_id=str(uuid.uuid4()),
            project_id=log_data.project_id,
            progress_state=log_data.progress_state,
            numeric_level=log_data.numeric_level,
            timestamp=log_data.timestamp or datetime.utcnow(),
            notes=log_data.notes,
            context=log_data.context or SkillLogContext(),
            created_at=datetime.utcnow()
        )

        # Add to embedded logs array
        result = await self.collection.update_one(
            {"skill_id": skill_id, "user_id": user_id},
            {
                "$push": {"logs": log_entry.model_dump()},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        if result.modified_count == 0:
            raise SkillError("Failed to add skill log", "LOG_ADD_FAILED")

        self.logging_manager.info(
            "Skill log added successfully",
            extra={"skill_id": skill_id, "log_id": log_entry.log_id, "user_id": user_id}
        )
        return log_entry

    async def get_skill_logs(self, skill_id: str, user_id: str,
                           skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """Get log entries for a skill."""
        skill_doc = await self._validate_skill_ownership(skill_id, user_id)

        logs = skill_doc.logs
        # Sort by timestamp descending and apply pagination
        sorted_logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)
        paginated_logs = sorted_logs[skip:skip + limit]

        return [log.model_dump() for log in paginated_logs]

    async def update_skill_log(self, skill_id: str, log_id: str,
                             update_data: Dict[str, Any], user_id: str) -> bool:
        """Update a specific log entry."""
        self.logging_manager.info(
            "Updating skill log entry",
            extra={"skill_id": skill_id, "log_id": log_id, "user_id": user_id}
        )

        # Build update query for embedded log
        update_doc = {"$set": {"updated_at": datetime.utcnow()}}

        # Set fields for the specific log entry
        for field, value in update_data.items():
            update_doc["$set"][f"logs.$.{field}"] = value

        result = await self.collection.update_one(
            {
                "skill_id": skill_id,
                "user_id": user_id,
                "logs.log_id": log_id
            },
            update_doc
        )

        if result.modified_count == 0:
            raise SkillError("Log entry not found or update failed", "LOG_UPDATE_FAILED")

        self.logging_manager.info(
            "Skill log updated successfully",
            extra={"skill_id": skill_id, "log_id": log_id, "user_id": user_id}
        )
        return True

    async def delete_skill_log(self, skill_id: str, log_id: str, user_id: str) -> bool:
        """Delete a specific log entry."""
        self.logging_manager.info(
            "Deleting skill log entry",
            extra={"skill_id": skill_id, "log_id": log_id, "user_id": user_id}
        )

        result = await self.collection.update_one(
            {"skill_id": skill_id, "user_id": user_id},
            {"$pull": {"logs": {"log_id": log_id}}}
        )

        if result.modified_count == 0:
            raise SkillError("Log entry not found", "LOG_DELETE_FAILED")

        # Update the skill's updated_at timestamp
        await self.collection.update_one(
            {"skill_id": skill_id, "user_id": user_id},
            {"$set": {"updated_at": datetime.utcnow()}}
        )

        self.logging_manager.info(
            "Skill log deleted successfully",
            extra={"skill_id": skill_id, "log_id": log_id, "user_id": user_id}
        )
        return True

    async def get_analytics_summary(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive analytics summary for user."""
        self.logging_manager.info(
            "Computing analytics summary",
            extra={"user_id": user_id}
        )

        # Get all skills with their logs
        skills_cursor = self.collection.find(
            {"user_id": user_id, "is_active": True}
        )

        total_skills = 0
        active_skills = 0
        skills_by_state = {}
        recent_activity = []
        stale_skills = []
        total_log_entries = 0
        total_hours = 0.0
        confidence_scores = []

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        async for skill_doc in skills_cursor:
            total_skills += 1
            skill = SkillDocument(**skill_doc)

            if skill.logs:
                active_skills += 1
                total_log_entries += len(skill.logs)

                # Track progress states
                if skill.logs:
                    latest_log = max(skill.logs, key=lambda x: x.timestamp)
                    state = latest_log.progress_state
                    skills_by_state[state] = skills_by_state.get(state, 0) + 1

                    # Recent activity
                    if latest_log.timestamp > thirty_days_ago:
                        recent_activity.append({
                            "skill_id": skill.skill_id,
                            "name": skill.name,
                            "last_activity": latest_log.timestamp.isoformat(),
                            "current_state": state
                        })

                    # Hours and confidence
                    for log in skill.logs:
                        if log.context and log.context.duration_hours:
                            total_hours += log.context.duration_hours
                        if log.context and log.context.confidence_level:
                            confidence_scores.append(log.context.confidence_level)
            else:
                # Stale skills (no logs ever)
                stale_skills.append({
                    "skill_id": skill.skill_id,
                    "name": skill.name,
                    "created_at": skill.created_at.isoformat()
                })

        # Sort and limit results
        recent_activity.sort(key=lambda x: x["last_activity"], reverse=True)
        recent_activity = recent_activity[:10]

        stale_skills.sort(key=lambda x: x["created_at"])
        stale_skills = stale_skills[:10]

        return {
            "total_skills": total_skills,
            "active_skills": active_skills,
            "skills_by_state": skills_by_state,
            "recent_activity": recent_activity,
            "stale_skills": stale_skills,
            "total_log_entries": total_log_entries,
            "total_hours_logged": total_hours,
            "average_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else None
        }

    async def _compute_skill_analytics(self, skill_id: str, user_id: str) -> SkillAnalyticsStats:
        """Compute analytics for a specific skill."""
        skill_doc = await self.collection.find_one(
            {"skill_id": skill_id, "user_id": user_id, "is_active": True}
        )

        if not skill_doc:
            raise SkillNotFoundError(skill_id, user_id)

        logs = skill_doc.get("logs", [])

        if not logs:
            return SkillAnalyticsStats()

        # Compute basic stats
        total_logs = len(logs)
        sorted_logs = sorted(logs, key=lambda x: x["timestamp"])
        last_log = sorted_logs[-1]

        current_state = last_log["progress_state"]
        last_activity = datetime.fromisoformat(last_log["timestamp"])

        # Project count
        projects = set()
        total_hours = 0.0
        confidence_scores = []

        for log in logs:
            if log.get("project_id"):
                projects.add(log["project_id"])

            context = log.get("context", {})
            if context.get("duration_hours"):
                total_hours += context["duration_hours"]
            if context.get("confidence_level"):
                confidence_scores.append(context["confidence_level"])

        # Child rollup stats
        child_rollup = await self._compute_child_rollup_stats(skill_id, user_id)

        return SkillAnalyticsStats(
            total_logs=total_logs,
            current_state=current_state,
            last_activity=last_activity,
            project_count=len(projects),
            total_hours=total_hours,
            average_confidence=sum(confidence_scores) / len(confidence_scores) if confidence_scores else None,
            parent_rollup=child_rollup
        )

    async def _compute_child_rollup_stats(self, skill_id: str, user_id: str) -> SkillRollupStats:
        """Compute rollup statistics for child skills."""
        # Find all children
        children_cursor = self.collection.find(
            {"user_id": user_id, "parent_skill_ids": skill_id, "is_active": True}
        )

        child_count = 0
        active_children = 0
        total_child_logs = 0
        last_activities = []

        async for child_doc in children_cursor:
            child_count += 1
            logs = child_doc.get("logs", [])

            if logs:
                active_children += 1
                total_child_logs += len(logs)

                # Track last activity
                sorted_logs = sorted(logs, key=lambda x: x["timestamp"])
                last_activities.append(datetime.fromisoformat(sorted_logs[-1]["timestamp"]))

        return SkillRollupStats(
            child_count=child_count,
            active_children=active_children,
            total_child_logs=total_child_logs,
            last_child_activity=max(last_activities) if last_activities else None
        )

    async def _get_child_skill_ids(self, skill_id: str, user_id: str) -> List[str]:
        """Get list of child skill IDs."""
        cursor = self.collection.find(
            {"user_id": user_id, "parent_skill_ids": skill_id, "is_active": True},
            {"skill_id": 1}
        )

        return [doc["skill_id"] async for doc in cursor]


# Global instance following codebase patterns
skill_manager = SkillManager()
