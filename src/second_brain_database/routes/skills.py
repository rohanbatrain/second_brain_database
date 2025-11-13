"""
Skill Log API routes.

Comprehensive FastAPI router for skill tracking and logging functionality,
following established patterns from workspace routes.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer

from second_brain_database.routes.auth.services.auth.login import get_current_user
from second_brain_database.routes.auth.dependencies import get_current_user_dep as get_current_user
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.skill_manager import (
    SkillError,
    SkillHierarchyError,
    SkillManager,
    SkillNotFoundError,
    SkillValidationError,
    skill_manager,
)
from second_brain_database.models.skill_models import (
    CreateSkillLogRequest,
    CreateSkillRequest,
    LinkSkillRequest,
    SkillAnalyticsSummary,
    SkillLogResponse,
    SkillResponse,
    SkillTreeNode,
    UpdateSkillRequest,
)

# Router setup following workspace routes pattern
router = APIRouter(
    prefix="/api/v1/skills",
    tags=["skills"],
    dependencies=[Depends(HTTPBearer())]
)

# Initialize logger
logger = get_logger(prefix="[Skill Routes]")

# Rate limiting following workspace patterns
# analytics_rate_limit = RateLimit(requests=10, window=60)  # 10 requests per minute for analytics


async def get_skill_manager() -> SkillManager:
    """Dependency injection for skill manager following codebase patterns."""
    return skill_manager


@router.post(
    "/",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new skill",
    description="Create a new skill with optional parent relationships and metadata."
)
async def create_skill(
    skill_data: CreateSkillRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> SkillResponse:
    """Create a new skill."""
    try:
        logger.info(
            "API: Creating skill",
            extra={
                "user_id": current_user["user_id"],
                "skill_name": skill_data.name,
                "endpoint": "/api/v1/skills/"
            }
        )

        skill_doc = await manager.create_skill(skill_data, current_user["user_id"])

        # Convert to response format
        response = SkillResponse(
            skill_id=skill_doc.skill_id,
            name=skill_doc.name,
            description=skill_doc.description,
            parent_skill_ids=skill_doc.parent_skill_ids,
            child_skill_ids=[],  # Will be computed by get_skill
            tags=skill_doc.tags,
            metadata=skill_doc.metadata,
            created_at=skill_doc.created_at.isoformat(),
            updated_at=skill_doc.updated_at.isoformat()
        )

        logger.info(
            "API: Skill created successfully",
            extra={
                "skill_id": response.skill_id,
                "user_id": current_user["user_id"]
            }
        )

        return response

    except SkillValidationError as e:
        logger.warning(
            "API: Skill validation error",
            extra={
                "user_id": current_user["user_id"],
                "error_code": e.error_code,
                "details": e.details
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except SkillHierarchyError as e:
        logger.warning(
            "API: Skill hierarchy error",
            extra={
                "user_id": current_user["user_id"],
                "error_code": e.error_code,
                "details": e.details
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error creating skill",
            extra={
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating skill"
        )


@router.get(
    "/",
    response_model=Dict[str, Any],
    summary="List user skills",
    description="Get paginated list of user's skills with optional analytics."
)
async def list_skills(
    include_analytics: bool = Query(False, description="Include analytics data"),
    skip: int = Query(0, ge=0, description="Number of skills to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of skills to return"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> Dict[str, Any]:
    """List user's skills with pagination."""
    try:
        logger.info(
            "API: Listing skills",
            extra={
                "user_id": current_user["user_id"],
                "include_analytics": include_analytics,
                "skip": skip,
                "limit": limit
            }
        )

        result = await manager.list_skills(
            current_user["user_id"],
            include_analytics=include_analytics,
            skip=skip,
            limit=limit
        )

        # Convert to response format
        skills_response = []
        for skill_data in result["skills"]:
            skill_response = SkillResponse(
                skill_id=skill_data["skill_id"],
                name=skill_data["name"],
                description=skill_data["description"],
                parent_skill_ids=skill_data["parent_skill_ids"],
                child_skill_ids=skill_data["child_skill_ids"],
                tags=skill_data["tags"],
                metadata=skill_data["metadata"],
                created_at=skill_data["created_at"].isoformat(),
                updated_at=skill_data["updated_at"].isoformat(),
                analytics=skill_data.get("analytics")
            )
            skills_response.append(skill_response.model_dump())

        return {
            "skills": skills_response,
            "total_count": result["total_count"],
            "skip": result["skip"],
            "limit": result["limit"]
        }

    except Exception as e:
        logger.error(
            "API: Unexpected error listing skills",
            extra={
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while listing skills"
        )


@router.get(
    "/tree",
    response_model=List[SkillTreeNode],
    summary="Get skill hierarchy tree",
    description="Get hierarchical tree view of all user skills."
)
async def get_skill_tree(
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> List[SkillTreeNode]:
    """Get hierarchical tree view of skills."""
    try:
        logger.info(
            "API: Getting skill tree",
            extra={"user_id": current_user["user_id"]}
        )

        tree_data = await manager.get_skill_tree(current_user["user_id"])

        # Convert to SkillTreeNode format
        def convert_to_tree_node(data: Dict[str, Any]) -> SkillTreeNode:
            skill_response = SkillResponse(
                skill_id=data["skill_id"],
                name=data["name"],
                description=data["description"],
                parent_skill_ids=[],  # Not needed in tree view
                child_skill_ids=[],   # Not needed in tree view
                tags=[],             # Not needed in tree view
                metadata={},         # Not needed in tree view
                created_at="",       # Not needed in tree view
                updated_at=""        # Not needed in tree view
            )

            return SkillTreeNode(
                skill=skill_response,
                children=[convert_to_tree_node(child) for child in data["children"]]
            )

        return [convert_to_tree_node(node) for node in tree_data]

    except Exception as e:
        logger.error(
            "API: Unexpected error getting skill tree",
            extra={
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while getting skill tree"
        )


@router.get(
    "/{skill_id}",
    response_model=SkillResponse,
    summary="Get skill details",
    description="Get detailed information about a specific skill."
)
async def get_skill(
    skill_id: str,
    include_analytics: bool = Query(False, description="Include analytics data"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> SkillResponse:
    """Get skill details."""
    try:
        logger.info(
            "API: Getting skill details",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "include_analytics": include_analytics
            }
        )

        skill_data = await manager.get_skill(
            skill_id,
            current_user["user_id"],
            include_analytics=include_analytics
        )

        return SkillResponse(
            skill_id=skill_data["skill_id"],
            name=skill_data["name"],
            description=skill_data["description"],
            parent_skill_ids=skill_data["parent_skill_ids"],
            child_skill_ids=skill_data["child_skill_ids"],
            tags=skill_data["tags"],
            metadata=skill_data["metadata"],
            created_at=skill_data["created_at"].isoformat(),
            updated_at=skill_data["updated_at"].isoformat(),
            analytics=skill_data.get("analytics")
        )

    except SkillNotFoundError as e:
        logger.warning(
            "API: Skill not found",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error getting skill",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while getting skill"
        )


@router.put(
    "/{skill_id}",
    response_model=SkillResponse,
    summary="Update skill",
    description="Update an existing skill's information."
)
async def update_skill(
    skill_id: str,
    update_data: UpdateSkillRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> SkillResponse:
    """Update skill information."""
    try:
        logger.info(
            "API: Updating skill",
            extra={"skill_id": skill_id, "user_id": current_user["user_id"]}
        )

        updated_skill = await manager.update_skill(skill_id, update_data, current_user["user_id"])

        return SkillResponse(
            skill_id=updated_skill.skill_id,
            name=updated_skill.name,
            description=updated_skill.description,
            parent_skill_ids=updated_skill.parent_skill_ids,
            child_skill_ids=await manager._get_child_skill_ids(skill_id, current_user["user_id"]),
            tags=updated_skill.tags,
            metadata=updated_skill.metadata,
            created_at=updated_skill.created_at.isoformat(),
            updated_at=updated_skill.updated_at.isoformat()
        )

    except SkillNotFoundError as e:
        logger.warning(
            "API: Skill not found for update",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except SkillValidationError as e:
        logger.warning(
            "API: Skill validation error on update",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code,
                "details": e.details
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error updating skill",
            extra={
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating skill"
        )


@router.delete(
    "/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete skill",
    description="Soft delete a skill (cannot delete skills with children)."
)
async def delete_skill(
    skill_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> None:
    """Delete a skill."""
    try:
        logger.info(
            "API: Deleting skill",
            extra={"skill_id": skill_id, "user_id": current_user["user_id"]}
        )

        await manager.delete_skill(skill_id, current_user["user_id"])

        logger.info(
            "API: Skill deleted successfully",
            extra={"skill_id": skill_id, "user_id": current_user["user_id"]}
        )

    except SkillNotFoundError as e:
        logger.warning(
            "API: Skill not found for deletion",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except SkillHierarchyError as e:
        logger.warning(
            "API: Cannot delete skill with children",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code,
                "details": e.details
            }
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error deleting skill",
            extra={
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting skill"
        )


@router.post(
    "/{skill_id}/link/{parent_id}",
    status_code=status.HTTP_200_OK,
    summary="Link parent skill",
    description="Link a skill to a parent skill in the hierarchy."
)
async def link_parent_skill(
    skill_id: str,
    parent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> Dict[str, str]:
    """Link a skill to a parent skill."""
    try:
        logger.info(
            "API: Linking parent skill",
            extra={
                "skill_id": skill_id,
                "parent_id": parent_id,
                "user_id": current_user["user_id"]
            }
        )

        await manager.link_parent_skill(skill_id, parent_id, current_user["user_id"])

        logger.info(
            "API: Parent skill linked successfully",
            extra={
                "skill_id": skill_id,
                "parent_id": parent_id,
                "user_id": current_user["user_id"]
            }
        )

        return {"message": "Parent skill linked successfully"}

    except (SkillNotFoundError, SkillHierarchyError) as e:
        logger.warning(
            "API: Error linking parent skill",
            extra={
                "skill_id": skill_id,
                "parent_id": parent_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code,
                "details": e.details
            }
        )
        status_code = status.HTTP_404_NOT_FOUND if isinstance(e, SkillNotFoundError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error linking parent skill",
            extra={
                "skill_id": skill_id,
                "parent_id": parent_id,
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while linking parent skill"
        )


@router.delete(
    "/{skill_id}/link/{parent_id}",
    status_code=status.HTTP_200_OK,
    summary="Unlink parent skill",
    description="Remove the link between a skill and its parent skill."
)
async def unlink_parent_skill(
    skill_id: str,
    parent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> Dict[str, str]:
    """Unlink a skill from a parent skill."""
    try:
        logger.info(
            "API: Unlinking parent skill",
            extra={
                "skill_id": skill_id,
                "parent_id": parent_id,
                "user_id": current_user["user_id"]
            }
        )

        await manager.unlink_parent_skill(skill_id, parent_id, current_user["user_id"])

        logger.info(
            "API: Parent skill unlinked successfully",
            extra={
                "skill_id": skill_id,
                "parent_id": parent_id,
                "user_id": current_user["user_id"]
            }
        )

        return {"message": "Parent skill unlinked successfully"}

    except SkillError as e:
        logger.warning(
            "API: Error unlinking parent skill",
            extra={
                "skill_id": skill_id,
                "parent_id": parent_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code,
                "details": e.details
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error unlinking parent skill",
            extra={
                "skill_id": skill_id,
                "parent_id": parent_id,
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while unlinking parent skill"
        )


# --- Skill Logging Endpoints ---

@router.get(
    "/{skill_id}/logs",
    response_model=List[SkillLogResponse],
    summary="Get skill logs",
    description="Get paginated log entries for a specific skill."
)
async def get_skill_logs(
    skill_id: str,
    skip: int = Query(0, ge=0, description="Number of log entries to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of log entries to return"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> List[SkillLogResponse]:
    """Get skill log entries."""
    try:
        logger.info(
            "API: Getting skill logs",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "skip": skip,
                "limit": limit
            }
        )

        logs_data = await manager.get_skill_logs(
            skill_id,
            current_user["user_id"],
            skip=skip,
            limit=limit
        )

        # Convert to response format
        logs_response = []
        for log_data in logs_data:
            log_response = SkillLogResponse(
                log_id=log_data["log_id"],
                skill_id=skill_id,
                project_id=log_data["project_id"],
                progress_state=log_data["progress_state"],
                numeric_level=log_data["numeric_level"],
                timestamp=log_data["timestamp"],
                notes=log_data["notes"],
                context=log_data["context"],
                created_at=log_data["created_at"]
            )
            logs_response.append(log_response)

        return logs_response

    except SkillNotFoundError as e:
        logger.warning(
            "API: Skill not found for logs",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error getting skill logs",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while getting skill logs"
        )


@router.post(
    "/{skill_id}/logs",
    response_model=SkillLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add skill log entry",
    description="Add a new log entry to track skill progress."
)
async def add_skill_log(
    skill_id: str,
    log_data: CreateSkillLogRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> SkillLogResponse:
    """Add a log entry to a skill."""
    try:
        logger.info(
            "API: Adding skill log entry",
            extra={"skill_id": skill_id, "user_id": current_user["user_id"]}
        )

        log_entry = await manager.add_skill_log(skill_id, log_data, current_user["user_id"])

        logger.info(
            "API: Skill log entry added successfully",
            extra={
                "skill_id": skill_id,
                "log_id": log_entry.log_id,
                "user_id": current_user["user_id"]
            }
        )

        return SkillLogResponse(
            log_id=log_entry.log_id,
            skill_id=skill_id,
            project_id=log_entry.project_id,
            progress_state=log_entry.progress_state,
            numeric_level=log_entry.numeric_level,
            timestamp=log_entry.timestamp.isoformat(),
            notes=log_entry.notes,
            context=log_entry.context,
            created_at=log_entry.created_at.isoformat()
        )

    except SkillNotFoundError as e:
        logger.warning(
            "API: Skill not found for log addition",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except SkillValidationError as e:
        logger.warning(
            "API: Skill log validation error",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code,
                "details": e.details
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error adding skill log",
            extra={
                "skill_id": skill_id,
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while adding skill log"
        )


@router.put(
    "/{skill_id}/logs/{log_id}",
    status_code=status.HTTP_200_OK,
    summary="Update skill log entry",
    description="Update an existing skill log entry."
)
async def update_skill_log(
    skill_id: str,
    log_id: str,
    update_data: Dict[str, Any],  # Simplified - could use a proper model
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> Dict[str, str]:
    """Update a skill log entry."""
    try:
        logger.info(
            "API: Updating skill log entry",
            extra={
                "skill_id": skill_id,
                "log_id": log_id,
                "user_id": current_user["user_id"]
            }
        )

        await manager.update_skill_log(skill_id, log_id, update_data, current_user["user_id"])

        logger.info(
            "API: Skill log entry updated successfully",
            extra={
                "skill_id": skill_id,
                "log_id": log_id,
                "user_id": current_user["user_id"]
            }
        )

        return {"message": "Skill log entry updated successfully"}

    except SkillError as e:
        logger.warning(
            "API: Error updating skill log",
            extra={
                "skill_id": skill_id,
                "log_id": log_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code,
                "details": e.details
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error updating skill log",
            extra={
                "skill_id": skill_id,
                "log_id": log_id,
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while updating skill log"
        )


@router.delete(
    "/{skill_id}/logs/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete skill log entry",
    description="Delete a skill log entry."
)
async def delete_skill_log(
    skill_id: str,
    log_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> None:
    """Delete a skill log entry."""
    try:
        logger.info(
            "API: Deleting skill log entry",
            extra={
                "skill_id": skill_id,
                "log_id": log_id,
                "user_id": current_user["user_id"]
            }
        )

        await manager.delete_skill_log(skill_id, log_id, current_user["user_id"])

        logger.info(
            "API: Skill log entry deleted successfully",
            extra={
                "skill_id": skill_id,
                "log_id": log_id,
                "user_id": current_user["user_id"]
            }
        )

    except SkillError as e:
        logger.warning(
            "API: Error deleting skill log",
            extra={
                "skill_id": skill_id,
                "log_id": log_id,
                "user_id": current_user["user_id"],
                "error_code": e.error_code,
                "details": e.details
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.message,
                "error_code": e.error_code,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            "API: Unexpected error deleting skill log",
            extra={
                "skill_id": skill_id,
                "log_id": log_id,
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while deleting skill log"
        )


# --- Analytics Endpoints ---

@router.get(
    "/analytics/summary",
    response_model=SkillAnalyticsSummary,
    summary="Get skill analytics summary",
    description="Get comprehensive analytics summary for user's skills."
)
async def get_analytics_summary(
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: SkillManager = Depends(get_skill_manager)
) -> SkillAnalyticsSummary:
    """Get analytics summary for user."""
    try:
        logger.info(
            "API: Getting analytics summary",
            extra={"user_id": current_user["user_id"]}
        )

        summary_data = await manager.get_analytics_summary(current_user["user_id"])

        return SkillAnalyticsSummary(**summary_data)

    except Exception as e:
        logger.error(
            "API: Unexpected error getting analytics summary",
            extra={
                "user_id": current_user["user_id"],
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while getting analytics summary"
        )