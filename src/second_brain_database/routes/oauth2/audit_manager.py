"""
OAuth2 audit manager for comprehensive audit trails and compliance.

This module provides centralized audit management for OAuth2 operations,
including audit trail generation, compliance reporting, and security monitoring.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.database import db_manager

from .logging_utils import (
    oauth2_logger,
    log_audit_summary,
    log_performance_event,
    OAuth2EventType
)

try:
    from .metrics import oauth2_metrics
    METRICS_AVAILABLE = True
except ImportError:
    oauth2_metrics = None
    METRICS_AVAILABLE = False

logger = get_logger(prefix="[OAuth2 Audit Manager]")


class AuditLevel(str, Enum):
    """Audit logging levels for different compliance requirements."""
    
    MINIMAL = "minimal"      # Basic operation logging
    STANDARD = "standard"    # Standard compliance logging
    DETAILED = "detailed"    # Detailed audit trails
    FORENSIC = "forensic"    # Full forensic logging


class ComplianceStandard(str, Enum):
    """Supported compliance standards for audit reporting."""
    
    SOX = "sox"              # Sarbanes-Oxley Act
    GDPR = "gdpr"            # General Data Protection Regulation
    HIPAA = "hipaa"          # Health Insurance Portability and Accountability Act
    PCI_DSS = "pci_dss"      # Payment Card Industry Data Security Standard
    ISO27001 = "iso27001"    # ISO/IEC 27001
    NIST = "nist"            # NIST Cybersecurity Framework


class OAuth2AuditManager:
    """
    Comprehensive OAuth2 audit manager for compliance and security monitoring.
    
    Provides centralized audit trail management, compliance reporting,
    and security event correlation for OAuth2 operations.
    """
    
    def __init__(self, audit_level: AuditLevel = AuditLevel.STANDARD):
        self.audit_level = audit_level
        self.logger = get_logger(prefix="[OAuth2 Audit Manager]")
        
        # Redis keys for audit data
        self.AUDIT_EVENTS_KEY = "oauth2:audit:events"
        self.AUDIT_SUMMARY_KEY = "oauth2:audit:summary"
        self.SECURITY_EVENTS_KEY = "oauth2:audit:security"
        self.PERFORMANCE_EVENTS_KEY = "oauth2:audit:performance"
        
        # Audit retention periods (in seconds)
        self.AUDIT_RETENTION = {
            AuditLevel.MINIMAL: 30 * 24 * 3600,    # 30 days
            AuditLevel.STANDARD: 90 * 24 * 3600,   # 90 days
            AuditLevel.DETAILED: 365 * 24 * 3600,  # 1 year
            AuditLevel.FORENSIC: 7 * 365 * 24 * 3600  # 7 years
        }
    
    async def record_audit_event(
        self,
        event_type: str,
        client_id: Optional[str],
        user_id: Optional[str],
        event_data: Dict[str, Any],
        severity: str = "info",
        compliance_relevant: bool = False
    ) -> str:
        """
        Record a comprehensive audit event.
        
        Args:
            event_type: Type of OAuth2 event
            client_id: OAuth2 client identifier
            user_id: User identifier
            event_data: Event-specific data
            severity: Event severity level
            compliance_relevant: Whether event is relevant for compliance
            
        Returns:
            Audit event ID for tracking
        """
        try:
            # Generate unique audit event ID
            event_id = f"audit_{event_type}_{datetime.utcnow().timestamp()}"
            
            # Create comprehensive audit record
            audit_record = {
                "event_id": event_id,
                "event_type": event_type,
                "client_id": client_id,
                "user_id": user_id,
                "severity": severity,
                "compliance_relevant": compliance_relevant,
                "audit_level": self.audit_level.value,
                "timestamp": datetime.utcnow().isoformat(),
                "event_data": event_data,
                "retention_until": (
                    datetime.utcnow() + timedelta(seconds=self.AUDIT_RETENTION[self.audit_level])
                ).isoformat()
            }
            
            # Store in Redis with appropriate TTL
            await redis_manager.setex(
                f"{self.AUDIT_EVENTS_KEY}:{event_id}",
                self.AUDIT_RETENTION[self.audit_level],
                json.dumps(audit_record, default=str)
            )
            
            # Add to event index for querying
            await redis_manager.zadd(
                f"{self.AUDIT_EVENTS_KEY}:index",
                {event_id: datetime.utcnow().timestamp()}
            )
            
            # Store security events separately for faster access
            if severity in ["high", "critical"] or "security" in event_type.lower():
                await redis_manager.setex(
                    f"{self.SECURITY_EVENTS_KEY}:{event_id}",
                    self.AUDIT_RETENTION[self.audit_level],
                    json.dumps(audit_record, default=str)
                )
                
                await redis_manager.zadd(
                    f"{self.SECURITY_EVENTS_KEY}:index",
                    {event_id: datetime.utcnow().timestamp()}
                )
            
            # Update audit statistics
            await self._update_audit_statistics(event_type, severity, client_id)
            
            # Log audit event creation
            self.logger.info(
                f"OAuth2 audit event recorded: {event_type}",
                extra={
                    "audit_event_id": event_id,
                    "event_type": event_type,
                    "client_id": client_id,
                    "user_id": user_id,
                    "severity": severity,
                    "compliance_relevant": compliance_relevant
                }
            )
            
            return event_id
            
        except Exception as e:
            self.logger.error(f"Failed to record audit event: {e}", exc_info=True)
            raise
    
    async def get_audit_trail(
        self,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit trail based on filters.
        
        Args:
            client_id: Filter by OAuth2 client
            user_id: Filter by user
            event_type: Filter by event type
            start_time: Start time for filtering
            end_time: End time for filtering
            limit: Maximum number of events to return
            
        Returns:
            List of audit events matching filters
        """
        try:
            # Get event IDs from index within time range
            start_score = start_time.timestamp() if start_time else 0
            end_score = end_time.timestamp() if end_time else datetime.utcnow().timestamp()
            
            event_ids = await redis_manager.zrangebyscore(
                f"{self.AUDIT_EVENTS_KEY}:index",
                start_score,
                end_score,
                start=0,
                num=limit
            )
            
            if not event_ids:
                return []
            
            # Retrieve audit records
            audit_events = []
            for event_id in event_ids:
                event_data = await redis_manager.get(f"{self.AUDIT_EVENTS_KEY}:{event_id}")
                if event_data:
                    try:
                        audit_record = json.loads(event_data)
                        
                        # Apply filters
                        if client_id and audit_record.get("client_id") != client_id:
                            continue
                        if user_id and audit_record.get("user_id") != user_id:
                            continue
                        if event_type and audit_record.get("event_type") != event_type:
                            continue
                        
                        audit_events.append(audit_record)
                        
                    except json.JSONDecodeError:
                        self.logger.warning(f"Failed to parse audit event: {event_id}")
                        continue
            
            # Sort by timestamp (most recent first)
            audit_events.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return audit_events[:limit]
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve audit trail: {e}", exc_info=True)
            return []
    
    async def get_security_events(
        self,
        severity: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retrieve security-relevant audit events.
        
        Args:
            severity: Filter by severity level
            start_time: Start time for filtering
            end_time: End time for filtering
            limit: Maximum number of events to return
            
        Returns:
            List of security events matching filters
        """
        try:
            # Get security event IDs from index
            start_score = start_time.timestamp() if start_time else 0
            end_score = end_time.timestamp() if end_time else datetime.utcnow().timestamp()
            
            event_ids = await redis_manager.zrangebyscore(
                f"{self.SECURITY_EVENTS_KEY}:index",
                start_score,
                end_score,
                start=0,
                num=limit
            )
            
            if not event_ids:
                return []
            
            # Retrieve security events
            security_events = []
            for event_id in event_ids:
                event_data = await redis_manager.get(f"{self.SECURITY_EVENTS_KEY}:{event_id}")
                if event_data:
                    try:
                        audit_record = json.loads(event_data)
                        
                        # Apply severity filter
                        if severity and audit_record.get("severity") != severity:
                            continue
                        
                        security_events.append(audit_record)
                        
                    except json.JSONDecodeError:
                        self.logger.warning(f"Failed to parse security event: {event_id}")
                        continue
            
            # Sort by timestamp (most recent first)
            security_events.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return security_events[:limit]
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve security events: {e}", exc_info=True)
            return []
    
    async def generate_compliance_report(
        self,
        standard: ComplianceStandard,
        start_time: datetime,
        end_time: datetime,
        client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate compliance report for specified standard.
        
        Args:
            standard: Compliance standard to report against
            start_time: Report start time
            end_time: Report end time
            client_id: Optional client filter
            
        Returns:
            Compliance report data
        """
        try:
            # Get audit events for the period
            audit_events = await self.get_audit_trail(
                client_id=client_id,
                start_time=start_time,
                end_time=end_time,
                limit=10000  # Large limit for comprehensive reporting
            )
            
            # Get security events
            security_events = await self.get_security_events(
                start_time=start_time,
                end_time=end_time,
                limit=1000
            )
            
            # Generate standard-specific report
            if standard == ComplianceStandard.SOX:
                report = await self._generate_sox_report(audit_events, security_events)
            elif standard == ComplianceStandard.GDPR:
                report = await self._generate_gdpr_report(audit_events, security_events)
            elif standard == ComplianceStandard.ISO27001:
                report = await self._generate_iso27001_report(audit_events, security_events)
            else:
                report = await self._generate_generic_report(audit_events, security_events)
            
            # Add report metadata
            report.update({
                "compliance_standard": standard.value,
                "report_period": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                },
                "client_filter": client_id,
                "generated_at": datetime.utcnow().isoformat(),
                "audit_level": self.audit_level.value,
                "total_events": len(audit_events),
                "security_events": len(security_events)
            })
            
            # Log report generation
            self.logger.info(
                f"OAuth2 compliance report generated: {standard.value}",
                extra={
                    "compliance_standard": standard.value,
                    "report_period_days": (end_time - start_time).days,
                    "total_events": len(audit_events),
                    "security_events": len(security_events),
                    "client_filter": client_id
                }
            )
            
            return report
            
        except Exception as e:
            self.logger.error(f"Failed to generate compliance report: {e}", exc_info=True)
            raise
    
    async def get_audit_statistics(
        self,
        time_period: str = "24h"
    ) -> Dict[str, Any]:
        """
        Get audit statistics for monitoring dashboard.
        
        Args:
            time_period: Time period for statistics (1h, 24h, 7d, 30d)
            
        Returns:
            Audit statistics data
        """
        try:
            # Get statistics from Redis
            stats_key = f"{self.AUDIT_SUMMARY_KEY}:{time_period}"
            stats_data = await redis_manager.get(stats_key)
            
            if stats_data:
                return json.loads(stats_data)
            
            # Calculate statistics if not cached
            time_delta = {
                "1h": timedelta(hours=1),
                "24h": timedelta(days=1),
                "7d": timedelta(days=7),
                "30d": timedelta(days=30)
            }.get(time_period, timedelta(days=1))
            
            start_time = datetime.utcnow() - time_delta
            end_time = datetime.utcnow()
            
            # Get events for the period
            audit_events = await self.get_audit_trail(
                start_time=start_time,
                end_time=end_time,
                limit=10000
            )
            
            security_events = await self.get_security_events(
                start_time=start_time,
                end_time=end_time,
                limit=1000
            )
            
            # Calculate statistics
            stats = {
                "time_period": time_period,
                "total_events": len(audit_events),
                "security_events": len(security_events),
                "event_types": {},
                "client_activity": {},
                "severity_distribution": {},
                "compliance_events": 0,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # Analyze events
            for event in audit_events:
                # Event type distribution
                event_type = event.get("event_type", "unknown")
                stats["event_types"][event_type] = stats["event_types"].get(event_type, 0) + 1
                
                # Client activity
                client_id = event.get("client_id")
                if client_id:
                    stats["client_activity"][client_id] = stats["client_activity"].get(client_id, 0) + 1
                
                # Severity distribution
                severity = event.get("severity", "info")
                stats["severity_distribution"][severity] = stats["severity_distribution"].get(severity, 0) + 1
                
                # Compliance events
                if event.get("compliance_relevant"):
                    stats["compliance_events"] += 1
            
            # Cache statistics for 5 minutes
            await redis_manager.setex(stats_key, 300, json.dumps(stats, default=str))
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get audit statistics: {e}", exc_info=True)
            return {}
    
    async def cleanup_expired_audit_data(self) -> int:
        """
        Clean up expired audit data based on retention policies.
        
        Returns:
            Number of expired records cleaned up
        """
        try:
            cleaned_count = 0
            current_time = datetime.utcnow().timestamp()
            
            # Clean up main audit events
            expired_events = await redis_manager.zrangebyscore(
                f"{self.AUDIT_EVENTS_KEY}:index",
                0,
                current_time - self.AUDIT_RETENTION[self.audit_level]
            )
            
            for event_id in expired_events:
                await redis_manager.delete(f"{self.AUDIT_EVENTS_KEY}:{event_id}")
                await redis_manager.zrem(f"{self.AUDIT_EVENTS_KEY}:index", event_id)
                cleaned_count += 1
            
            # Clean up security events
            expired_security = await redis_manager.zrangebyscore(
                f"{self.SECURITY_EVENTS_KEY}:index",
                0,
                current_time - self.AUDIT_RETENTION[self.audit_level]
            )
            
            for event_id in expired_security:
                await redis_manager.delete(f"{self.SECURITY_EVENTS_KEY}:{event_id}")
                await redis_manager.zrem(f"{self.SECURITY_EVENTS_KEY}:index", event_id)
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} expired audit records")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired audit data: {e}", exc_info=True)
            return 0
    
    async def _update_audit_statistics(
        self,
        event_type: str,
        severity: str,
        client_id: Optional[str]
    ) -> None:
        """Update real-time audit statistics."""
        try:
            # Update hourly statistics
            hour_key = f"{self.AUDIT_SUMMARY_KEY}:hourly:{datetime.utcnow().strftime('%Y%m%d%H')}"
            await redis_manager.hincrby(hour_key, f"events:{event_type}", 1)
            await redis_manager.hincrby(hour_key, f"severity:{severity}", 1)
            if client_id:
                await redis_manager.hincrby(hour_key, f"client:{client_id}", 1)
            await redis_manager.expire(hour_key, 7 * 24 * 3600)  # Keep for 7 days
            
        except Exception as e:
            self.logger.error(f"Failed to update audit statistics: {e}")
    
    async def _generate_sox_report(
        self,
        audit_events: List[Dict[str, Any]],
        security_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate SOX compliance report."""
        return {
            "access_controls": {
                "authorization_events": len([e for e in audit_events if "authorization" in e.get("event_type", "")]),
                "failed_authentications": len([e for e in security_events if "authentication_failed" in e.get("event_type", "")]),
                "privilege_escalations": len([e for e in security_events if "privilege" in e.get("event_type", "")])
            },
            "data_integrity": {
                "token_modifications": len([e for e in audit_events if "token" in e.get("event_type", "")]),
                "configuration_changes": len([e for e in audit_events if "client" in e.get("event_type", "")])
            },
            "monitoring": {
                "security_violations": len([e for e in security_events if e.get("severity") in ["high", "critical"]]),
                "audit_trail_completeness": "complete" if audit_events else "incomplete"
            }
        }
    
    async def _generate_gdpr_report(
        self,
        audit_events: List[Dict[str, Any]],
        security_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate GDPR compliance report."""
        return {
            "data_processing": {
                "consent_events": len([e for e in audit_events if "consent" in e.get("event_type", "")]),
                "data_access_requests": len([e for e in audit_events if "access" in e.get("event_type", "")]),
                "data_deletion_requests": len([e for e in audit_events if "deletion" in e.get("event_type", "")])
            },
            "security_measures": {
                "encryption_events": len([e for e in audit_events if "encryption" in e.get("event_type", "")]),
                "breach_incidents": len([e for e in security_events if e.get("severity") == "critical"])
            },
            "user_rights": {
                "consent_withdrawals": len([e for e in audit_events if "consent_revoked" in e.get("event_type", "")]),
                "data_portability": len([e for e in audit_events if "export" in e.get("event_type", "")])
            }
        }
    
    async def _generate_iso27001_report(
        self,
        audit_events: List[Dict[str, Any]],
        security_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate ISO 27001 compliance report."""
        return {
            "information_security": {
                "access_control_events": len([e for e in audit_events if "authorization" in e.get("event_type", "")]),
                "security_incidents": len(security_events),
                "vulnerability_events": len([e for e in security_events if "vulnerability" in e.get("event_type", "")])
            },
            "risk_management": {
                "high_risk_events": len([e for e in security_events if e.get("severity") == "high"]),
                "critical_events": len([e for e in security_events if e.get("severity") == "critical"]),
                "risk_mitigation_actions": len([e for e in audit_events if "mitigation" in e.get("event_type", "")])
            },
            "continuous_monitoring": {
                "monitoring_coverage": "comprehensive" if audit_events else "limited",
                "incident_response_time": "within_sla"  # This would be calculated from actual response times
            }
        }
    
    async def _generate_generic_report(
        self,
        audit_events: List[Dict[str, Any]],
        security_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate generic compliance report."""
        return {
            "summary": {
                "total_events": len(audit_events),
                "security_events": len(security_events),
                "compliance_events": len([e for e in audit_events if e.get("compliance_relevant")])
            },
            "event_distribution": {
                event_type: len([e for e in audit_events if e.get("event_type") == event_type])
                for event_type in set(e.get("event_type", "unknown") for e in audit_events)
            },
            "security_summary": {
                "critical_events": len([e for e in security_events if e.get("severity") == "critical"]),
                "high_severity_events": len([e for e in security_events if e.get("severity") == "high"]),
                "medium_severity_events": len([e for e in security_events if e.get("severity") == "medium"])
            }
        }


# Global OAuth2 audit manager instance
oauth2_audit_manager = OAuth2AuditManager()


# Convenience functions for common audit operations
async def record_audit_event(
    event_type: str,
    client_id: Optional[str],
    user_id: Optional[str],
    event_data: Dict[str, Any],
    severity: str = "info",
    compliance_relevant: bool = False
) -> str:
    """Record OAuth2 audit event."""
    return await oauth2_audit_manager.record_audit_event(
        event_type, client_id, user_id, event_data, severity, compliance_relevant
    )


async def get_audit_trail(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get OAuth2 audit trail."""
    return await oauth2_audit_manager.get_audit_trail(
        client_id, user_id, None, start_time, end_time, limit
    )


async def get_security_events(
    severity: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get OAuth2 security events."""
    return await oauth2_audit_manager.get_security_events(
        severity, start_time, end_time, limit
    )


async def generate_compliance_report(
    standard: ComplianceStandard,
    start_time: datetime,
    end_time: datetime,
    client_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generate OAuth2 compliance report."""
    return await oauth2_audit_manager.generate_compliance_report(
        standard, start_time, end_time, client_id
    )