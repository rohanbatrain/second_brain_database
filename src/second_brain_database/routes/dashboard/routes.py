"""
Dashboard API routes.

FastAPI routes for dashboard preferences, widget management, and aggregated data.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.routes.dashboard.models import (
    CreateWidgetRequest,
    DashboardPreferencesResponse,
    UpdateLayoutRequest,
    UpdateWidgetRequest,
    WidgetConfig,
    WidgetPosition,
    WidgetResponse,
)
from second_brain_database.utils.logging_utils import (
    ip_address_context,
    log_error_with_context,
    request_id_context,
    user_id_context,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = get_logger(prefix="[DASHBOARD]")

DASHBOARD_COLLECTION = "dashboard_preferences"


def _get_context_key(context: str, context_id: Optional[str] = None) -> str:
    """Generate context key for layout storage."""
    if context == "personal":
        return "personal"
    elif context in ["family", "team"] and context_id:
        return f"{context}:{context_id}"
    return context


def _setup_request_context(request: Request, current_user: dict) -> str:
    """Setup logging context and return request ID."""
    request_id = str(datetime.now(timezone.utc).timestamp()).replace(".", "")[-8:]
    client_ip = security_manager.get_client_ip(request)
    username = current_user["username"]

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    return request_id


@router.get(
    "/preferences/{context}",
    response_model=DashboardPreferencesResponse,
    summary="Get dashboard preferences for context",
)
async def get_dashboard_preferences(
    request: Request,
    context: str = Path(..., pattern="^(personal|family|team)$"),
    context_id: Optional[str] = Query(None, description="Family ID or Workspace ID"),
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get dashboard preferences for a specific context.

    Returns the widget layout and configuration for the specified dashboard context.
    If no preferences exist, returns default empty layout.

    Args:
        request: FastAPI request
        context: Dashboard context (personal, family, team)
        context_id: Optional family or workspace ID
        current_user: Authenticated user

    Returns:
        Dashboard preferences with widget configurations
    """
    request_id = _setup_request_context(request, current_user)
    username = current_user["username"]
    user_id = str(current_user.get("_id", current_user.get("id", "")))

    logger.info(
        "[%s] GET /dashboard/preferences/%s - User: %s, ContextID: %s",
        request_id,
        context,
        username,
        context_id,
    )

    try:
        collection = db_manager.get_collection(DASHBOARD_COLLECTION)
        context_key = _get_context_key(context, context_id)

        # Find user's dashboard preferences
        prefs = await collection.find_one({"user_id": user_id})

        if not prefs or context_key not in prefs.get("layouts", {}):
            # Return default empty layout
            return DashboardPreferencesResponse(
                context=context, context_id=context_id, widgets=[], grid_columns=12
            )

        layout = prefs["layouts"][context_key]
        return DashboardPreferencesResponse(
            context=context,
            context_id=context_id,
            widgets=layout.get("widgets", []),
            grid_columns=layout.get("grid_columns", 12),
        )

    except Exception as e:
        logger.error("[%s] Failed to get dashboard preferences: %s", request_id, str(e))
        log_error_with_context(
            e,
            context={"user": username, "request_id": request_id, "context": context},
            operation="get_dashboard_preferences",
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard preferences")


@router.put(
    "/preferences/{context}",
    response_model=DashboardPreferencesResponse,
    summary="Update dashboard layout",
)
async def update_dashboard_layout(
    request: Request,
    context: str = Path(..., pattern="^(personal|family|team)$"),
    layout_data: UpdateLayoutRequest = Body(...),
    context_id: Optional[str] = Query(None, description="Family ID or Workspace ID"),
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Update the entire dashboard layout for a context.

    Replaces the widget configuration for the specified dashboard context.

    Args:
        request: FastAPI request
        context: Dashboard context
        layout_data: New layout configuration
        context_id: Optional family or workspace ID
        current_user: Authenticated user

    Returns:
        Updated dashboard preferences
    """
    request_id = _setup_request_context(request, current_user)
    username = current_user["username"]
    user_id = str(current_user.get("_id", current_user.get("id", "")))

    logger.info(
        "[%s] PUT /dashboard/preferences/%s - User: %s, Widgets: %d",
        request_id,
        context,
        username,
        len(layout_data.widgets),
    )

    try:
        collection = db_manager.get_collection(DASHBOARD_COLLECTION)
        context_key = _get_context_key(context, context_id)

        layout_dict = {
            "context": context,
            "context_id": context_id,
            "widgets": [w.model_dump() for w in layout_data.widgets],
            "grid_columns": layout_data.grid_columns or 12,
        }

        # Upsert dashboard preferences
        await collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "username": username,
                    f"layouts.{context_key}": layout_dict,
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {"user_id": user_id, "created_at": datetime.utcnow()},
            },
            upsert=True,
        )

        logger.info("[%s] Dashboard layout updated for context: %s", request_id, context_key)

        return DashboardPreferencesResponse(
            context=context,
            context_id=context_id,
            widgets=layout_data.widgets,
            grid_columns=layout_data.grid_columns or 12,
        )

    except Exception as e:
        logger.error("[%s] Failed to update dashboard layout: %s", request_id, str(e))
        log_error_with_context(
            e,
            context={"user": username, "request_id": request_id, "context": context},
            operation="update_dashboard_layout",
        )
        raise HTTPException(status_code=500, detail="Failed to update dashboard layout")


@router.post("/widgets", response_model=WidgetResponse, summary="Add widget to dashboard")
async def add_widget(
    request: Request,
    widget_data: CreateWidgetRequest = Body(...),
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Add a new widget to the dashboard.

    Creates a new widget instance and adds it to the specified dashboard context.
    If no position is provided, the widget is placed at the next available position.

    Args:
        request: FastAPI request
        widget_data: Widget creation data
        current_user: Authenticated user

    Returns:
        Created widget configuration
    """
    request_id = _setup_request_context(request, current_user)
    username = current_user["username"]
    user_id = str(current_user.get("_id", current_user.get("id", "")))

    logger.info(
        "[%s] POST /dashboard/widgets - User: %s, Type: %s",
        request_id,
        username,
        widget_data.widget_type,
    )

    try:
        collection = db_manager.get_collection(DASHBOARD_COLLECTION)
        context_key = _get_context_key(widget_data.context, widget_data.context_id)

        # Generate widget ID
        widget_id = str(uuid4())

        # Determine position
        if widget_data.position:
            position = widget_data.position
        else:
            # Auto-position: find next available spot
            prefs = await collection.find_one({"user_id": user_id})
            existing_widgets = []
            if prefs and context_key in prefs.get("layouts", {}):
                existing_widgets = prefs["layouts"][context_key].get("widgets", [])

            # Simple auto-positioning: place at bottom
            max_y = max([w.get("position", {}).get("y", 0) + w.get("position", {}).get("h", 1) 
                        for w in existing_widgets], default=0)
            position = WidgetPosition(x=0, y=max_y, w=6, h=4)

        # Create widget config
        widget_config = WidgetConfig(
            widget_id=widget_id,
            widget_type=widget_data.widget_type,
            position=position,
            visible=True,
            settings=widget_data.settings,
        )

        # Add widget to layout
        await collection.update_one(
            {"user_id": user_id},
            {
                "$push": {f"layouts.{context_key}.widgets": widget_config.model_dump()},
                "$set": {
                    "username": username,
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": datetime.utcnow(),
                    f"layouts.{context_key}.context": widget_data.context,
                    f"layouts.{context_key}.context_id": widget_data.context_id,
                    f"layouts.{context_key}.grid_columns": 12,
                },
            },
            upsert=True,
        )

        logger.info("[%s] Widget added: %s (%s)", request_id, widget_id, widget_data.widget_type)

        return WidgetResponse(
            widget_id=widget_id,
            widget_type=widget_data.widget_type,
            position=position,
            visible=True,
            settings=widget_data.settings,
        )

    except Exception as e:
        logger.error("[%s] Failed to add widget: %s", request_id, str(e))
        log_error_with_context(
            e,
            context={"user": username, "request_id": request_id, "widget_type": widget_data.widget_type},
            operation="add_widget",
        )
        raise HTTPException(status_code=500, detail="Failed to add widget")


@router.put("/widgets/{widget_id}", response_model=WidgetResponse, summary="Update widget configuration")
async def update_widget(
    request: Request,
    widget_id: str = Path(..., description="Widget instance ID"),
    update_data: UpdateWidgetRequest = Body(...),
    context: str = Query(..., pattern="^(personal|family|team)$"),
    context_id: Optional[str] = Query(None),
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Update widget configuration.

    Updates position, visibility, or settings for a specific widget.

    Args:
        request: FastAPI request
        widget_id: Widget instance ID
        update_data: Update data
        context: Dashboard context
        context_id: Optional family or workspace ID
        current_user: Authenticated user

    Returns:
        Updated widget configuration
    """
    request_id = _setup_request_context(request, current_user)
    username = current_user["username"]
    user_id = str(current_user.get("_id", current_user.get("id", "")))

    logger.info("[%s] PUT /dashboard/widgets/%s - User: %s", request_id, widget_id, username)

    try:
        collection = db_manager.get_collection(DASHBOARD_COLLECTION)
        context_key = _get_context_key(context, context_id)

        # Build update operations
        update_ops = {}
        if update_data.position is not None:
            update_ops[f"layouts.{context_key}.widgets.$[widget].position"] = update_data.position.model_dump()
        if update_data.visible is not None:
            update_ops[f"layouts.{context_key}.widgets.$[widget].visible"] = update_data.visible
        if update_data.settings is not None:
            update_ops[f"layouts.{context_key}.widgets.$[widget].settings"] = update_data.settings

        if not update_ops:
            raise HTTPException(status_code=400, detail="No update data provided")

        update_ops["updated_at"] = datetime.utcnow()

        # Update widget
        result = await collection.update_one(
            {"user_id": user_id},
            {"$set": update_ops},
            array_filters=[{"widget.widget_id": widget_id}],
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Widget not found")

        # Fetch updated widget
        prefs = await collection.find_one({"user_id": user_id})
        if not prefs or context_key not in prefs.get("layouts", {}):
            raise HTTPException(status_code=404, detail="Widget not found")

        widgets = prefs["layouts"][context_key].get("widgets", [])
        widget = next((w for w in widgets if w["widget_id"] == widget_id), None)

        if not widget:
            raise HTTPException(status_code=404, detail="Widget not found")

        logger.info("[%s] Widget updated: %s", request_id, widget_id)

        return WidgetResponse(**widget)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[%s] Failed to update widget: %s", request_id, str(e))
        log_error_with_context(
            e,
            context={"user": username, "request_id": request_id, "widget_id": widget_id},
            operation="update_widget",
        )
        raise HTTPException(status_code=500, detail="Failed to update widget")


@router.delete("/widgets/{widget_id}", summary="Delete widget from dashboard")
async def delete_widget(
    request: Request,
    widget_id: str = Path(..., description="Widget instance ID"),
    context: str = Query(..., pattern="^(personal|family|team)$"),
    context_id: Optional[str] = Query(None),
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Delete a widget from the dashboard.

    Removes the specified widget from the dashboard layout.

    Args:
        request: FastAPI request
        widget_id: Widget instance ID
        context: Dashboard context
        context_id: Optional family or workspace ID
        current_user: Authenticated user

    Returns:
        Success message
    """
    request_id = _setup_request_context(request, current_user)
    username = current_user["username"]
    user_id = str(current_user.get("_id", current_user.get("id", "")))

    logger.info("[%s] DELETE /dashboard/widgets/%s - User: %s", request_id, widget_id, username)

    try:
        collection = db_manager.get_collection(DASHBOARD_COLLECTION)
        context_key = _get_context_key(context, context_id)

        # Remove widget from array
        result = await collection.update_one(
            {"user_id": user_id},
            {
                "$pull": {f"layouts.{context_key}.widgets": {"widget_id": widget_id}},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Widget not found")

        logger.info("[%s] Widget deleted: %s", request_id, widget_id)

        return {"status": "success", "message": "Widget deleted", "widget_id": widget_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[%s] Failed to delete widget: %s", request_id, str(e))
        log_error_with_context(
            e,
            context={"user": username, "request_id": request_id, "widget_id": widget_id},
            operation="delete_widget",
        )
        raise HTTPException(status_code=500, detail="Failed to delete widget")
