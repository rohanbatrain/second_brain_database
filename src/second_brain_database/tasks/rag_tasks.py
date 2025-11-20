"""
Consolidated RAG Celery Tasks

Strategic Celery integration for RAG operations where background processing
provides architectural benefits. Consolidates RAG tasks into the main Celery app
to avoid redundancy and maintain consistency with existing task infrastructure.

Celery is used ONLY for:
- Long-running document processing and indexing operations
- Bulk/batch operations that can benefit from queuing
- Background cache warming and maintenance tasks
- Scheduled analytics and reporting tasks
- Operations that need retry logic and failure recovery

Celery is NOT used for:
- Real-time query responses (handled by FastAPI directly)  
- Simple CRUD operations
- User session management
- Authentication/authorization flows
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from celery.schedules import crontab

from ..managers.logging_manager import get_logger
from .celery_app import celery_app

logger = get_logger(prefix="[RAGTasks]")


# 1. DOCUMENT PROCESSING TASKS (Perfect for Celery - Long-running, can fail, needs retry)

@celery_app.task(
    name="rag_process_document",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=False
)
def process_document_for_rag(
    self,
    document_id: str,
    user_id: str,
    processing_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a document for RAG indexing with comprehensive error handling.
    
    This is ideal for Celery because:
    - Long-running operation (can take 30+ seconds for large docs)
    - May fail due to external dependencies (Qdrant, MongoDB)
    - Benefits from retry logic with exponential backoff
    - Allows user to continue using app while processing
    - Can handle bulk operations efficiently
    
    Args:
        document_id: Document ID to process
        user_id: User ID for isolation
        processing_options: Optional processing configuration
        
    Returns:
        Processing result with status and metrics
    """
    try:
        start_time = datetime.now(timezone.utc)
        
        # Import RAG components (lazy loading to avoid circular imports)
        from ..rag import RAGSystem
        
        async def _process():
            # Initialize RAG system
            rag = RAGSystem()
            
            # Get document from database
            from ..database import db_manager
            await db_manager.connect()
            
            doc_collection = db_manager.get_collection("documents")
            document = await doc_collection.find_one({"_id": document_id, "user_id": user_id})
            
            if not document:
                raise ValueError(f"Document {document_id} not found for user {user_id}")
            
            # Process and index document
            result = await rag.document_service.process_document(
                file_path=document.get("file_path"),
                filename=document.get("filename", "unknown.txt"),
                user_id=user_id,
                **(processing_options or {})
            )
            
            # Update document status in database
            await doc_collection.update_one(
                {"_id": document_id},
                {
                    "$set": {
                        "rag_indexed": True,
                        "rag_indexed_at": datetime.now(timezone.utc),
                        "rag_chunks": result.get("chunk_count", 0),
                        "processing_time": (datetime.now(timezone.utc) - start_time).total_seconds()
                    }
                }
            )
            
            return result
        
        # Execute async processing
        result = asyncio.run(_process())
        
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        logger.info(
            f"RAG document processing completed for {document_id}",
            extra={
                "document_id": document_id,
                "user_id": user_id,
                "processing_time": processing_time,
                "chunks_created": result.get("chunk_count", 0)
            }
        )
        
        return {
            "document_id": document_id,
            "user_id": user_id,
            "status": "success",
            "processing_time": processing_time,
            "chunks_created": result.get("chunk_count", 0),
            "indexed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(
            f"RAG document processing failed for {document_id}: {e}",
            extra={"document_id": document_id, "user_id": user_id, "error": str(e)},
            exc_info=True
        )
        
        # Update task state for progress tracking
        self.update_state(
            state="FAILURE",
            meta={
                "document_id": document_id,
                "error": str(e),
                "retry_count": self.request.retries
            }
        )
        
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task(
    name="rag_batch_process_documents",
    bind=True,
    max_retries=2
)
def batch_process_documents_for_rag(
    self,
    document_ids: List[str],
    user_id: str,
    processing_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process multiple documents for RAG in batch.
    
    Perfect for Celery because:
    - Can process large batches without blocking UI
    - Provides progress updates via task state
    - Handles partial failures gracefully
    - Can be scheduled for off-peak processing
    
    Args:
        document_ids: List of document IDs to process
        user_id: User ID for isolation
        processing_options: Processing configuration
        
    Returns:
        Batch processing results with success/failure counts
    """
    try:
        total_docs = len(document_ids)
        successful = 0
        failed = 0
        results = []
        
        logger.info(
            f"Starting batch RAG processing for {total_docs} documents",
            extra={"user_id": user_id, "total_docs": total_docs}
        )
        
        for i, doc_id in enumerate(document_ids):
            try:
                # Update progress
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": i + 1,
                        "total": total_docs,
                        "successful": successful,
                        "failed": failed,
                        "processing_document": doc_id
                    }
                )
                
                # Process individual document
                result = process_document_for_rag.apply(
                    args=[doc_id, user_id, processing_options]
                )
                
                doc_result = result.get()
                results.append({
                    "document_id": doc_id,
                    "status": "success",
                    "result": doc_result
                })
                successful += 1
                
            except Exception as e:
                logger.warning(
                    f"Failed to process document {doc_id} in batch: {e}",
                    extra={"document_id": doc_id, "user_id": user_id}
                )
                results.append({
                    "document_id": doc_id,
                    "status": "failed",
                    "error": str(e)
                })
                failed += 1
        
        batch_result = {
            "total_documents": total_docs,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total_docs if total_docs > 0 else 0,
            "results": results,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(
            f"Batch RAG processing completed: {successful}/{total_docs} successful",
            extra={
                "user_id": user_id,
                "total_docs": total_docs,
                "successful": successful,
                "failed": failed
            }
        )
        
        return batch_result
        
    except Exception as e:
        logger.error(
            f"Batch RAG processing failed: {e}",
            extra={"user_id": user_id, "document_count": len(document_ids)},
            exc_info=True
        )
        raise


# 2. CACHE WARMING TASKS (Ideal for Celery - Background optimization, scheduled)

@celery_app.task(
    name="rag_warm_cache",
    bind=True,
    max_retries=2
)
def warm_rag_cache(
    self,
    user_id: Optional[str] = None,
    query_patterns: Optional[List[str]] = None,
    cache_levels: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Warm RAG caches with frequently accessed queries.
    
    Ideal for Celery because:
    - Background optimization task
    - Can be scheduled during low-traffic periods
    - Long-running operation that shouldn't block user interactions
    - Can handle failures gracefully without affecting user experience
    
    Args:
        user_id: Optional user ID for user-specific cache warming
        query_patterns: Specific query patterns to warm
        cache_levels: Cache levels to warm
        
    Returns:
        Cache warming results
    """
    try:
        from ..rag import RAGSystem
        from ..rag.advanced.result_caching import get_monitoring_system
        
        async def _warm_cache():
            # Get default query patterns if not provided
            if not query_patterns:
                default_patterns = [
                    "What is this document about?",
                    "Summarize the main points",
                    "What are the key findings?",
                    "Explain the methodology",
                    "What are the conclusions?"
                ]
            else:
                default_patterns = query_patterns
            
            # Initialize RAG system
            rag = RAGSystem()
            monitoring = get_monitoring_system()
            
            # Warm cache with query patterns
            warmed_count = await monitoring.alerts.warm_cache(
                queries=default_patterns,
                vector_store_service=rag.vector_store_service,
                llm_service=rag.llm_service,
                user_id=user_id
            )
            
            return {
                "warmed_queries": warmed_count,
                "query_patterns": default_patterns,
                "user_id": user_id,
                "cache_levels": cache_levels or ["query_result", "synthesis_result"]
            }
        
        result = asyncio.run(_warm_cache())
        
        logger.info(
            f"RAG cache warming completed: {result['warmed_queries']} queries warmed",
            extra={
                "user_id": user_id,
                "warmed_count": result["warmed_queries"]
            }
        )
        
        return result
        
    except Exception as e:
        logger.error(f"RAG cache warming failed: {e}", exc_info=True)
        raise


# 3. ANALYTICS AND MAINTENANCE TASKS (Perfect for scheduled background work)

@celery_app.task(name="rag_generate_analytics")
def generate_rag_analytics(
    user_id: Optional[str] = None,
    time_period_hours: int = 24
) -> Dict[str, Any]:
    """
    Generate RAG usage analytics.
    
    Perfect for scheduled Celery tasks because:
    - Computation-intensive analytics processing
    - Can be run during off-peak hours
    - Results can be cached for dashboard display
    - Doesn't need to be real-time
    
    Args:
        user_id: Optional user ID for user-specific analytics
        time_period_hours: Time period for analytics
        
    Returns:
        Analytics results
    """
    try:
        async def _generate_analytics():
            from ..rag.monitoring import get_monitoring_system
            
            monitoring = get_monitoring_system()
            
            # Get comprehensive analytics
            dashboard_data = await monitoring.get_dashboard_data()
            
            # Get performance profiles for all components
            components = ["query_orchestrator", "vector_store", "llm_service", "document_processor"]
            performance_profiles = {}
            
            for component in components:
                profile = await monitoring.performance.get_performance_profile(component, time_period_hours / 24)
                performance_profiles[component] = {
                    "avg_response_time": profile.avg_response_time_ms,
                    "p95_response_time": profile.p95_response_time_ms,
                    "throughput": profile.throughput_per_second,
                    "error_rate": profile.error_rate,
                    "success_rate": profile.success_rate
                }
            
            # Generate usage statistics
            cache_stats = await monitoring.alerts.get_cache_stats()
            
            analytics = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "time_period_hours": time_period_hours,
                "user_id": user_id,
                "system_health": dashboard_data.get("health", {}),
                "performance_profiles": performance_profiles,
                "cache_performance": {
                    "hit_rate": cache_stats.hit_rate,
                    "total_entries": cache_stats.total_entries,
                    "size_mb": cache_stats.total_size_bytes / (1024 * 1024)
                },
                "alerts": dashboard_data.get("alerts", {}),
                "system_resources": dashboard_data.get("system_resources", {})
            }
            
            return analytics
        
        result = asyncio.run(_generate_analytics())
        
        logger.info(
            f"RAG analytics generated for {time_period_hours}h period",
            extra={"user_id": user_id, "time_period": time_period_hours}
        )
        
        return result
        
    except Exception as e:
        logger.error(f"RAG analytics generation failed: {e}", exc_info=True)
        return {"error": str(e)}


