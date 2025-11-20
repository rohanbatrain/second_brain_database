"""
Blog Authentication Manager for website-scoped authentication and authorization.

This module provides website-level authentication with role-based access control,
extending the existing JWT authentication system to support multi-tenant blog operations.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.models.blog_models import WebsiteRole
from second_brain_database.routes.auth.services.auth.login import get_current_user

logger = get_logger(prefix="[Blog Auth Manager]")


class BlogAuthManager:
    """
    Manager for blog website authentication and authorization.

    Handles website-scoped JWT tokens, role-based access control, and
    website-level permission checking.
    """

    def __init__(self):
        self.redis = redis_manager

    async def create_website_token(
        self,
        user_id: str,
        username: str,
        website_id: str,
        role: WebsiteRole,
        expires_minutes: int = 30
    ) -> str:
        """
        Create a website-scoped JWT token.

        Args:
            user_id: User ID
            username: Username
            website_id: Website ID
            role: Website role
            expires_minutes: Token expiration time

        Returns:
            JWT token string
        """
        try:
            expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
            to_encode = {
                "sub": username,
                "user_id": user_id,
                "website_id": website_id,
                "role": role.value,
                "exp": expire,
                "iat": datetime.utcnow(),
                "token_type": "website"
            }

            secret_key = getattr(settings, "SECRET_KEY", None)
            if hasattr(secret_key, "get_secret_value"):
                secret_key = secret_key.get_secret_value()

            if not isinstance(secret_key, (str, bytes)) or not secret_key:
                raise RuntimeError("JWT secret key is missing or invalid")

            encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.ALGORITHM)

            # Cache token for quick validation
            cache_key = f"blog:token:{encoded_jwt[:16]}"
            await self.redis.setex(cache_key, expires_minutes * 60, "valid")

            logger.debug("Created website token for user %s on website %s with role %s",
                        username, website_id, role.value)
            return encoded_jwt

        except Exception as e:
            logger.error("Failed to create website token: %s", e, exc_info=True)
            raise

    async def validate_website_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a website-scoped JWT token.

        Args:
            token: JWT token string

        Returns:
            Token payload with user and website info

        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Check cache first
            cache_key = f"blog:token:{token[:16]}"
            if not await self.redis.get(cache_key):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token is invalid or expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            secret_key = getattr(settings, "SECRET_KEY", None)
            if hasattr(secret_key, "get_secret_value"):
                secret_key = secret_key.get_secret_value()

            if not isinstance(secret_key, (str, bytes)) or not secret_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Server configuration error",
                )

            payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])

            # Validate required claims
            required_claims = ["sub", "user_id", "website_id", "role", "token_type"]
            for claim in required_claims:
                if claim not in payload:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid token: missing {claim}",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

            if payload.get("token_type") != "website":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Validate role
            try:
                role = WebsiteRole(payload["role"])
                payload["role"] = role
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid role in token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            logger.debug("Validated website token for user %s on website %s",
                        payload["sub"], payload["website_id"])
            return payload

        except jwt.ExpiredSignatureError:
            # Remove from cache
            await self.redis.delete(cache_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError as e:
            logger.warning("JWT validation error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error("Unexpected error validating website token: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication error",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def check_website_permission(
        self,
        user_id: str,
        website_id: str,
        required_role: WebsiteRole = WebsiteRole.VIEWER
    ) -> Dict[str, Any]:
        """
        Check if user has permission for a website with required role.

        Args:
            user_id: User ID
            website_id: Website ID
            required_role: Minimum required role

        Returns:
            Membership info if user has permission

        Raises:
            HTTPException: If permission denied
        """
        try:
            from second_brain_database.managers.blog_manager import BlogWebsiteManager

            website_manager = BlogWebsiteManager()
            membership = await website_manager.check_website_access(user_id, website_id, required_role)

            if not membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions for this website",
                )

            return membership.model_dump()

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to check website permission: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission check failed",
            )

    async def invalidate_website_tokens(self, user_id: str, website_id: str):
        """
        Invalidate all website tokens for a user on a specific website.

        Args:
            user_id: User ID
            website_id: Website ID
        """
        try:
            # For now, we'll rely on token expiration
            # In production, you might want to maintain a blacklist
            logger.info("Invalidating website tokens for user %s on website %s",
                       user_id, website_id)

        except Exception as e:
            logger.error("Failed to invalidate website tokens: %s", e, exc_info=True)

    def get_role_hierarchy(self) -> Dict[WebsiteRole, int]:
        """Get role hierarchy levels for comparison."""
        return {
            WebsiteRole.VIEWER: 0,
            WebsiteRole.AUTHOR: 1,
            WebsiteRole.EDITOR: 2,
            WebsiteRole.ADMIN: 3,
            WebsiteRole.OWNER: 4
        }

    def has_role_level(self, user_role: WebsiteRole, required_role: WebsiteRole) -> bool:
        """Check if user role meets or exceeds required role level."""
        hierarchy = self.get_role_hierarchy()
        return hierarchy.get(user_role, 0) >= hierarchy.get(required_role, 0)


# Global blog auth manager instance
blog_auth_manager = BlogAuthManager()

# OAuth2 scheme for website tokens
oauth2_website_scheme = OAuth2PasswordBearer(tokenUrl="/auth/blog/login")


async def get_current_website_user(token: str = Depends(oauth2_website_scheme)) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user for website operations.

    Returns user info with website context and role.
    """
    try:
        # Validate website token
        token_data = await blog_auth_manager.validate_website_token(token)

        # Get full user info
        user = await get_current_user(token)  # This will validate the base user

        # Add website context
        user["website_id"] = token_data["website_id"]
        user["website_role"] = token_data["role"]

        logger.debug("Authenticated website user: %s for website %s with role %s",
                    user.get("username"), token_data["website_id"], token_data["role"].value)

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get current website user: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Website authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_website_role(
    required_role: WebsiteRole,
    current_user: Dict[str, Any] = Depends(get_current_website_user)
) -> Dict[str, Any]:
    """
    Dependency to require specific website role.

    Args:
        required_role: Minimum required role
        current_user: Current authenticated user with website context

    Returns:
        User info if role requirement met

    Raises:
        HTTPException: If role requirement not met
    """
    try:
        user_role = current_user.get("website_role")
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No website role assigned",
            )

        if not blog_auth_manager.has_role_level(user_role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_role.value}, your role: {user_role.value}",
            )

        return current_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to check website role: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role validation failed",
        )


async def require_website_owner(
    current_user: Dict[str, Any] = Depends(get_current_website_user)
) -> Dict[str, Any]:
    """Require website owner role."""
    return await require_website_role(WebsiteRole.OWNER, current_user)


async def require_website_admin(
    current_user: Dict[str, Any] = Depends(get_current_website_user)
) -> Dict[str, Any]:
    """Require website admin role or higher."""
    return await require_website_role(WebsiteRole.ADMIN, current_user)


async def require_website_editor(
    current_user: Dict[str, Any] = Depends(get_current_website_user)
) -> Dict[str, Any]:
    """Require website editor role or higher."""
    return await require_website_role(WebsiteRole.EDITOR, current_user)


async def require_website_author(
    current_user: Dict[str, Any] = Depends(get_current_website_user)
) -> Dict[str, Any]:
    """Require website author role or higher."""
    return await require_website_role(WebsiteRole.AUTHOR, current_user)


async def require_website_viewer(
    current_user: Dict[str, Any] = Depends(get_current_website_user)
) -> Dict[str, Any]:
    """Require website viewer role or higher (any role)."""
    return await require_website_role(WebsiteRole.VIEWER, current_user)