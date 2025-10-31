"""
AI Analytics Manager for user behavior tracking and performance monitoring.

This module provides comprehensive analytics for AI usage patterns, user behavior,
and system performance metrics. Integrates with existing MongoDB and Redis infrastructure.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import json

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.logging_utils import log_database_operation, log_performance
from second_brain_database.utils.ai_metrics import ai_performance_monitor


logger = get_logger(prefix="[AI_ANALYTICS]")


@dataclass
class AIUsageEvent:
    """AI usage event for analytics tracking."""
    
    event_id: str
    user_id: str
    session_id: str
    agent_type: str
    event_type: str  # session_start, message_sent, tool_executed, etc.
    timestamp: datetime
    duration_ms: Optional[int] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class AIPerformanceMetrics:
    """AI performance metrics for a specific time period."""
    
    period_start: datetime
    period_end: datetime
    total_sessions: int
    total_messages: int
    total_tokens: int
    average_response_time: float
    error_rate: float
    agent_usage: Dict[str, int]
    user_engagement: Dict[str, Any]
    tool_usage: Dict[str, int]


class AIAnalyticsManager:
    """
    Manager for AI analytics and user behavior tracking.
    
    Provides comprehensive analytics including:
    - User engagement metrics
    - Agent usage patterns
    - Performance monitoring
    - Error tracking and analysis
    - Usage trends and insights
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[AI_ANALYTICS_MANAGER]")
        self._analytics_collection = "ai_analytics"
        self._metrics_collection = "ai_metrics"
        self._cache_ttl = 300  # 5 minutes
        
    async def initialize(self):
        """Initialize analytics manager and create indexes."""
        try:
            # Create indexes for analytics collection
            await self._create_analytics_indexes()
            self.logger.info("AI analytics manager initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize AI analytics manager: %s", e)
            raise
    
    @log_database_operation("ai_analytics", "create_indexes")
    async def _create_analytics_indexes(self):
        """Create database indexes for analytics collections."""
        db = db_manager.get_database()
        
        # Analytics collection indexes
        analytics_indexes = [
            [("user_id", 1), ("timestamp", -1)],
            [("session_id", 1), ("timestamp", -1)],
            [("agent_type", 1), ("timestamp", -1)],
            [("event_type", 1), ("timestamp", -1)],
            [("timestamp", -1)],  # For time-based queries
            [("timestamp", 1), ("user_id", 1)],  # Compound for user analytics
        ]
        
        for index_spec in analytics_indexes:
            await db[self._analytics_collection].create_index(index_spec)
        
        # Metrics collection indexes
        metrics_indexes = [
            [("period_start", -1)],
            [("agent_type", 1), ("period_start", -1)],
        ]
        
        for index_spec in metrics_indexes:
            await db[self._metrics_collection].create_index(index_spec)
        
        # TTL index for analytics data (keep for 90 days)
        await db[self._analytics_collection].create_index(
            [("timestamp", 1)],
            expireAfterSeconds=90 * 24 * 60 * 60  # 90 days
        )
    
    @log_performance("record_usage_event")
    async def record_usage_event(
        self,
        user_id: str,
        session_id: str,
        agent_type: str,
        event_type: str,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a user usage event for analytics.
        
        Args:
            user_id: User identifier
            session_id: AI session identifier
            agent_type: Type of AI agent
            event_type: Type of event (session_start, message_sent, etc.)
            duration_ms: Event duration in milliseconds
            metadata: Additional event metadata
            
        Returns:
            Event ID
        """
        try:
            import uuid
            
            event = AIUsageEvent(
                event_id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                agent_type=agent_type,
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                metadata=metadata or {}
            )
            
            # Store in database
            db = db_manager.database
            await db[self._analytics_collection].insert_one(event.to_dict())
            
            # Update real-time metrics
            ai_performance_monitor.record_metric(f"user_event_{event_type}", 1, {
                "agent_type": agent_type,
                "user_id": user_id
            })
            
            # Cache recent events for quick access
            cache_key = f"ai_analytics:recent:{user_id}"
            try:
                recent_events = await redis_manager.get_json(cache_key) or []
                recent_events.append(event.to_dict())
                
                # Keep only last 50 events
                if len(recent_events) > 50:
                    recent_events = recent_events[-50:]
                
                await redis_manager.set_json(cache_key, recent_events, ttl=self._cache_ttl)
            except Exception as cache_error:
                self.logger.warning("Failed to cache analytics event: %s", cache_error)
            
            self.logger.debug("Recorded usage event: %s/%s/%s", user_id, agent_type, event_type)
            return event.event_id
            
        except Exception as e:
            self.logger.error("Failed to record usage event: %s", e)
            raise
    
    @log_performance("get_user_analytics")
    async def get_user_analytics(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get analytics data for a specific user.
        
        Args:
            user_id: User identifier
            start_date: Start date for analytics period
            end_date: End date for analytics period
            limit: Maximum number of events to return
            
        Returns:
            User analytics data
        """
        try:
            # Set default date range (last 30 days)
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # Check cache first
            cache_key = f"ai_analytics:user:{user_id}:{start_date.date()}:{end_date.date()}"
            cached_data = await redis_manager.get_json(cache_key)
            if cached_data:
                self.logger.debug("Retrieved user analytics from cache: %s", user_id)
                return cached_data
            
            # Query database
            db = db_manager.get_database()
            
            # Get events in date range
            events_cursor = db[self._analytics_collection].find({
                "user_id": user_id,
                "timestamp": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }).sort("timestamp", -1).limit(limit)
            
            events = await events_cursor.to_list(length=limit)
            
            # Calculate analytics
            analytics = self._calculate_user_analytics(events, start_date, end_date)
            
            # Cache results
            try:
                await redis_manager.set_json(cache_key, analytics, ttl=self._cache_ttl)
            except Exception as cache_error:
                self.logger.warning("Failed to cache user analytics: %s", cache_error)
            
            self.logger.debug("Retrieved user analytics: %s (%d events)", user_id, len(events))
            return analytics
            
        except Exception as e:
            self.logger.error("Failed to get user analytics for %s: %s", user_id, e)
            raise
    
    @log_performance("get_system_analytics")
    async def get_system_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get system-wide analytics data.
        
        Args:
            start_date: Start date for analytics period
            end_date: End date for analytics period
            
        Returns:
            System analytics data
        """
        try:
            # Set default date range (last 7 days)
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(days=7)
            
            # Check cache first
            cache_key = f"ai_analytics:system:{start_date.date()}:{end_date.date()}"
            cached_data = await redis_manager.get_json(cache_key)
            if cached_data:
                self.logger.debug("Retrieved system analytics from cache")
                return cached_data
            
            # Query database for aggregated data
            db = db_manager.get_database()
            
            # Aggregation pipeline for system metrics
            pipeline = [
                {
                    "$match": {
                        "timestamp": {
                            "$gte": start_date.isoformat(),
                            "$lte": end_date.isoformat()
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "agent_type": "$agent_type",
                            "event_type": "$event_type"
                        },
                        "count": {"$sum": 1},
                        "avg_duration": {"$avg": "$duration_ms"},
                        "users": {"$addToSet": "$user_id"}
                    }
                }
            ]
            
            aggregation_results = await db[self._analytics_collection].aggregate(pipeline).to_list(length=None)
            
            # Calculate system analytics
            analytics = self._calculate_system_analytics(aggregation_results, start_date, end_date)
            
            # Add real-time metrics
            analytics["real_time_metrics"] = ai_performance_monitor.get_performance_summary()
            
            # Cache results
            try:
                await redis_manager.set_json(cache_key, analytics, ttl=self._cache_ttl)
            except Exception as cache_error:
                self.logger.warning("Failed to cache system analytics: %s", cache_error)
            
            self.logger.debug("Retrieved system analytics for period %s to %s", start_date, end_date)
            return analytics
            
        except Exception as e:
            self.logger.error("Failed to get system analytics: %s", e)
            raise
    
    @log_performance("get_agent_performance")
    async def get_agent_performance(
        self,
        agent_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get performance metrics for AI agents.
        
        Args:
            agent_type: Specific agent type (optional)
            start_date: Start date for metrics period
            end_date: End date for metrics period
            
        Returns:
            Agent performance data
        """
        try:
            # Set default date range (last 24 hours)
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                start_date = end_date - timedelta(hours=24)
            
            # Get performance stats from metrics collector
            performance_summary = ai_performance_monitor.get_performance_summary()
            performance_stats = {}
            
            # Get historical data from database
            db = db_manager.get_database()
            
            match_filter = {
                "timestamp": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }
            
            if agent_type:
                match_filter["agent_type"] = agent_type
            
            # Aggregation for response times and error rates
            pipeline = [
                {"$match": match_filter},
                {
                    "$group": {
                        "_id": "$agent_type",
                        "total_events": {"$sum": 1},
                        "avg_duration": {"$avg": "$duration_ms"},
                        "sessions": {"$addToSet": "$session_id"},
                        "users": {"$addToSet": "$user_id"}
                    }
                }
            ]
            
            historical_data = await db[self._analytics_collection].aggregate(pipeline).to_list(length=None)
            
            # Combine real-time and historical data
            performance_data = {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "real_time_stats": performance_summary,
                "historical_data": {
                    item["_id"]: {
                        "total_events": item["total_events"],
                        "average_duration_ms": item["avg_duration"],
                        "unique_sessions": len(item["sessions"]),
                        "unique_users": len(item["users"])
                    }
                    for item in historical_data
                }
            }
            
            self.logger.debug("Retrieved agent performance data for %s", agent_type or "all agents")
            return performance_data
            
        except Exception as e:
            self.logger.error("Failed to get agent performance: %s", e)
            raise
    
    @log_performance("generate_usage_report")
    async def generate_usage_report(
        self,
        report_type: str = "daily",
        target_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive usage report.
        
        Args:
            report_type: Type of report (daily, weekly, monthly)
            target_date: Target date for report (defaults to today)
            
        Returns:
            Usage report data
        """
        try:
            if not target_date:
                target_date = datetime.now(timezone.utc)
            
            # Calculate date range based on report type
            if report_type == "daily":
                start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
            elif report_type == "weekly":
                days_since_monday = target_date.weekday()
                start_date = target_date - timedelta(days=days_since_monday)
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=7)
            elif report_type == "monthly":
                start_date = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if start_date.month == 12:
                    end_date = start_date.replace(year=start_date.year + 1, month=1)
                else:
                    end_date = start_date.replace(month=start_date.month + 1)
            else:
                raise ValueError(f"Invalid report type: {report_type}")
            
            # Get comprehensive analytics
            system_analytics = await self.get_system_analytics(start_date, end_date)
            agent_performance = await self.get_agent_performance(None, start_date, end_date)
            
            # Generate report
            report = {
                "report_type": report_type,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": system_analytics.get("summary", {}),
                "agent_performance": agent_performance,
                "usage_trends": system_analytics.get("trends", {}),
                "top_users": system_analytics.get("top_users", []),
                "error_analysis": system_analytics.get("errors", {}),
                "recommendations": self._generate_recommendations(system_analytics, agent_performance)
            }
            
            self.logger.info("Generated %s usage report for %s", report_type, target_date.date())
            return report
            
        except Exception as e:
            self.logger.error("Failed to generate usage report: %s", e)
            raise
    
    def _calculate_user_analytics(
        self,
        events: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate analytics from user events."""
        if not events:
            return {
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "total_events": 0,
                "sessions": 0,
                "messages": 0,
                "agent_usage": {},
                "activity_timeline": []
            }
        
        # Group events by type and agent
        event_counts = defaultdict(int)
        agent_usage = defaultdict(int)
        sessions = set()
        messages = 0
        
        for event in events:
            event_type = event.get("event_type", "unknown")
            agent_type = event.get("agent_type", "unknown")
            
            event_counts[event_type] += 1
            agent_usage[agent_type] += 1
            
            if event.get("session_id"):
                sessions.add(event["session_id"])
            
            if event_type in ["message_sent", "message_received"]:
                messages += 1
        
        return {
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_events": len(events),
            "sessions": len(sessions),
            "messages": messages,
            "event_breakdown": dict(event_counts),
            "agent_usage": dict(agent_usage),
            "activity_timeline": events[:20]  # Last 20 events
        }
    
    def _calculate_system_analytics(
        self,
        aggregation_results: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate system-wide analytics from aggregation results."""
        total_events = 0
        total_users = set()
        agent_stats = defaultdict(lambda: {"events": 0, "users": set(), "avg_duration": 0})
        event_stats = defaultdict(int)
        
        for result in aggregation_results:
            agent_type = result["_id"]["agent_type"]
            event_type = result["_id"]["event_type"]
            count = result["count"]
            users = set(result["users"])
            avg_duration = result.get("avg_duration", 0)
            
            total_events += count
            total_users.update(users)
            
            agent_stats[agent_type]["events"] += count
            agent_stats[agent_type]["users"].update(users)
            if avg_duration:
                agent_stats[agent_type]["avg_duration"] = avg_duration
            
            event_stats[event_type] += count
        
        return {
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "summary": {
                "total_events": total_events,
                "unique_users": len(total_users),
                "active_agents": len(agent_stats)
            },
            "agent_breakdown": {
                agent: {
                    "events": stats["events"],
                    "unique_users": len(stats["users"]),
                    "avg_duration_ms": stats["avg_duration"]
                }
                for agent, stats in agent_stats.items()
            },
            "event_breakdown": dict(event_stats)
        }
    
    def _generate_recommendations(
        self,
        system_analytics: Dict[str, Any],
        agent_performance: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on analytics data."""
        recommendations = []
        
        # Check performance metrics
        real_time_stats = agent_performance.get("real_time_stats", {})
        performance_metrics = real_time_stats.get("performance_metrics", {})
        
        # Check response times
        avg_response_time = performance_metrics.get("avg_response_time_ms", 0) / 1000.0  # Convert to seconds
        if avg_response_time > 5.0:  # 5 second threshold
            recommendations.append(
                f"Slow response times detected ({avg_response_time:.1f}s). "
                "Consider optimizing processing or scaling resources."
            )
        
        # Check compliance rates
        response_compliance = performance_metrics.get("response_time_compliance_pct", 100)
        if response_compliance < 90:  # 90% compliance threshold
            recommendations.append(
                f"Low response time compliance ({response_compliance:.1f}%). "
                "Consider investigating performance bottlenecks."
            )
        
        # Check usage patterns
        summary = system_analytics.get("summary", {})
        total_events = summary.get("total_events", 0)
        unique_users = summary.get("unique_users", 0)
        
        if unique_users > 0 and total_events / unique_users < 5:
            recommendations.append(
                "Low engagement per user detected. Consider improving user experience "
                "or providing better onboarding for AI features."
            )
        
        if not recommendations:
            recommendations.append("System performance is within normal parameters.")
        
        return recommendations


# Global analytics manager instance
ai_analytics_manager = AIAnalyticsManager()