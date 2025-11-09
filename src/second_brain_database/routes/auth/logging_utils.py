"""
Authentication-specific logging utilities.

This module provides specialized logging utilities for authentication operations,
building on the comprehensive logging infrastructure in utils.logging_utils.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Request

from second_brain_database.managers.security_manager import security_manager
from second_brain_database.utils.logging_utils import (
    SecurityContext,
    SecurityLogger,
    ip_address_context,
    log_auth_failure,
    log_auth_success,
    log_security_event,
    request_id_context,
    user_id_context,
)


class AuthLogger:
    """Centralized authentication logging utilities."""

    def __init__(self):
        self.security_logger = SecurityLogger(prefix="[AUTH]")

    def log_registration_attempt(
        self,
        username: str,
        email: str,
        ip_address: str = "",
        success: bool = True,
        reason: Optional[str] = None,
        user_agent: str = "",
    ):
        """Log user registration attempts."""
        details = {
            "username": username,
            "email": email,
            "user_agent": user_agent[:100] if user_agent else "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if reason:
            details["reason"] = reason

        if success:
            log_auth_success(event_type="registration", user_id=username, ip_address=ip_address, details=details)
        else:
            log_auth_failure(event_type="registration", user_id=username, ip_address=ip_address, details=details)

    def log_login_attempt(
        self,
        identifier: str,
        ip_address: str = "",
        success: bool = True,
        reason: Optional[str] = None,
        mfa_required: bool = False,
        user_agent: str = "",
    ):
        """Log user login attempts."""
        details = {
            "identifier": identifier,
            "user_agent": user_agent[:100] if user_agent else "",
            "mfa_required": mfa_required,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if reason:
            details["reason"] = reason

        if success:
            log_auth_success(event_type="login", user_id=identifier, ip_address=ip_address, details=details)
        else:
            log_auth_failure(event_type="login", user_id=identifier, ip_address=ip_address, details=details)

    def log_logout_attempt(
        self, user_id: str, ip_address: str = "", success: bool = True, reason: Optional[str] = None
    ):
        """Log user logout attempts."""
        details = {"timestamp": datetime.now(timezone.utc).isoformat()}

        if reason:
            details["reason"] = reason

        if success:
            log_auth_success(event_type="logout", user_id=user_id, ip_address=ip_address, details=details)
        else:
            log_auth_failure(event_type="logout", user_id=user_id, ip_address=ip_address, details=details)

    def log_password_change(
        self, user_id: str, ip_address: str = "", success: bool = True, reason: Optional[str] = None
    ):
        """Log password change attempts."""
        details = {"timestamp": datetime.now(timezone.utc).isoformat()}

        if reason:
            details["reason"] = reason

        if success:
            log_auth_success(event_type="password_change", user_id=user_id, ip_address=ip_address, details=details)
        else:
            log_auth_failure(event_type="password_change", user_id=user_id, ip_address=ip_address, details=details)

    def log_password_reset_request(
        self,
        email: str,
        ip_address: str = "",
        success: bool = True,
        reason: Optional[str] = None,
        suspicious: bool = False,
        abuse_reasons: Optional[list] = None,
    ):
        """Log password reset requests."""
        details = {"email": email, "suspicious": suspicious, "timestamp": datetime.now(timezone.utc).isoformat()}

        if reason:
            details["reason"] = reason

        if abuse_reasons:
            details["abuse_reasons"] = abuse_reasons

        if suspicious:
            log_security_event(
                event_type="password_reset_suspicious", details=details, user_id=email, ip_address=ip_address
            )
        elif success:
            log_auth_success(event_type="password_reset_request", user_id=email, ip_address=ip_address, details=details)
        else:
            log_auth_failure(event_type="password_reset_request", user_id=email, ip_address=ip_address, details=details)

    def log_email_verification(
        self, user_id: str, email: str, ip_address: str = "", success: bool = True, reason: Optional[str] = None
    ):
        """Log email verification attempts."""
        details = {"email": email, "timestamp": datetime.now(timezone.utc).isoformat()}

        if reason:
            details["reason"] = reason

        if success:
            log_auth_success(event_type="email_verification", user_id=user_id, ip_address=ip_address, details=details)
        else:
            log_auth_failure(event_type="email_verification", user_id=user_id, ip_address=ip_address, details=details)

    def log_2fa_setup(self, user_id: str, ip_address: str = "", success: bool = True, reason: Optional[str] = None):
        """Log 2FA setup attempts."""
        details = {"timestamp": datetime.now(timezone.utc).isoformat()}

        if reason:
            details["reason"] = reason

        if success:
            log_auth_success(event_type="2fa_setup", user_id=user_id, ip_address=ip_address, details=details)
        else:
            log_auth_failure(event_type="2fa_setup", user_id=user_id, ip_address=ip_address, details=details)

    def log_2fa_verification(
        self, user_id: str, method: str, ip_address: str = "", success: bool = True, reason: Optional[str] = None
    ):
        """Log 2FA verification attempts."""
        details = {"method": method, "timestamp": datetime.now(timezone.utc).isoformat()}

        if reason:
            details["reason"] = reason

        if success:
            log_auth_success(event_type="2fa_verification", user_id=user_id, ip_address=ip_address, details=details)
        else:
            log_auth_failure(event_type="2fa_verification", user_id=user_id, ip_address=ip_address, details=details)

    def log_token_operation(
        self,
        user_id: str,
        operation: str,
        token_type: str = "access",
        ip_address: str = "",
        success: bool = True,
        reason: Optional[str] = None,
    ):
        """Log token operations (refresh, revoke, etc.)."""
        details = {
            "operation": operation,
            "token_type": token_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if reason:
            details["reason"] = reason

        if success:
            log_auth_success(event_type=f"token_{operation}", user_id=user_id, ip_address=ip_address, details=details)
        else:
            log_auth_failure(event_type=f"token_{operation}", user_id=user_id, ip_address=ip_address, details=details)

    def log_rate_limit_exceeded(self, endpoint: str, ip_address: str = "", user_id: Optional[str] = None):
        """Log rate limit violations."""
        details = {"endpoint": endpoint, "timestamp": datetime.now(timezone.utc).isoformat()}

        log_security_event(event_type="rate_limit_exceeded", details=details, user_id=user_id, ip_address=ip_address)

    def log_suspicious_activity(
        self, activity_type: str, details: Dict[str, Any], user_id: Optional[str] = None, ip_address: str = ""
    ):
        """Log suspicious security activities."""
        enhanced_details = {**details, "timestamp": datetime.now(timezone.utc).isoformat()}

        log_security_event(
            event_type=f"suspicious_{activity_type}", details=enhanced_details, user_id=user_id, ip_address=ip_address
        )


def extract_request_info(request: Request) -> Dict[str, str]:
    """Extract common request information for logging."""
    return {
        "ip_address": security_manager.get_client_ip(request) if request else "",
        "user_agent": request.headers.get("user-agent", "") if request else "",
        "request_id": request_id_context.get(""),
    }


def set_auth_context(user_id: Optional[str] = None, ip_address: Optional[str] = None):
    """Set authentication context for logging."""
    if user_id:
        user_id_context.set(user_id)
    if ip_address:
        ip_address_context.set(ip_address)


# Global auth logger instance
auth_logger = AuthLogger()