@celery_app.task(name="rag_cleanup_expired_data")
def cleanup_expired_rag_data(
    max_age_days: int = 30,
    cleanup_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Clean up expired RAG data and optimize storage.
    
    Perfect for scheduled maintenance because:
    - Can run during low-traffic periods
    - Long-running cleanup operations
    - Can handle large datasets efficiently
    - Doesn't affect user operations
    
    Args:
        max_age_days: Maximum age for data retention
        cleanup_types: Types of data to clean up
        
    Returns:
        Cleanup results
    """
    try:
        async def _cleanup():
            from ..database import db_manager
            from ..rag.advanced.result_caching import get_monitoring_system
            
            cleanup_results = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "max_age_days": max_age_days,
                "cleanup_types": cleanup_types or ["cache", "logs", "analytics"],
                "cleaned_items": {}
            }
            
            # Connect to database
            await db_manager.connect()
            
            # Clean up cache entries
            if not cleanup_types or "cache" in cleanup_types:
                monitoring = get_monitoring_system()
                cleared_count = await monitoring.alerts.clear_cache()
                cleanup_results["cleaned_items"]["cache_entries"] = cleared_count
            
            # Clean up old analytics data
            if not cleanup_types or "analytics" in cleanup_types:
                analytics_collection = db_manager.get_collection("rag_analytics")
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
                
                result = await analytics_collection.delete_many({
                    "generated_at": {"$lt": cutoff_date}
                })
                cleanup_results["cleaned_items"]["analytics_records"] = result.deleted_count
            
            # Clean up old conversation histories
            if not cleanup_types or "conversations" in cleanup_types:
                conversations_collection = db_manager.get_collection("rag_conversations")
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
                
                result = await conversations_collection.delete_many({
                    "created_at": {"$lt": cutoff_date}
                })
                cleanup_results["cleaned_items"]["conversation_records"] = result.deleted_count
            
            cleanup_results["completed_at"] = datetime.now(timezone.utc).isoformat()
            cleanup_results["total_cleaned"] = sum(cleanup_results["cleaned_items"].values())
            
            return cleanup_results
        
        result = asyncio.run(_cleanup())
        
        logger.info(
            f"RAG cleanup completed: {result['total_cleaned']} items cleaned",
            extra={"max_age_days": max_age_days, "total_cleaned": result["total_cleaned"]}
        )
        
        return result
        
    except Exception as e:
        logger.error(f"RAG cleanup failed: {e}", exc_info=True)
        return {"error": str(e)}


# 4. CONVERSATION MEMORY OPTIMIZATION (Background processing)

@celery_app.task(name="rag_optimize_conversation_memory")
def optimize_conversation_memory(
    user_id: Optional[str] = None,
    optimization_strategy: str = "adaptive"
) -> Dict[str, Any]:
    """
    Optimize conversation memory storage and performance.
    
    Good for Celery because:
    - Memory optimization can be CPU intensive
    - Can run in background without affecting active conversations
    - Can be scheduled during low-usage periods
    - Results improve future conversation performance
    
    Args:
        user_id: Optional user ID for user-specific optimization
        optimization_strategy: Strategy to use for optimization
        
    Returns:
        Optimization results
    """
    try:
        async def _optimize():
            from ..rag.advanced.conversation_memory import ConversationMemoryManager
            
            memory_manager = ConversationMemoryManager()
            
            # Get all conversations for optimization
            conversations = await memory_manager.get_user_conversations(user_id) if user_id else await memory_manager.get_all_conversations()
            
            optimized_count = 0
            total_memory_saved = 0
            
            for conversation_id in conversations:
                try:
                    # Get conversation context and optimize
                    context = await memory_manager.get_conversation_context(conversation_id, strategy=optimization_strategy)
                    
                    # Apply memory optimization
                    optimization_result = await memory_manager.optimize_conversation_memory(
                        conversation_id, 
                        strategy=optimization_strategy
                    )
                    
                    if optimization_result.get("optimized"):
                        optimized_count += 1
                        total_memory_saved += optimization_result.get("memory_saved", 0)
                        
                except Exception as e:
                    logger.warning(f"Failed to optimize conversation {conversation_id}: {e}")
                    continue
            
            return {
                "optimized_conversations": optimized_count,
                "total_conversations": len(conversations),
                "memory_saved_mb": total_memory_saved / (1024 * 1024),
                "optimization_strategy": optimization_strategy,
                "user_id": user_id
            }
        
        result = asyncio.run(_optimize())
        
        logger.info(
            f"Conversation memory optimization completed: {result['optimized_conversations']} conversations optimized",
            extra={
                "optimized_count": result["optimized_conversations"],
                "memory_saved_mb": result["memory_saved_mb"],
                "user_id": user_id
            }
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Conversation memory optimization failed: {e}", exc_info=True)
        return {"error": str(e)}


# Update Celery beat schedule for RAG tasks
celery_app.conf.beat_schedule.update({
    # Cache warming - every 2 hours during business hours
    'warm-rag-cache': {
        'task': 'rag_warm_cache',
        'schedule': crontab(minute=0, hour='9-17/2'),  # Every 2 hours from 9 AM to 5 PM
    },
    
    # Analytics generation - daily at 2 AM
    'generate-rag-analytics': {
        'task': 'rag_generate_analytics',
        'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
    },
    
    # Cleanup - weekly on Sunday at 3 AM
    'cleanup-rag-data': {
        'task': 'rag_cleanup_expired_data',
        'schedule': crontab(minute=0, hour=3, day_of_week=0),  # Sundays at 3 AM
    },
    
    # Memory optimization - daily at 4 AM
    'optimize-conversation-memory': {
        'task': 'rag_optimize_conversation_memory',
        'schedule': crontab(minute=0, hour=4),  # Daily at 4 AM
    },
})


# Helper functions for task management

def get_rag_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a RAG task."""
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id, app=celery_app)
    
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "info": result.info,
        "successful": result.successful(),
        "failed": result.failed()
    }


def cancel_rag_task(task_id: str) -> bool:
    """Cancel a running RAG task."""
    try:
        celery_app.control.revoke(task_id, terminate=True)
        return True
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        return False


# Export key functions for use in FastAPI routes
__all__ = [
    'process_document_for_rag',
    'batch_process_documents_for_rag', 
    'warm_rag_cache',
    'generate_rag_analytics',
    'cleanup_expired_rag_data',
    'optimize_conversation_memory',
    'get_rag_task_status',
    'cancel_rag_task'
]