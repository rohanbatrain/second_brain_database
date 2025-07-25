"""
Permanent token usage tracking and analytics service.

This module provides comprehensive usage analytics for permanent tokens including:
- Last-used timestamp tracking
- Usage statistics and patterns
- Token lifecycle analytics
- Cleanup recommendations for unused tokens
- Usage trends and insights
"""

import asyncio
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.permanent_tokens.audit_logger import AUDIT_COLLECTION
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Permanent Token Analytics]")
security_logger = SecurityLogger(prefix="[PERM-TOKEN-ANALYTICS-SECURITY]")
db_logger = DatabaseLogger(prefix="[PERM-TOKEN-ANALYTICS-DB]")

# Analytics configuration
USAGE_ANALYTICS_COLLECTION = "permanent_token_usage_analytics"
INACTIVE_TOKEN_THRESHOLD_DAYS = 30  # Consider tokens inactive after 30 days
CLEANUP_RECOMMENDATION_THRESHOLD_DAYS = 90  # Recommend cleanup after 90 days
USAGE_PATTERN_ANALYSIS_DAYS = 30  # Analyze usage patterns over 30 days


@dataclass
class TokenUsageStats:
    """Statistics for a single token's usage."""

    token_id: str
    user_id: str
    username: str
    description: Optional[str]
    created_at: datetime
    last_used_at: Optional[datetime]
    total_uses: int
    unique_ips: int
    unique_user_agents: int
    days_since_creation: int
    days_since_last_use: Optional[int]
    usage_frequency: float  # uses per day
    is_active: bool
    is_stale: bool
    risk_score: float  # 0-1, higher means more suspicious


@dataclass
class UsageAnalytics:
    """Comprehensive usage analytics for permanent tokens."""

    timestamp: datetime
    total_tokens: int
    active_tokens: int
    inactive_tokens: int
    stale_tokens: int
    total_usage_events: int
    unique_users: int
    unique_ips: int
    avg_uses_per_token: float
    most_used_tokens: List[Dict[str, Any]]
    least_used_tokens: List[Dict[str, Any]]
    cleanup_recommendations: List[Dict[str, Any]]
    security_insights: List[Dict[str, Any]]
    usage_trends: Dict[str, Any]


