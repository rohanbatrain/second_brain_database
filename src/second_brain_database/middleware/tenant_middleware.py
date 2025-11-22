"""
Tenant middleware for automatic tenant context injection.

This middleware extracts tenant information from requests and sets the
tenant context for the duration of the request.
"""

from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.middleware.tenant_context import clear_tenant_context, set_tenant_context

logger = get_logger(prefix="[Tenant Middleware]")


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and set tenant context for each request.

    Tenant identification strategies (in order of precedence):
    1. Custom domain (e.g., acme.secondbrain.com -> tenant via DB lookup)
    2. Subdomain (e.g., acme.app.com -> tenant_acme)
    3. X-Tenant-ID header (for API clients)
    4. User's primary tenant (from request.state.user if authenticated)
    5. Default tenant (for backward compatibility)
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and inject tenant context."""
        tenant_id = None

        try:
            # Strategy 1: Custom domain lookup
            host = request.headers.get("host", "").split(":")[0]  # Remove port
            if host and not host.startswith("localhost") and not host.startswith("127.0.0.1"):
                tenant_id = await self._lookup_tenant_by_domain(host)

            # Strategy 2: Subdomain extraction
            if not tenant_id:
                tenant_id = self._extract_tenant_from_subdomain(host)

            # Strategy 3: Header-based (for API clients)
            if not tenant_id:
                tenant_id = request.headers.get("X-Tenant-ID")

            # Strategy 4: User's primary tenant (from authenticated user)
            if not tenant_id and hasattr(request.state, "user"):
                user = request.state.user
                if isinstance(user, dict):
                    tenant_id = user.get("primary_tenant_id")

            # Strategy 5: Default tenant for backward compatibility
            if not tenant_id:
                tenant_id = settings.DEFAULT_TENANT_ID

            # Set tenant context
            set_tenant_context(tenant_id)

            # Add tenant_id to request state for easy access
            request.state.tenant_id = tenant_id

            logger.debug(
                "Tenant context set for request: %s %s -> tenant_id=%s",
                request.method,
                request.url.path,
                tenant_id,
            )

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error("Error in tenant middleware: %s", e, exc_info=True)
            # Continue with default tenant on error
            if not tenant_id:
                tenant_id = settings.DEFAULT_TENANT_ID
                set_tenant_context(tenant_id)
            response = await call_next(request)
            return response

        finally:
            # Always clear tenant context after request
            clear_tenant_context()

    async def _lookup_tenant_by_domain(self, domain: str) -> Optional[str]:
        """
        Look up tenant by custom domain.

        Args:
            domain: The domain to look up

        Returns:
            Optional[str]: Tenant ID if found, None otherwise
        """
        try:
            tenants_collection = db_manager.get_collection("tenants")
            tenant = await tenants_collection.find_one({"settings.custom_domain": domain})

            if tenant:
                logger.debug("Found tenant by custom domain: %s -> %s", domain, tenant["tenant_id"])
                return tenant["tenant_id"]

        except Exception as e:
            logger.warning("Failed to lookup tenant by domain %s: %s", domain, e)

        return None

    def _extract_tenant_from_subdomain(self, host: str) -> Optional[str]:
        """
        Extract tenant from subdomain.

        Args:
            host: The host header value

        Returns:
            Optional[str]: Tenant ID extracted from subdomain, or None
        """
        try:
            # Check if this looks like a subdomain (e.g., acme.app.com)
            parts = host.split(".")
            if len(parts) >= 3:  # Has subdomain
                subdomain = parts[0]
                # Skip common subdomains
                if subdomain not in ["www", "api", "app", "localhost"]:
                    tenant_id = f"tenant_{subdomain}"
                    logger.debug("Extracted tenant from subdomain: %s -> %s", host, tenant_id)
                    return tenant_id

        except Exception as e:
            logger.warning("Failed to extract tenant from subdomain %s: %s", host, e)

        return None
