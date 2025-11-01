"""
AI Security Configuration Validator

This module validates AI security configuration to ensure proper setup
and identifies potential security misconfigurations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import os

from ....managers.logging_manager import get_logger
from ....config import settings

logger = get_logger(prefix="[AISecurityConfigValidator]")


class AISecurityConfigValidator:
    """
    Validates AI security configuration and identifies potential issues.
    """
    
    def __init__(self):
        self.logger = logger
        self.validation_results = []
        
    async def validate_configuration(self) -> Dict[str, Any]:
        """
        Perform comprehensive validation of AI security configuration.
        
        Returns:
            Dictionary with validation results and recommendations
        """
        self.validation_results = []
        
        # Validate basic security settings
        await self._validate_basic_security()
        
        # Validate rate limiting configuration
        await self._validate_rate_limiting()
        
        # Validate authentication settings
        await self._validate_authentication()
        
        # Validate encryption settings
        await self._validate_encryption()
        
        # Validate logging and monitoring
        await self._validate_logging_monitoring()
        
        # Validate environment-specific settings
        await self._validate_environment_settings()
        
        # Generate summary
        return self._generate_validation_summary()
    
    async def _validate_basic_security(self) -> None:
        """Validate basic security settings."""
        try:
            # Check if security is enabled
            security_enabled = getattr(settings, 'MCP_SECURITY_ENABLED', False)
            if not security_enabled:
                self._add_warning(
                    "MCP_SECURITY_ENABLED",
                    "AI security is disabled",
                    "Enable MCP_SECURITY_ENABLED=true for production"
                )
            else:
                self._add_success("MCP_SECURITY_ENABLED", "AI security is enabled")
            
            # Check authentication requirement
            require_auth = getattr(settings, 'MCP_REQUIRE_AUTH', False)
            if not require_auth:
                self._add_warning(
                    "MCP_REQUIRE_AUTH",
                    "Authentication not required for AI operations",
                    "Enable MCP_REQUIRE_AUTH=true for production"
                )
            else:
                self._add_success("MCP_REQUIRE_AUTH", "Authentication is required")
            
            # Check audit logging
            audit_enabled = getattr(settings, 'MCP_AUDIT_ENABLED', False)
            if not audit_enabled:
                self._add_warning(
                    "MCP_AUDIT_ENABLED",
                    "AI audit logging is disabled",
                    "Enable MCP_AUDIT_ENABLED=true for compliance"
                )
            else:
                self._add_success("MCP_AUDIT_ENABLED", "Audit logging is enabled")
                
        except Exception as e:
            self._add_error("BASIC_SECURITY", f"Error validating basic security: {str(e)}")
    
    async def _validate_rate_limiting(self) -> None:
        """Validate rate limiting configuration."""
        try:
            # Check AI rate limits
            ai_rate_limit = getattr(settings, 'AI_RATE_LIMIT_REQUESTS', 100)
            if ai_rate_limit > 1000:
                self._add_warning(
                    "AI_RATE_LIMIT_REQUESTS",
                    f"AI rate limit is very high: {ai_rate_limit}",
                    "Consider lowering for better security"
                )
            elif ai_rate_limit < 10:
                self._add_warning(
                    "AI_RATE_LIMIT_REQUESTS",
                    f"AI rate limit is very low: {ai_rate_limit}",
                    "May impact user experience"
                )
            else:
                self._add_success("AI_RATE_LIMIT_REQUESTS", f"Rate limit configured: {ai_rate_limit}")
            
            # Check quotas
            daily_quota = getattr(settings, 'AI_DAILY_QUOTA', 1000)
            hourly_quota = getattr(settings, 'AI_HOURLY_QUOTA', 100)
            
            if daily_quota < hourly_quota * 24:
                self._add_warning(
                    "AI_QUOTAS",
                    "Daily quota is less than 24x hourly quota",
                    "Adjust quotas for consistency"
                )
            else:
                self._add_success("AI_QUOTAS", "Quota configuration is consistent")
                
        except Exception as e:
            self._add_error("RATE_LIMITING", f"Error validating rate limiting: {str(e)}")
    
    async def _validate_authentication(self) -> None:
        """Validate authentication configuration."""
        try:
            # Check JWT secret
            jwt_secret = getattr(settings, 'SECRET_KEY', '')
            if not jwt_secret:
                self._add_error(
                    "SECRET_KEY",
                    "JWT secret key is not configured",
                    "Set SECRET_KEY environment variable"
                )
            elif len(jwt_secret) < 32:
                self._add_warning(
                    "SECRET_KEY",
                    "JWT secret key is too short",
                    "Use a secret key with at least 32 characters"
                )
            else:
                self._add_success("SECRET_KEY", "JWT secret key is properly configured")
            
            # Check MCP auth token
            mcp_auth_token = getattr(settings, 'MCP_AUTH_TOKEN', '')
            if not mcp_auth_token:
                self._add_warning(
                    "MCP_AUTH_TOKEN",
                    "MCP authentication token is not configured",
                    "Set MCP_AUTH_TOKEN for enhanced security"
                )
            elif len(mcp_auth_token) < 16:
                self._add_warning(
                    "MCP_AUTH_TOKEN",
                    "MCP auth token is too short",
                    "Use a longer token for better security"
                )
            else:
                self._add_success("MCP_AUTH_TOKEN", "MCP auth token is configured")
                
        except Exception as e:
            self._add_error("AUTHENTICATION", f"Error validating authentication: {str(e)}")
    
    async def _validate_encryption(self) -> None:
        """Validate encryption configuration."""
        try:
            # Check Fernet key
            fernet_key = getattr(settings, 'FERNET_KEY', '')
            if not fernet_key:
                self._add_warning(
                    "FERNET_KEY",
                    "Encryption key is not configured",
                    "Set FERNET_KEY for data encryption"
                )
            else:
                # Validate Fernet key format
                try:
                    from cryptography.fernet import Fernet
                    Fernet(fernet_key.encode())
                    self._add_success("FERNET_KEY", "Encryption key is valid")
                except Exception:
                    self._add_error(
                        "FERNET_KEY",
                        "Invalid Fernet key format",
                        "Generate a new Fernet key"
                    )
            
            # Check AI encryption key
            ai_encryption_key = getattr(settings, 'AI_ENCRYPTION_KEY', '')
            if not ai_encryption_key:
                self._add_info(
                    "AI_ENCRYPTION_KEY",
                    "AI-specific encryption key not configured",
                    "Optional: Set AI_ENCRYPTION_KEY for AI data encryption"
                )
            else:
                self._add_success("AI_ENCRYPTION_KEY", "AI encryption key is configured")
                
        except Exception as e:
            self._add_error("ENCRYPTION", f"Error validating encryption: {str(e)}")
    
    async def _validate_logging_monitoring(self) -> None:
        """Validate logging and monitoring configuration."""
        try:
            # Check Redis connection for audit logs
            redis_url = getattr(settings, 'REDIS_URL', '')
            if not redis_url:
                self._add_error(
                    "REDIS_URL",
                    "Redis URL is not configured",
                    "Set REDIS_URL for session management and audit logs"
                )
            else:
                self._add_success("REDIS_URL", "Redis is configured")
            
            # Check MongoDB for persistent storage
            mongodb_url = getattr(settings, 'MONGODB_URL', '')
            if not mongodb_url:
                self._add_error(
                    "MONGODB_URL",
                    "MongoDB URL is not configured",
                    "Set MONGODB_URL for data persistence"
                )
            else:
                self._add_success("MONGODB_URL", "MongoDB is configured")
            
            # Check log level
            log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
            if log_level == 'DEBUG':
                self._add_warning(
                    "LOG_LEVEL",
                    "Debug logging is enabled",
                    "Use INFO or WARNING level in production"
                )
            else:
                self._add_success("LOG_LEVEL", f"Log level is appropriate: {log_level}")
                
        except Exception as e:
            self._add_error("LOGGING_MONITORING", f"Error validating logging: {str(e)}")
    
    async def _validate_environment_settings(self) -> None:
        """Validate environment-specific settings."""
        try:
            # Check environment
            env = getattr(settings, 'ENVIRONMENT', 'development')
            
            if env == 'production':
                # Production-specific validations
                debug_mode = getattr(settings, 'MCP_DEBUG_MODE', False)
                if debug_mode:
                    self._add_error(
                        "MCP_DEBUG_MODE",
                        "Debug mode is enabled in production",
                        "Disable MCP_DEBUG_MODE in production"
                    )
                
                # Check HTTPS enforcement
                force_https = getattr(settings, 'FORCE_HTTPS', False)
                if not force_https:
                    self._add_warning(
                        "FORCE_HTTPS",
                        "HTTPS is not enforced",
                        "Enable FORCE_HTTPS=true in production"
                    )
                
                self._add_success("ENVIRONMENT", "Production environment detected")
            else:
                self._add_info("ENVIRONMENT", f"Environment: {env}")
            
            # Check CORS settings
            cors_origins = getattr(settings, 'CORS_ORIGINS', [])
            if '*' in cors_origins and env == 'production':
                self._add_warning(
                    "CORS_ORIGINS",
                    "CORS allows all origins in production",
                    "Restrict CORS origins for security"
                )
                
        except Exception as e:
            self._add_error("ENVIRONMENT", f"Error validating environment: {str(e)}")
    
    def _add_success(self, component: str, message: str) -> None:
        """Add a success validation result."""
        self.validation_results.append({
            "component": component,
            "level": "SUCCESS",
            "message": message,
            "recommendation": None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def _add_info(self, component: str, message: str, recommendation: str = None) -> None:
        """Add an info validation result."""
        self.validation_results.append({
            "component": component,
            "level": "INFO",
            "message": message,
            "recommendation": recommendation,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def _add_warning(self, component: str, message: str, recommendation: str = None) -> None:
        """Add a warning validation result."""
        self.validation_results.append({
            "component": component,
            "level": "WARNING",
            "message": message,
            "recommendation": recommendation,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def _add_error(self, component: str, message: str, recommendation: str = None) -> None:
        """Add an error validation result."""
        self.validation_results.append({
            "component": component,
            "level": "ERROR",
            "message": message,
            "recommendation": recommendation,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def _generate_validation_summary(self) -> Dict[str, Any]:
        """Generate validation summary."""
        summary = {
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_checks": len(self.validation_results),
            "results_by_level": {
                "SUCCESS": 0,
                "INFO": 0,
                "WARNING": 0,
                "ERROR": 0
            },
            "security_score": 0,
            "recommendations": [],
            "critical_issues": [],
            "results": self.validation_results
        }
        
        # Count results by level
        for result in self.validation_results:
            level = result["level"]
            summary["results_by_level"][level] += 1
            
            # Collect recommendations
            if result.get("recommendation"):
                summary["recommendations"].append({
                    "component": result["component"],
                    "level": level,
                    "recommendation": result["recommendation"]
                })
            
            # Collect critical issues
            if level == "ERROR":
                summary["critical_issues"].append({
                    "component": result["component"],
                    "message": result["message"]
                })
        
        # Calculate security score (0-100)
        total_checks = len(self.validation_results)
        if total_checks > 0:
            success_count = summary["results_by_level"]["SUCCESS"]
            info_count = summary["results_by_level"]["INFO"]
            warning_count = summary["results_by_level"]["WARNING"]
            error_count = summary["results_by_level"]["ERROR"]
            
            # Weighted scoring: SUCCESS=1, INFO=0.8, WARNING=0.5, ERROR=0
            weighted_score = (success_count * 1.0 + info_count * 0.8 + warning_count * 0.5)
            summary["security_score"] = int((weighted_score / total_checks) * 100)
        
        # Overall assessment
        if summary["security_score"] >= 90:
            summary["assessment"] = "EXCELLENT"
        elif summary["security_score"] >= 75:
            summary["assessment"] = "GOOD"
        elif summary["security_score"] >= 60:
            summary["assessment"] = "FAIR"
        else:
            summary["assessment"] = "NEEDS_IMPROVEMENT"
        
        return summary


# Global instance
ai_security_config_validator = AISecurityConfigValidator()