"""
Abuse event logging and admin review utilities for authentication abuse detection.

This module provides asynchronous functions to log, list, and resolve abuse events
related to password reset and authentication abuse. Events are stored in MongoDB
and support admin review, filtering, and resolution workflows.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from bson import ObjectId
import pymongo

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Service Abuse Events]")

# Constants
ABUSE_EVENTS_COLLECTION: str = "abuse_events"
DEFAULT_EVENT_LIMIT: int = 100


class AbuseEvent(TypedDict, total=False):
    """
    TypedDict representing an abuse event document in the abuse_events collection.

    Fields:
        email (str): The user's email address.
        ip (str): The IP address involved in the event.
        user_agent (Optional[str]): The user agent string.
        event_type (Optional[str]): 'self_abuse' or 'targeted_abuse'.
        details (Optional[str]): Freeform string for reason/context.
        whitelisted (bool): Was this (email, ip) pair whitelisted at the time?
        action_taken (Optional[str]): What action was taken.
        resolved_by_admin (bool): Has an admin reviewed/resolved this event?
        notes (Optional[str]): Admin notes.
        timestamp (str): ISO8601 timestamp of the event.
        _id (Optional[str]): Stringified MongoDB ObjectId.
    """

    email: str
    ip: str
    user_agent: Optional[str]
    event_type: Optional[str]
    details: Optional[str]
    whitelisted: bool
    action_taken: Optional[str]
    resolved_by_admin: bool
    notes: Optional[str]
    timestamp: str
    _id: Optional[str]


async def log_reset_abuse_event(
    email: str,
    ip: str,
    user_agent: Optional[str] = None,
    event_type: Optional[str] = None,  # 'self_abuse' or 'targeted_abuse'
    details: Optional[str] = None,
    whitelisted: bool = False,
    action_taken: Optional[str] = None,  # e.g., 'blocked', 'notified', 'banned', 'none'
    resolved_by_admin: bool = False,
    notes: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> None:
    """
    Log an abuse event to the abuse_events collection.

    Args:
        email (str): The user's email address.
        ip (str): The IP address involved.
        user_agent (Optional[str]): The user agent string.
        event_type (Optional[str]): 'self_abuse' or 'targeted_abuse'.
        details (Optional[str]): Freeform string for reason/context.
        whitelisted (bool): Was this (email, ip) pair whitelisted at the time?
        action_taken (Optional[str]): What action was taken.
        resolved_by_admin (bool): Has an admin reviewed/resolved this event?
        notes (Optional[str]): Admin notes.
        timestamp (Optional[datetime]): When the event occurred (defaults to now).

    Side Effects:
        Writes to MongoDB.
    """
    try:
        collection = db_manager.get_collection(ABUSE_EVENTS_COLLECTION)
        doc: AbuseEvent = {
            "email": email,
            "ip": ip,
            "user_agent": user_agent,
            "event_type": event_type,
            "details": details,
            "whitelisted": whitelisted,
            "action_taken": action_taken,
            "resolved_by_admin": resolved_by_admin,
            "notes": notes,
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        }
        await collection.insert_one(doc)
        logger.info("Abuse event logged for email=%s, ip=%s, type=%s", email, ip, event_type)
    except ImportError:
        logger.error("Failed to import required modules for logging abuse event", exc_info=True)
    except pymongo.errors.PyMongoError:
        logger.error("Failed to log abuse event", exc_info=True)


async def admin_list_abuse_events(
    email: Optional[str] = None,
    event_type: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = DEFAULT_EVENT_LIMIT,
) -> List[AbuseEvent]:
    """
    List abuse events for admin review.

    Args:
        email (Optional[str]): Filter by email.
        event_type (Optional[str]): Filter by event type.
        resolved (Optional[bool]): Filter by resolved status.
        limit (int): Max number of events to return.

    Returns:
        List[AbuseEvent]: List of abuse event dicts, sorted by timestamp (most recent first).

    Side Effects:
        Reads from MongoDB.
    """
    try:
        collection = db_manager.get_collection(ABUSE_EVENTS_COLLECTION)
        query: Dict[str, Any] = {}
        if email:
            query["email"] = email
        if event_type:
            query["event_type"] = event_type
        if resolved is not None:
            query["resolved_by_admin"] = resolved
        cursor = collection.find(query).sort("timestamp", -1).limit(limit)
        events: List[AbuseEvent] = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            events.append(doc)
        logger.debug("Admin listed %d abuse events with query: %r", len(events), query)
        return events
    except pymongo.errors.PyMongoError:
        logger.error("Failed to list abuse events", exc_info=True)
        return []


async def admin_resolve_abuse_event(event_id: str, notes: Optional[str] = None) -> bool:
    """
    Mark an abuse event as resolved by admin, with optional notes.

    Args:
        event_id (str): The event's ObjectId as a string.
        notes (Optional[str]): Optional admin notes.

    Returns:
        bool: True if the event was updated, False if not found or error.

    Side Effects:
        Updates MongoDB.
    """
    try:

        collection = db_manager.get_collection(ABUSE_EVENTS_COLLECTION)
        result = await collection.update_one(
            {"_id": ObjectId(event_id)}, {"$set": {"resolved_by_admin": True, "notes": notes or ""}}
        )
        updated = result.modified_count > 0
        if updated:
            logger.info("Abuse event %s marked as resolved by admin.", event_id)
        else:
            logger.warning("Abuse event %s not found for resolution.", event_id)
        return updated
    except pymongo.errors.PyMongoError:
        logger.error("Failed to resolve abuse event", exc_info=True)
        return False
