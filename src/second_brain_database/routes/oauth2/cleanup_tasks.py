"""
OAuth2 cleanup tasks for state management and maintenance.

This module provides background tasks for cleaning up expired OAuth2 states
and maintaining the health of the OAuth2 state management system.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

from second_brain_database.managers.logging_manager import get_logger
from .state_manager import oauth2_state_manager

logger = get_logger(prefix="[OAuth2 CleanupTasks]")


class OAuth2CleanupTasks:
    """
    OAuth2 cleanup tasks for maintaining state management system health.
    
    Provides background tasks for:
    - Cleaning up expired OAuth2 states
    - Monitoring state storage health
    - Generating cleanup statistics
    """
    
    def __init__(self):
        """Initialize the OAuth2CleanupTasks."""
        self.cleanup_interval = 300  # 5 minutes
        self.is_running = False
        self._cleanup_task = None
        
        logger.info("OAuth2CleanupTasks initialized")
    
    async def start_cleanup_tasks(self) -> None:
        """
        Start the background cleanup tasks.
        
        This should be called when the application starts to begin
        automatic cleanup of expired OAuth2 states.
        """
        if self.is_running:
            logger.warning("OAuth2 cleanup tasks already running")
            return
        
        self.is_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("OAuth2 cleanup tasks started")
    
    async def stop_cleanup_tasks(self) -> None:
        """
        Stop the background cleanup tasks.
        
        This should be called when the application shuts down to
        gracefully stop the cleanup tasks.
        """
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("OAuth2 cleanup tasks stopped")
    
    async def _cleanup_loop(self) -> None:
        """
        Main cleanup loop that runs periodically.
        
        Performs cleanup operations at regular intervals while
        the cleanup tasks are running.
        """
        logger.info("OAuth2 cleanup loop started")
        
        while self.is_running:
            try:
                # Perform cleanup operations
                await self._perform_cleanup()
                
                # Wait for next cleanup interval
                await asyncio.sleep(self.cleanup_interval)
                
            except asyncio.CancelledError:
                logger.info("OAuth2 cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(
                    f"Error in OAuth2 cleanup loop: {e}",
                    exc_info=True,
                    extra={"event_type": "oauth2_cleanup_error"}
                )
                
                # Wait before retrying to avoid rapid error loops
                await asyncio.sleep(60)  # 1 minute
    
    async def _perform_cleanup(self) -> None:
        """
        Perform cleanup operations for OAuth2 state management.
        
        This includes cleaning up expired states and generating
        health statistics.
        """
        try:
            # Clean up expired states
            cleaned_count = await oauth2_state_manager.cleanup_expired_states()
            
            # Get state statistics
            stats = await oauth2_state_manager.get_state_statistics()
            
            # Log cleanup results
            if cleaned_count > 0 or stats.get("total_states", 0) > 0:
                logger.info(
                    "OAuth2 state cleanup completed",
                    extra={
                        "cleaned_states": cleaned_count,
                        "total_states": stats.get("total_states", 0),
                        "expiring_soon": stats.get("expiring_soon", 0),
                        "normal_ttl": stats.get("normal_ttl", 0),
                        "long_ttl": stats.get("long_ttl", 0),
                        "cleanup_timestamp": datetime.now(timezone.utc).isoformat(),
                        "event_type": "oauth2_cleanup_completed"
                    }
                )
            
        except Exception as e:
            logger.error(
                f"Error performing OAuth2 cleanup: {e}",
                exc_info=True,
                extra={"event_type": "oauth2_cleanup_error"}
            )
    
    async def manual_cleanup(self) -> Dict[str, Any]:
        """
        Perform manual cleanup of OAuth2 states.
        
        This can be called manually to trigger cleanup operations
        outside of the regular cleanup schedule.
        
        Returns:
            Dictionary with cleanup results and statistics
        """
        try:
            logger.info("Manual OAuth2 cleanup requested")
            
            # Get statistics before cleanup
            stats_before = await oauth2_state_manager.get_state_statistics()
            
            # Perform cleanup
            cleaned_count = await oauth2_state_manager.cleanup_expired_states()
            
            # Get statistics after cleanup
            stats_after = await oauth2_state_manager.get_state_statistics()
            
            cleanup_results = {
                "cleanup_timestamp": datetime.now(timezone.utc).isoformat(),
                "cleaned_states": cleaned_count,
                "stats_before": stats_before,
                "stats_after": stats_after,
                "states_removed": stats_before.get("total_states", 0) - stats_after.get("total_states", 0)
            }
            
            logger.info(
                "Manual OAuth2 cleanup completed",
                extra={
                    **cleanup_results,
                    "event_type": "oauth2_manual_cleanup_completed"
                }
            )
            
            return cleanup_results
            
        except Exception as e:
            logger.error(
                f"Error in manual OAuth2 cleanup: {e}",
                exc_info=True,
                extra={"event_type": "oauth2_manual_cleanup_error"}
            )
            raise
    
    async def get_cleanup_status(self) -> Dict[str, Any]:
        """
        Get the current status of OAuth2 cleanup tasks.
        
        Returns:
            Dictionary with cleanup task status and statistics
        """
        try:
            # Get current state statistics
            stats = await oauth2_state_manager.get_state_statistics()
            
            status = {
                "cleanup_running": self.is_running,
                "cleanup_interval_seconds": self.cleanup_interval,
                "current_timestamp": datetime.now(timezone.utc).isoformat(),
                "state_statistics": stats
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting cleanup status: {e}")
            return {
                "cleanup_running": self.is_running,
                "cleanup_interval_seconds": self.cleanup_interval,
                "current_timestamp": datetime.now(timezone.utc).isoformat(),
                "state_statistics": {"error": str(e)},
                "error": "Failed to get complete status"
            }


# Global instance
oauth2_cleanup_tasks = OAuth2CleanupTasks()