"""Celery tasks for LangGraph workflows.

Note: Workflow functionality is currently disabled.
"""
from typing import Dict, Any
from datetime import datetime, timezone

from .celery_app import celery_app
from ..managers.logging_manager import get_logger
from ..database import db_manager

logger = get_logger(prefix="[WorkflowTasks]")


@celery_app.task(name="execute_multi_step_workflow", bind=True)
def execute_multi_step_workflow(
    self,
    user_context_dict: Dict[str, Any],
    user_message: str,
    workflow_id: str
) -> Dict[str, Any]:
    """Execute multi-step workflow asynchronously.

    Note: Workflow functionality is currently disabled.
    """
    logger.warning(f"Multi-step workflow requested but system is disabled: {workflow_id}")
    return {
        "error": "Workflow system is currently disabled",
        "workflow_id": workflow_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@celery_app.task(name="execute_shopping_workflow", bind=True)
def execute_shopping_workflow(
    self,
    user_context_dict: Dict[str, Any],
    user_message: str,
    workflow_id: str
) -> Dict[str, Any]:
    """Execute shopping workflow asynchronously.

    Note: Workflow functionality is currently disabled.
    """
    logger.warning(f"Shopping workflow requested but system is disabled: {workflow_id}")
    return {
        "error": "Workflow system is currently disabled",
        "workflow_id": workflow_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@celery_app.task(name="monitor_workflow_progress")
def monitor_workflow_progress(workflow_id: str) -> Dict[str, Any]:
    """Monitor and report workflow progress.

    Args:
        workflow_id: Workflow ID to monitor

    Returns:
        Progress status
    """
    try:
        workflow = db_manager.get_collection("workflows").find_one(
            {"workflow_id": workflow_id}
        )

        if not workflow:
            return {"error": "Workflow not found"}

        progress = {
            "workflow_id": workflow_id,
            "status": workflow["status"],
            "started_at": workflow.get("started_at"),
            "completed_at": workflow.get("completed_at"),
            "error": workflow.get("error")
        }

        return progress

    except Exception as e:
        logger.error(f"Error monitoring workflow: {e}", exc_info=True)
        return {"error": str(e)}