class PermanentTokenAnalytics:
    """
    Analytics service for permanent token usage tracking and insights.
    """

    def __init__(self):
        self.last_analytics_update = None
        self.cached_analytics = None
        self.cache_ttl_minutes = 15  # Cache analytics for 15 minutes

    @log_performance("update_token_usage")
    async def update_token_usage(
        self, token_hash: str, user_id: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None
    ) -> bool:
        """
        Update usage statistics for a token.

        Args:
            token_hash: SHA-256 hash of the token
            user_id: User ID who used the token
            ip_address: IP address of the request
            user_agent: User agent of the request

        Returns:
            bool: True if update was successful
        """
        logger.info("Updating token usage analytics for user: %s from IP: %s", user_id, ip_address or "unknown")

        try:
            now = datetime.utcnow()

            # Update last_used_at in permanent_tokens collection
            tokens_collection = db_manager.get_collection("permanent_tokens")
            token_update_result = await tokens_collection.update_one(
                {"token_hash": token_hash, "is_revoked": False}, {"$set": {"last_used_at": now}}
            )

            log_database_operation(
                operation="update_token_last_used",
                collection="permanent_tokens",
                query={"token_hash": token_hash[:8] + "...", "is_revoked": False},
                result={"modified_count": token_update_result.modified_count, "timestamp": now.isoformat()},
            )

            # Update usage analytics
            analytics_collection = db_manager.get_collection(USAGE_ANALYTICS_COLLECTION)

            # Create or update usage record
            usage_record = {
                "token_hash": token_hash,
                "user_id": user_id,
                "timestamp": now,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "date": now.strftime("%Y-%m-%d"),  # For daily aggregation
            }

            analytics_result = await analytics_collection.insert_one(usage_record)

            log_database_operation(
                operation="insert_token_usage_analytics",
                collection=USAGE_ANALYTICS_COLLECTION,
                query={},
                result={
                    "inserted_id": str(analytics_result.inserted_id),
                    "user_id": user_id,
                    "ip_address": ip_address,
                    "date": usage_record["date"],
                },
            )

            # Log security event for token usage tracking
            log_security_event(
                event_type="permanent_token_usage_tracked",
                user_id=user_id,
                ip_address=ip_address,
                success=True,
                details={
                    "token_hash_prefix": token_hash[:8],
                    "user_agent": user_agent,
                    "analytics_recorded": bool(analytics_result.inserted_id),
                    "last_used_updated": token_update_result.modified_count > 0,
                },
            )

            logger.info(
                "Successfully updated usage statistics for token: %s, user: %s", token_hash[:8] + "...", user_id
            )
            return True

        except Exception as e:
            logger.error("Error updating token usage analytics for user %s: %s", user_id, e, exc_info=True)
            log_error_with_context(
                e,
                context={
                    "token_hash_prefix": token_hash[:8] if token_hash else None,
                    "user_id": user_id,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                },
                operation="update_token_usage",
            )
            return False

    @log_performance("get_token_usage_stats")
    async def get_token_usage_stats(self, token_id: str) -> Optional[TokenUsageStats]:
        """
        Get detailed usage statistics for a specific token.

        Args:
            token_id: Unique token identifier

        Returns:
            TokenUsageStats: Detailed usage statistics
        """
        logger.debug("Retrieving usage statistics for token: %s", token_id)

        try:
            # Get token metadata
            tokens_collection = db_manager.get_collection("permanent_tokens")
            token_doc = await tokens_collection.find_one({"token_id": token_id})

            log_database_operation(
                operation="get_token_metadata",
                collection="permanent_tokens",
                query={"token_id": token_id},
                result={"found": token_doc is not None},
            )

            if not token_doc:
                logger.warning("Token not found for usage stats: %s", token_id)
                return None

            # Get user information
            users_collection = db_manager.get_collection("users")
            user_doc = await users_collection.find_one({"_id": token_doc["user_id"]})

            log_database_operation(
                operation="get_token_user",
                collection="users",
                query={"_id": token_doc["user_id"]},
                result={"found": user_doc is not None},
            )

            if not user_doc:
                logger.warning("User not found for token: %s", token_id)
                return None

            # Get usage statistics from audit logs
            audit_collection = db_manager.get_collection(AUDIT_COLLECTION)

            # Count total uses
            total_uses = await audit_collection.count_documents({"token_id": token_id, "event_type": "token_validated"})

            # Get unique IPs and user agents
            pipeline = [
                {"$match": {"token_id": token_id, "event_type": "token_validated"}},
                {
                    "$group": {
                        "_id": None,
                        "unique_ips": {"$addToSet": "$ip_address"},
                        "unique_user_agents": {"$addToSet": "$user_agent"},
                    }
                },
            ]

            cursor = audit_collection.aggregate(pipeline)
            usage_data = await cursor.to_list(length=1)

            log_database_operation(
                operation="get_token_usage_aggregation",
                collection=AUDIT_COLLECTION,
                query={"token_id": token_id, "event_type": "token_validated"},
                result={"total_uses": total_uses, "aggregation_results": len(usage_data)},
            )

            unique_ips = len(usage_data[0]["unique_ips"]) if usage_data else 0
            unique_user_agents = len(usage_data[0]["unique_user_agents"]) if usage_data else 0

            # Calculate time-based metrics
            now = datetime.utcnow()
            created_at = token_doc["created_at"]
            last_used_at = token_doc.get("last_used_at")

            days_since_creation = (now - created_at).days
            days_since_last_use = (now - last_used_at).days if last_used_at else None

            # Calculate usage frequency
            usage_frequency = total_uses / max(days_since_creation, 1)

            # Determine activity status
            is_active = (
                last_used_at is not None
                and days_since_last_use is not None
                and days_since_last_use <= INACTIVE_TOKEN_THRESHOLD_DAYS
            )

            is_stale = last_used_at is None or (
                days_since_last_use is not None and days_since_last_use > CLEANUP_RECOMMENDATION_THRESHOLD_DAYS
            )

            # Calculate risk score (0-1, higher is more suspicious)
            risk_score = self._calculate_risk_score(unique_ips, unique_user_agents, total_uses, days_since_creation)

            stats = TokenUsageStats(
                token_id=token_id,
                user_id=token_doc["user_id"],
                username=user_doc["username"],
                description=token_doc.get("description"),
                created_at=created_at,
                last_used_at=last_used_at,
                total_uses=total_uses,
                unique_ips=unique_ips,
                unique_user_agents=unique_user_agents,
                days_since_creation=days_since_creation,
                days_since_last_use=days_since_last_use,
                usage_frequency=round(usage_frequency, 2),
                is_active=is_active,
                is_stale=is_stale,
                risk_score=round(risk_score, 2),
            )

            logger.info(
                "Retrieved usage stats for token %s: %d uses, %d unique IPs, risk score %.2f",
                token_id,
                total_uses,
                unique_ips,
                risk_score,
            )

            # Log security event for high-risk tokens
            if risk_score > 0.7:
                log_security_event(
                    event_type="high_risk_token_detected",
                    user_id=user_doc["username"],
                    success=True,
                    details={
                        "token_id": token_id,
                        "risk_score": risk_score,
                        "unique_ips": unique_ips,
                        "unique_user_agents": unique_user_agents,
                        "total_uses": total_uses,
                        "days_since_creation": days_since_creation,
                    },
                )

            return stats

        except Exception as e:
            logger.error("Error getting token usage stats for %s: %s", token_id, e, exc_info=True)
            log_error_with_context(e, context={"token_id": token_id}, operation="get_token_usage_stats")
            return None

    @log_performance("get_user_usage_analytics")
    async def get_user_usage_analytics(self, user_id: str) -> Dict[str, Any]:
        """
        Get usage analytics for all tokens belonging to a user.

        Args:
            user_id: User ID to analyze

        Returns:
            Dict containing user's token usage analytics
        """
        logger.info("Generating usage analytics for user: %s", user_id)

        try:
            # Get all user's tokens
            tokens_collection = db_manager.get_collection("permanent_tokens")
            user_tokens = await tokens_collection.find({"user_id": user_id, "is_revoked": False}).to_list(length=None)

            log_database_operation(
                operation="get_user_tokens",
                collection="permanent_tokens",
                query={"user_id": user_id, "is_revoked": False},
                result={"token_count": len(user_tokens)},
            )

            if not user_tokens:
                logger.info("No active tokens found for user: %s", user_id)
                return {
                    "user_id": user_id,
                    "total_tokens": 0,
                    "active_tokens": 0,
                    "inactive_tokens": 0,
                    "stale_tokens": 0,
                    "total_uses": 0,
                    "tokens": [],
                    "recommendations": [],
                }

            # Get detailed stats for each token
            token_stats = []
            total_uses = 0
            active_count = 0
            inactive_count = 0
            stale_count = 0

            for token_doc in user_tokens:
                stats = await self.get_token_usage_stats(token_doc["token_id"])
                if stats:
                    token_stats.append(asdict(stats))
                    total_uses += stats.total_uses

                    if stats.is_active:
                        active_count += 1
                    else:
                        inactive_count += 1

                    if stats.is_stale:
                        stale_count += 1

            # Generate recommendations
            recommendations = self._generate_user_recommendations(token_stats)

            analytics_result = {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "total_tokens": len(user_tokens),
                "active_tokens": active_count,
                "inactive_tokens": inactive_count,
                "stale_tokens": stale_count,
                "total_uses": total_uses,
                "avg_uses_per_token": round(total_uses / len(user_tokens), 2) if user_tokens else 0,
                "tokens": token_stats,
                "recommendations": recommendations,
            }

            logger.info(
                "Generated user analytics for %s: %d tokens, %d total uses, %d recommendations",
                user_id,
                len(user_tokens),
                total_uses,
                len(recommendations),
            )

            # Log security events for concerning patterns
            if stale_count > 0:
                log_security_event(
                    event_type="user_stale_tokens_detected",
                    user_id=user_id,
                    success=True,
                    details={
                        "stale_token_count": stale_count,
                        "total_tokens": len(user_tokens),
                        "stale_percentage": round((stale_count / len(user_tokens)) * 100, 2),
                    },
                )

            high_risk_tokens = [token for token in token_stats if token["risk_score"] > 0.7]
            if high_risk_tokens:
                log_security_event(
                    event_type="user_high_risk_tokens_detected",
                    user_id=user_id,
                    success=True,
                    details={
                        "high_risk_count": len(high_risk_tokens),
                        "total_tokens": len(user_tokens),
                        "risk_percentage": round((len(high_risk_tokens) / len(user_tokens)) * 100, 2),
                        "token_ids": [token["token_id"] for token in high_risk_tokens],
                    },
                )

            return analytics_result

        except Exception as e:
            logger.error("Error getting user usage analytics for %s: %s", user_id, e, exc_info=True)
            log_error_with_context(e, context={"user_id": user_id}, operation="get_user_usage_analytics")
            return {"error": str(e), "user_id": user_id}

    async def get_system_usage_analytics(self) -> UsageAnalytics:
        """
        Get comprehensive system-wide usage analytics.

        Returns:
            UsageAnalytics: System-wide analytics and insights
        """
        try:
            # Check cache first
            if (
                self.cached_analytics
                and self.last_analytics_update
                and datetime.utcnow() - self.last_analytics_update < timedelta(minutes=self.cache_ttl_minutes)
            ):
                return self.cached_analytics

            now = datetime.utcnow()

            # Get all active tokens
            tokens_collection = db_manager.get_collection("permanent_tokens")
            all_tokens = await tokens_collection.find({"is_revoked": False}).to_list(length=None)

            if not all_tokens:
                return UsageAnalytics(
                    timestamp=now,
                    total_tokens=0,
                    active_tokens=0,
                    inactive_tokens=0,
                    stale_tokens=0,
                    total_usage_events=0,
                    unique_users=0,
                    unique_ips=0,
                    avg_uses_per_token=0.0,
                    most_used_tokens=[],
                    least_used_tokens=[],
                    cleanup_recommendations=[],
                    security_insights=[],
                    usage_trends={},
                )

            # Analyze each token
            token_stats = []
            for token_doc in all_tokens:
                stats = await self.get_token_usage_stats(token_doc["token_id"])
                if stats:
                    token_stats.append(stats)

            # Calculate system metrics
            total_tokens = len(token_stats)
            active_tokens = sum(1 for stats in token_stats if stats.is_active)
            inactive_tokens = total_tokens - active_tokens
            stale_tokens = sum(1 for stats in token_stats if stats.is_stale)
            total_usage_events = sum(stats.total_uses for stats in token_stats)
            unique_users = len(set(stats.user_id for stats in token_stats))

            # Get unique IPs from audit logs
            audit_collection = db_manager.get_collection(AUDIT_COLLECTION)
            unique_ips_cursor = audit_collection.distinct(
                "ip_address", {"event_type": "token_validated", "ip_address": {"$ne": None}}
            )
            unique_ips = len(await unique_ips_cursor.to_list(length=None))

            avg_uses_per_token = total_usage_events / total_tokens if total_tokens > 0 else 0.0

            # Get most and least used tokens
            sorted_tokens = sorted(token_stats, key=lambda x: x.total_uses, reverse=True)
            most_used_tokens = [asdict(token) for token in sorted_tokens[:10]]
            least_used_tokens = [asdict(token) for token in sorted_tokens[-10:]]

            # Generate cleanup recommendations
            cleanup_recommendations = self._generate_cleanup_recommendations(token_stats)

            # Generate security insights
            security_insights = self._generate_security_insights(token_stats)

            # Generate usage trends
            usage_trends = await self._generate_usage_trends()

            analytics = UsageAnalytics(
                timestamp=now,
                total_tokens=total_tokens,
                active_tokens=active_tokens,
                inactive_tokens=inactive_tokens,
                stale_tokens=stale_tokens,
                total_usage_events=total_usage_events,
                unique_users=unique_users,
                unique_ips=unique_ips,
                avg_uses_per_token=round(avg_uses_per_token, 2),
                most_used_tokens=most_used_tokens,
                least_used_tokens=least_used_tokens,
                cleanup_recommendations=cleanup_recommendations,
                security_insights=security_insights,
                usage_trends=usage_trends,
            )

            # Cache the results
            self.cached_analytics = analytics
            self.last_analytics_update = now

            return analytics

        except Exception as e:
            logger.error("Error generating system usage analytics: %s", e)
            return UsageAnalytics(
                timestamp=datetime.utcnow(),
                total_tokens=0,
                active_tokens=0,
                inactive_tokens=0,
                stale_tokens=0,
                total_usage_events=0,
                unique_users=0,
                unique_ips=0,
                avg_uses_per_token=0.0,
                most_used_tokens=[],
                least_used_tokens=[],
                cleanup_recommendations=[],
                security_insights=[],
                usage_trends={},
            )

    def _calculate_risk_score(
        self, unique_ips: int, unique_user_agents: int, total_uses: int, days_since_creation: int
    ) -> float:
        """Calculate risk score for a token based on usage patterns."""
        risk_score = 0.0

        # High number of unique IPs increases risk
        if unique_ips > 10:
            risk_score += 0.3
        elif unique_ips > 5:
            risk_score += 0.2
        elif unique_ips > 2:
            risk_score += 0.1

        # High number of unique user agents increases risk
        if unique_user_agents > 5:
            risk_score += 0.2
        elif unique_user_agents > 3:
            risk_score += 0.1

        # Very high usage frequency can be suspicious
        if days_since_creation > 0:
            usage_per_day = total_uses / days_since_creation
            if usage_per_day > 100:  # More than 100 uses per day
                risk_score += 0.3
            elif usage_per_day > 50:
                risk_score += 0.2

        # Newly created tokens with high usage
        if days_since_creation < 7 and total_uses > 100:
            risk_score += 0.2

        return min(risk_score, 1.0)  # Cap at 1.0

    def _generate_user_recommendations(self, token_stats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate cleanup and security recommendations for a user."""
        recommendations = []

        # Find stale tokens
        stale_tokens = [token for token in token_stats if token["is_stale"]]
        if stale_tokens:
            recommendations.append(
                {
                    "type": "cleanup",
                    "priority": "medium",
                    "title": "Remove unused tokens",
                    "description": f"You have {len(stale_tokens)} tokens that haven't been used in over {CLEANUP_RECOMMENDATION_THRESHOLD_DAYS} days",
                    "action": "Consider revoking these tokens if they're no longer needed",
                    "token_ids": [token["token_id"] for token in stale_tokens],
                }
            )

        # Find high-risk tokens
        high_risk_tokens = [token for token in token_stats if token["risk_score"] > 0.7]
        if high_risk_tokens:
            recommendations.append(
                {
                    "type": "security",
                    "priority": "high",
                    "title": "Review high-risk tokens",
                    "description": f"You have {len(high_risk_tokens)} tokens with suspicious usage patterns",
                    "action": "Review these tokens for unusual activity and consider rotating them",
                    "token_ids": [token["token_id"] for token in high_risk_tokens],
                }
            )

        # Check for tokens with many unique IPs
        multi_ip_tokens = [token for token in token_stats if token["unique_ips"] > 5]
        if multi_ip_tokens:
            recommendations.append(
                {
                    "type": "security",
                    "priority": "medium",
                    "title": "Tokens used from multiple locations",
                    "description": f"You have {len(multi_ip_tokens)} tokens being used from many different IP addresses",
                    "action": "Verify that this usage pattern is expected for your use case",
                    "token_ids": [token["token_id"] for token in multi_ip_tokens],
                }
            )

        return recommendations

    def _generate_cleanup_recommendations(self, token_stats: List[TokenUsageStats]) -> List[Dict[str, Any]]:
        """Generate system-wide cleanup recommendations."""
        recommendations = []

        # Count stale tokens
        stale_tokens = [token for token in token_stats if token.is_stale]
        if stale_tokens:
            recommendations.append(
                {
                    "type": "cleanup",
                    "priority": "medium",
                    "title": "System cleanup needed",
                    "description": f"{len(stale_tokens)} tokens haven't been used in over {CLEANUP_RECOMMENDATION_THRESHOLD_DAYS} days",
                    "action": "Consider implementing automated cleanup for unused tokens",
                    "affected_tokens": len(stale_tokens),
                    "potential_savings": f"Could free up {len(stale_tokens)} database records and cache entries",
                }
            )

        # Count never-used tokens
        never_used = [token for token in token_stats if token.total_uses == 0]
        if never_used:
            recommendations.append(
                {
                    "type": "cleanup",
                    "priority": "low",
                    "title": "Unused tokens detected",
                    "description": f"{len(never_used)} tokens have never been used",
                    "action": "Consider notifying users about unused tokens or implementing expiration policies",
                    "affected_tokens": len(never_used),
                }
            )

        return recommendations

    def _generate_security_insights(self, token_stats: List[TokenUsageStats]) -> List[Dict[str, Any]]:
        """Generate security insights from usage patterns."""
        insights = []

        # High-risk tokens
        high_risk_tokens = [token for token in token_stats if token.risk_score > 0.7]
        if high_risk_tokens:
            insights.append(
                {
                    "type": "security_alert",
                    "severity": "high",
                    "title": "High-risk tokens detected",
                    "description": f"{len(high_risk_tokens)} tokens show suspicious usage patterns",
                    "details": "These tokens are used from many different IPs or show unusual usage frequency",
                    "recommendation": "Review these tokens and consider implementing additional monitoring",
                }
            )

        # Tokens with many unique IPs
        multi_ip_tokens = [token for token in token_stats if token.unique_ips > 10]
        if multi_ip_tokens:
            insights.append(
                {
                    "type": "security_warning",
                    "severity": "medium",
                    "title": "Tokens used from many locations",
                    "description": f"{len(multi_ip_tokens)} tokens are used from more than 10 different IP addresses",
                    "details": "This could indicate token sharing or compromise",
                    "recommendation": "Implement IP-based restrictions or additional authentication",
                }
            )

        # Very active tokens
        very_active_tokens = [token for token in token_stats if token.usage_frequency > 50]
        if very_active_tokens:
            insights.append(
                {
                    "type": "performance_insight",
                    "severity": "info",
                    "title": "High-frequency token usage",
                    "description": f"{len(very_active_tokens)} tokens are used more than 50 times per day on average",
                    "details": "These tokens might benefit from enhanced caching or rate limiting",
                    "recommendation": "Consider optimizing cache strategies for frequently used tokens",
                }
            )

        return insights

    async def _generate_usage_trends(self) -> Dict[str, Any]:
        """Generate usage trend analysis."""
        try:
            # Get usage data for the last 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)

            audit_collection = db_manager.get_collection(AUDIT_COLLECTION)

            # Daily usage counts
            pipeline = [
                {"$match": {"event_type": "token_validated", "timestamp": {"$gte": cutoff_date}}},
                {
                    "$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                        "count": {"$sum": 1},
                        "unique_tokens": {"$addToSet": "$token_id"},
                        "unique_users": {"$addToSet": "$user_id"},
                    }
                },
                {"$sort": {"_id": 1}},
            ]

            cursor = audit_collection.aggregate(pipeline)
            daily_stats = await cursor.to_list(length=None)

            # Process trends
            trends = {
                "daily_usage": [
                    {
                        "date": stat["_id"],
                        "total_uses": stat["count"],
                        "unique_tokens": len(stat["unique_tokens"]),
                        "unique_users": len(stat["unique_users"]),
                    }
                    for stat in daily_stats
                ],
                "total_days_analyzed": len(daily_stats),
                "avg_daily_usage": sum(stat["count"] for stat in daily_stats) / len(daily_stats) if daily_stats else 0,
            }

            return trends

        except Exception as e:
            logger.error("Error generating usage trends: %s", e)
            return {"error": str(e)}


# Global analytics instance
token_analytics = PermanentTokenAnalytics()


# Convenience functions
async def track_token_usage(token_hash: str, user_id: str, ip_address: str = None, user_agent: str = None):
    """Track token usage for analytics."""
    return await token_analytics.update_token_usage(token_hash, user_id, ip_address, user_agent)


async def get_token_stats(token_id: str) -> Optional[TokenUsageStats]:
    """Get usage statistics for a specific token."""
    return await token_analytics.get_token_usage_stats(token_id)


async def get_user_analytics(user_id: str) -> Dict[str, Any]:
    """Get usage analytics for a user's tokens."""
    return await token_analytics.get_user_usage_analytics(user_id)


async def get_system_analytics() -> UsageAnalytics:
    """Get system-wide usage analytics."""
    return await token_analytics.get_system_usage_analytics()
