"""
AI Security Configuration

This module provides configuration settings for AI security features,
integrating with existing security systems and adding AI-specific settings.
"""

from typing import Dict, List, Any
from datetime import timedelta

from ....config import settings


class AISecurityConfig:
    """Configuration for AI security features."""
    
    # Rate limiting configuration
    AI_RATE_LIMIT_REQUESTS = getattr(settings, "AI_RATE_LIMIT_REQUESTS", 100)
    AI_RATE_LIMIT_PERIOD_SECONDS = getattr(settings, "AI_RATE_LIMIT_PERIOD_SECONDS", 3600)
    AI_DAILY_QUOTA = getattr(settings, "AI_DAILY_QUOTA", 1000)
    AI_HOURLY_QUOTA = getattr(settings, "AI_HOURLY_QUOTA", 100)
    
    # Session security
    AI_SESSION_TIMEOUT = getattr(settings, "AI_SESSION_TIMEOUT", 3600)  # 1 hour
    AI_MAX_SESSIONS_PER_USER = getattr(settings, "AI_MAX_SESSIONS_PER_USER", 5)
    AI_SESSION_CLEANUP_INTERVAL = getattr(settings, "AI_SESSION_CLEANUP_INTERVAL", 300)  # 5 minutes
    
    # Conversation security
    AI_MAX_CONVERSATION_LENGTH = getattr(settings, "AI_MAX_CONVERSATION_LENGTH", 10000)
    AI_MAX_MESSAGE_LENGTH = getattr(settings, "AI_MAX_MESSAGE_LENGTH", 5000)
    AI_MAX_TOOL_CALLS_PER_SESSION = getattr(settings, "AI_MAX_TOOL_CALLS_PER_SESSION", 100)
    
    # Privacy settings
    AI_ENCRYPTION_KEY = getattr(settings, "AI_ENCRYPTION_KEY", None)
    AI_DEFAULT_PRIVACY_MODE = getattr(settings, "AI_DEFAULT_PRIVACY_MODE", "private")
    AI_CONVERSATION_RETENTION_DAYS = getattr(settings, "AI_CONVERSATION_RETENTION_DAYS", 30)
    
    # Threat detection
    AI_THREAT_DETECTION_ENABLED = getattr(settings, "AI_THREAT_DETECTION_ENABLED", True)
    AI_RAPID_REQUESTS_THRESHOLD = getattr(settings, "AI_RAPID_REQUESTS_THRESHOLD", 50)
    AI_RAPID_REQUESTS_WINDOW = getattr(settings, "AI_RAPID_REQUESTS_WINDOW", 60)
    
    # Suspicious patterns for threat detection
    AI_SUSPICIOUS_PATTERNS = getattr(settings, "AI_SUSPICIOUS_PATTERNS", [
        "injection",
        "exploit",
        "hack",
        "bypass",
        "admin",
        "root",
        "password",
        "token",
        "script",
        "eval",
        "exec",
        "system",
        "shell",
        "cmd"
    ])
    
    # Audit logging
    AI_AUDIT_LOG_RETENTION_DAYS = getattr(settings, "AI_AUDIT_LOG_RETENTION_DAYS", 90)
    AI_AUDIT_LOG_LEVEL = getattr(settings, "AI_AUDIT_LOG_LEVEL", "full")  # full, minimal, none
    
    # Permission defaults
    AI_DEFAULT_PERMISSIONS = {
        "user": [
            "ai:basic_chat",
            "ai:voice_interaction",
            "ai:conversation_history",
            "ai:knowledge_access"
        ],
        "family_admin": [
            "ai:basic_chat",
            "ai:voice_interaction",
            "ai:family_management",
            "ai:conversation_history",
            "ai:knowledge_access",
            "ai:tool_execution"
        ],
        "workspace_admin": [
            "ai:basic_chat",
            "ai:voice_interaction",
            "ai:workspace_collaboration",
            "ai:conversation_history",
            "ai:knowledge_access",
            "ai:tool_execution"
        ],
        "admin": [
            "ai:basic_chat",
            "ai:voice_interaction",
            "ai:family_management",
            "ai:workspace_collaboration",
            "ai:commerce_assistance",
            "ai:security_monitoring",
            "ai:admin_operations",
            "ai:conversation_history",
            "ai:knowledge_access",
            "ai:tool_execution"
        ]
    }
    
    # Privacy retention periods
    AI_RETENTION_PERIODS = {
        "1_day": 24 * 3600,
        "7_days": 7 * 24 * 3600,
        "30_days": 30 * 24 * 3600,
        "90_days": 90 * 24 * 3600,
        "1_year": 365 * 24 * 3600,
        "never": None
    }
    
    # Default privacy settings
    AI_DEFAULT_PRIVACY_SETTINGS = {
        "conversation_retention": "30_days",
        "data_sharing": False,
        "family_visibility": "admin_only",
        "encryption_enabled": True,
        "audit_logging": "full",
        "knowledge_indexing": True
    }
    
    # Security monitoring thresholds
    AI_MONITORING_THRESHOLDS = {
        "high_frequency_requests": {
            "threshold": 100,
            "window": 300,  # 5 minutes
            "action": "rate_limit"
        },
        "suspicious_content": {
            "threshold": 5,
            "window": 3600,  # 1 hour
            "action": "flag_for_review"
        },
        "failed_authentications": {
            "threshold": 10,
            "window": 600,  # 10 minutes
            "action": "temporary_block"
        },
        "excessive_tool_calls": {
            "threshold": 50,
            "window": 3600,  # 1 hour
            "action": "session_limit"
        }
    }
    
    # Integration with existing security systems
    AI_RESPECT_IP_LOCKDOWN = getattr(settings, "AI_RESPECT_IP_LOCKDOWN", True)
    AI_RESPECT_USER_AGENT_LOCKDOWN = getattr(settings, "AI_RESPECT_USER_AGENT_LOCKDOWN", True)
    AI_USE_EXISTING_RATE_LIMITS = getattr(settings, "AI_USE_EXISTING_RATE_LIMITS", True)
    AI_INTEGRATE_AUDIT_LOGGING = getattr(settings, "AI_INTEGRATE_AUDIT_LOGGING", True)
    
    @classmethod
    def get_permission_defaults(cls, user_role: str) -> List[str]:
        """Get default permissions for a user role."""
        return cls.AI_DEFAULT_PERMISSIONS.get(user_role, cls.AI_DEFAULT_PERMISSIONS["user"])
    
    @classmethod
    def get_retention_period_seconds(cls, retention_setting: str) -> int:
        """Get retention period in seconds."""
        return cls.AI_RETENTION_PERIODS.get(retention_setting, cls.AI_RETENTION_PERIODS["30_days"])
    
    @classmethod
    def is_threat_detection_enabled(cls) -> bool:
        """Check if threat detection is enabled."""
        return cls.AI_THREAT_DETECTION_ENABLED
    
    @classmethod
    def get_monitoring_threshold(cls, metric_name: str) -> Dict[str, Any]:
        """Get monitoring threshold configuration."""
        return cls.AI_MONITORING_THRESHOLDS.get(metric_name, {})
    
    @classmethod
    def should_respect_ip_lockdown(cls) -> bool:
        """Check if AI should respect existing IP lockdown."""
        return cls.AI_RESPECT_IP_LOCKDOWN
    
    @classmethod
    def should_respect_user_agent_lockdown(cls) -> bool:
        """Check if AI should respect existing user agent lockdown."""
        return cls.AI_RESPECT_USER_AGENT_LOCKDOWN
    
    @classmethod
    def should_use_existing_rate_limits(cls) -> bool:
        """Check if AI should use existing rate limiting infrastructure."""
        return cls.AI_USE_EXISTING_RATE_LIMITS
    
    @classmethod
    def should_integrate_audit_logging(cls) -> bool:
        """Check if AI should integrate with existing audit logging."""
        return cls.AI_INTEGRATE_AUDIT_LOGGING


# Global configuration instance
ai_security_config = AISecurityConfig()