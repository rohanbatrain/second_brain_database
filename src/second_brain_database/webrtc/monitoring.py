"""
WebRTC Health Checks & Monitoring

Comprehensive health checks, metrics, and observability for WebRTC service.
Provides detailed system statistics and component health monitoring.

Note: Global Prometheus metrics are handled by the main FastAPI app at /metrics
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[WebRTC-Health]")


class ServiceStatus(str):
    """Service status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status of a system component."""
    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Health status")
    latency_ms: Optional[float] = Field(None, description="Response latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class HealthCheckResponse(BaseModel):
    """Overall health check response."""
    status: str = Field(..., description="Overall service status")
    timestamp: str = Field(..., description="Check timestamp (ISO 8601)")
    version: str = Field("1.0.0", description="Service version")
    uptime_seconds: Optional[float] = Field(None, description="Service uptime")
    
    components: List[ComponentHealth] = Field(default_factory=list, description="Component health status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-11-10T12:00:00Z",
                "version": "1.0.0",
                "uptime_seconds": 3600.5,
                "components": [
                    {
                        "name": "redis",
                        "status": "healthy",
                        "latency_ms": 2.5
                    },
                    {
                        "name": "mongodb",
                        "status": "healthy",
                        "latency_ms": 15.3
                    }
                ]
            }
        }


class WebRtcMetrics(BaseModel):
    """Real-time WebRTC metrics."""
    
    # Connection metrics
    active_websocket_connections: int = Field(0, description="Active WebSocket connections")
    total_connections_today: int = Field(0, description="Total connections since midnight")
    
    # Room metrics
    active_rooms: int = Field(0, description="Active rooms")
    total_rooms_created_today: int = Field(0, description="Rooms created since midnight")
    
    # Participant metrics
    total_participants: int = Field(0, description="Total participants across all rooms")
    average_participants_per_room: float = Field(0.0, description="Average participants per room")
    
    # Message metrics
    messages_per_second: float = Field(0.0, description="Messages per second (last minute)")
    total_messages_today: int = Field(0, description="Total messages since midnight")
    
    # Error metrics
    errors_per_minute: float = Field(0.0, description="Errors per minute")
    error_rate_percentage: float = Field(0.0, description="Error rate percentage")
    
    # Performance metrics
    average_message_latency_ms: float = Field(0.0, description="Average message latency")
    p95_message_latency_ms: float = Field(0.0, description="95th percentile message latency")
    p99_message_latency_ms: float = Field(0.0, description="99th percentile message latency")
    
    # Resource metrics
    redis_memory_used_mb: Optional[float] = Field(None, description="Redis memory usage (MB)")
    redis_connection_pool_size: Optional[int] = Field(None, description="Redis connection pool size")
    redis_connection_pool_available: Optional[int] = Field(None, description="Available Redis connections")
    
    class Config:
        json_schema_extra = {
            "example": {
                "active_websocket_connections": 150,
                "active_rooms": 25,
                "total_participants": 280,
                "average_participants_per_room": 11.2,
                "messages_per_second": 45.3,
                "error_rate_percentage": 0.02
            }
        }


class WebRtcStats(BaseModel):
    """Detailed WebRTC statistics."""
    
    timestamp: str = Field(..., description="Stats timestamp (ISO 8601)")
    
    # Room breakdown
    rooms_by_size: Dict[str, int] = Field(
        default_factory=dict,
        description="Room count by size (1-5, 6-10, 11-25, 26-50, 51+)"
    )
    
    # Feature usage
    features_used: Dict[str, int] = Field(
        default_factory=dict,
        description="Feature usage counts"
    )
    
    # Top rooms
    top_rooms: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top 10 rooms by participants"
    )
    
    # Rate limiting
    rate_limited_users: int = Field(0, description="Users currently rate limited")
    rate_limit_violations_today: int = Field(0, description="Rate limit violations today")
    
    # Recording
    active_recordings: int = Field(0, description="Active recordings")
    total_recordings_today: int = Field(0, description="Recordings started today")


class WebRtcMonitoring:
    """
    Monitoring and observability for WebRTC service.
    
    Provides:
    - Health checks for all dependencies
    - Real-time metrics collection
    - Detailed statistics
    
    Note: Prometheus metrics are auto-collected by the main FastAPI instrumentator
    """
    
    def __init__(self):
        """Initialize monitoring manager."""
        self.redis = redis_manager
        self.mongodb = db_manager
        self.start_time = time.time()
        
        # Metrics keys
        self.METRICS_PREFIX = "webrtc:metrics:"
        self.STATS_PREFIX = "webrtc:stats:"
        
        logger.info("WebRTC monitoring initialized")
    
    async def check_health(self) -> HealthCheckResponse:
        """
        Perform comprehensive health check.
        
        Returns:
            HealthCheckResponse with status of all components
        """
        components = []
        
        # Check Redis
        redis_health = await self._check_redis_health()
        components.append(redis_health)
        
        # Check MongoDB
        mongodb_health = await self._check_mongodb_health()
        components.append(mongodb_health)
        
        # Determine overall status
        statuses = [c.status for c in components]
        if all(s == ServiceStatus.HEALTHY for s in statuses):
            overall_status = ServiceStatus.HEALTHY
        elif any(s == ServiceStatus.UNHEALTHY for s in statuses):
            overall_status = ServiceStatus.UNHEALTHY
        else:
            overall_status = ServiceStatus.DEGRADED
        
        uptime = time.time() - self.start_time
        
        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            uptime_seconds=uptime,
            components=components
        )
    
    async def _check_redis_health(self) -> ComponentHealth:
        """Check Redis health."""
        start_time = time.time()
        
        try:
            redis_client = await self.redis.get_redis()
            
            # Perform ping
            await redis_client.ping()
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Get additional info
            info = await redis_client.info("memory")
            memory_used_mb = info.get("used_memory", 0) / (1024 * 1024)
            
            return ComponentHealth(
                name="redis",
                status=ServiceStatus.HEALTHY,
                latency_ms=round(latency_ms, 2),
                details={
                    "memory_used_mb": round(memory_used_mb, 2)
                }
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Redis health check failed: {e}")
            
            return ComponentHealth(
                name="redis",
                status=ServiceStatus.UNHEALTHY,
                latency_ms=round(latency_ms, 2),
                error=str(e)
            )
    
    async def _check_mongodb_health(self) -> ComponentHealth:
        """Check MongoDB health."""
        start_time = time.time()
        
        try:
            db = await self.mongodb.get_database()
            
            # Perform ping
            await db.command("ping")
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Get server status
            server_status = await db.command("serverStatus")
            connections = server_status.get("connections", {})
            
            return ComponentHealth(
                name="mongodb",
                status=ServiceStatus.HEALTHY,
                latency_ms=round(latency_ms, 2),
                details={
                    "connections": connections.get("current", 0),
                    "available_connections": connections.get("available", 0)
                }
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"MongoDB health check failed: {e}")
            
            return ComponentHealth(
                name="mongodb",
                status=ServiceStatus.UNHEALTHY,
                latency_ms=round(latency_ms, 2),
                error=str(e)
            )
    
    async def get_metrics(self) -> WebRtcMetrics:
        """
        Get current WebRTC metrics.
        
        Returns:
            WebRtcMetrics with current statistics
        """
        try:
            redis_client = await self.redis.get_redis()
            
            # Count active rooms
            room_keys = await redis_client.keys("webrtc:participants:*")
            active_rooms = len(room_keys)
            
            # Count total participants
            total_participants = 0
            for key in room_keys:
                count = await redis_client.scard(key)
                total_participants += count
            
            # Calculate average participants per room
            avg_participants = total_participants / active_rooms if active_rooms > 0 else 0.0
            
            # Get Redis memory info
            info = await redis_client.info("memory")
            redis_memory_mb = info.get("used_memory", 0) / (1024 * 1024)
            
            # TODO: Implement connection tracking, message rate, error tracking
            # These would require additional Redis structures to track metrics
            
            return WebRtcMetrics(
                active_rooms=active_rooms,
                total_participants=total_participants,
                average_participants_per_room=round(avg_participants, 2),
                redis_memory_used_mb=round(redis_memory_mb, 2)
            )
            
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return WebRtcMetrics()
    
    async def get_stats(self) -> WebRtcStats:
        """
        Get detailed WebRTC statistics.
        
        Returns:
            WebRtcStats with comprehensive statistics
        """
        try:
            redis_client = await self.redis.get_redis()
            
            # Get room size breakdown
            room_keys = await redis_client.keys("webrtc:participants:*")
            rooms_by_size = {
                "1-5": 0,
                "6-10": 0,
                "11-25": 0,
                "26-50": 0,
                "51+": 0
            }
            
            top_rooms = []
            
            for key in room_keys:
                count = await redis_client.scard(key)
                room_id = key.decode() if isinstance(key, bytes) else key
                room_id = room_id.replace("webrtc:participants:", "")
                
                # Categorize by size
                if count <= 5:
                    rooms_by_size["1-5"] += 1
                elif count <= 10:
                    rooms_by_size["6-10"] += 1
                elif count <= 25:
                    rooms_by_size["11-25"] += 1
                elif count <= 50:
                    rooms_by_size["26-50"] += 1
                else:
                    rooms_by_size["51+"] += 1
                
                # Add to top rooms list
                top_rooms.append({
                    "room_id": room_id,
                    "participant_count": count
                })
            
            # Sort and limit to top 10
            top_rooms.sort(key=lambda x: x["participant_count"], reverse=True)
            top_rooms = top_rooms[:10]
            
            # Count active recordings
            recording_keys = await redis_client.keys("webrtc:recordings:*")
            active_recordings = 0
            for key in recording_keys:
                status = await redis_client.hget(key, "status")
                if status == b"active" or status == "active":
                    active_recordings += 1
            
            return WebRtcStats(
                timestamp=datetime.now(timezone.utc).isoformat(),
                rooms_by_size=rooms_by_size,
                top_rooms=top_rooms,
                active_recordings=active_recordings
            )
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return WebRtcStats(
                timestamp=datetime.now(timezone.utc).isoformat()
            )


# Global monitoring instance
webrtc_monitoring = WebRtcMonitoring()
