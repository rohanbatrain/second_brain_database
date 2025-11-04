from typing import Dict, Any
from datetime import datetime, timezone, timedelta

from .celery_app import celery_app
from ..managers.logging_manager import get_logger
from ..managers.redis_manager import redis_manager
from ..database import db_manager

logger = get_logger(prefix="[AITasks]")


@celery_app.task(name="process_ai_message_async", bind=True, max_retries=3)
def process_ai_message_async(
    self,
    user_context_dict: Dict[str, Any],
    session_id: str,
    message: str,
    agent_type: str = "personal"
) -> Dict[str, Any]:
    """Process AI message asynchronously.
    
    Note: AI processing is currently disabled.
    """
    logger.warning(f"AI message processing requested but LangChain is disabled: session {session_id}")
    return {
        "error": "AI system is currently disabled",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@celery_app.task(name="cleanup_expired_sessions")
def cleanup_expired_sessions():
    """Periodic task to cleanup expired AI sessions."""
    try:
        redis = redis_manager.get_redis_sync()
        
        # Find all AI session keys
        session_keys = redis.keys("ai_session_*")
        
        expired_count = 0
        for key in session_keys:
            # Check if key is expired (handled by Redis TTL)
            # Archive to MongoDB before expiration
            session_data = redis.get(key)
            if session_data:
                # Check if close to expiration
                ttl = redis.ttl(key)
                if ttl and ttl < 300:  # Less than 5 minutes remaining
                    # Archive to MongoDB
                    import json
                    data = json.loads(session_data)
                    
                    db_manager.get_collection("ai_sessions_archive").insert_one({
                        **data,
                        "archived_at": datetime.now(timezone.utc)
                    })
                    
                    expired_count += 1
        
        logger.info(f"Archived {expired_count} expiring AI sessions")
        
        return {"archived": expired_count}
        
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {e}", exc_info=True)
        return {"error": str(e)}


@celery_app.task(name="sync_langsmith_traces")
def sync_langsmith_traces():
    """Sync LangSmith traces to MongoDB for analytics."""
    logger.info("LangSmith trace sync requested but LangChain is disabled")
    return {"status": "disabled", "reason": "LangChain system is disabled"}


@celery_app.task(name="generate_ai_analytics")
def generate_ai_analytics(user_id: str, date_range: int = 7):
    """Generate AI usage analytics for a user.
    
    Args:
        user_id: User ID
        date_range: Days to analyze
        
    Returns:
        Analytics dict
    """
    try:
        collection = db_manager.get_collection("ai_conversations")
        
        start_date = datetime.now(timezone.utc) - timedelta(days=date_range)
        
        # Aggregate analytics
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "created_at": {"$gte": start_date}
                }
            },
            {
                "$group": {
                    "_id": "$agent_type",
                    "total_sessions": {"$sum": 1},
                    "total_messages": {"$sum": "$total_messages"},
                    "avg_messages_per_session": {"$avg": "$total_messages"}
                }
            }
        ]
        
        results = list(collection.aggregate(pipeline))
        
        analytics = {
            "user_id": user_id,
            "date_range_days": date_range,
            "by_agent_type": results,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Store analytics
        db_manager.get_collection("ai_analytics").insert_one(analytics)
        
        logger.info(f"Generated AI analytics for user {user_id}")
        
        return analytics
        
    except Exception as e:
        logger.error(f"Error generating analytics: {e}", exc_info=True)
        return {"error": str(e)}
