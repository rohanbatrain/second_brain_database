"""
OAuth2 provider package.

This package implements a complete OAuth2 2.1 authorization server (provider)
that allows client applications to authenticate users and access authorized resources.
"""

from .routes import router
from .security_manager import oauth2_security_manager

__all__ = ["router", "oauth2_security_manager"]