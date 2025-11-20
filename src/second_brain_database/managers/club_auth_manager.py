"""
Club Authentication Manager for club-scoped authentication and authorization.

This module provides club-level authentication with role-based access control,
extending the existing JWT authentication system to support multi-tenant club operations.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.club_models import ClubRole
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[Club Auth Manager]")


class ClubAuthManager:
    """
    Manager for club authentication and authorization.

    Handles club-scoped JWT tokens, role-based access control, and
    club-level permission checking.
    """

    def __init__(self):
        self.redis = redis_manager

    async def create_club_token(
        self,
        user_id: str,
        username: str,
        club_id: str,
        role: ClubRole,
        vertical_id: Optional[str] = None,
        expires_minutes: int = 30
    ) -> str:
        """
        Create a club-scoped JWT token.

        Args:
            user_id: User ID
            username: Username
            club_id: Club ID
            role: Club role
            vertical_id: Optional vertical ID
            expires_minutes: Token expiration time

        Returns:
            JWT token string
        """
        try:
            expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
            to_encode = {
                "sub": username,
                "user_id": user_id,
                "club_id": club_id,
                "role": role.value,
                "vertical_id": vertical_id,
                "exp": expire,
                "iat": datetime.utcnow(),
                "token_type": "club"
            }

            secret_key = getattr(settings, "SECRET_KEY", None)
            if hasattr(secret_key, "get_secret_value"):
                secret_key = secret_key.get_secret_value()

            if not isinstance(secret_key, (str, bytes)) or not secret_key:
                raise RuntimeError("JWT secret key is missing or invalid")

            encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.ALGORITHM)

            # Cache token for quick validation
            cache_key = f"club:token:{encoded_jwt[:16]}"
            await self.redis.setex(cache_key, expires_minutes * 60, "valid")

            logger.debug("Created club token for user %s on club %s with role %s",
                        username, club_id, role.value)
            return encoded_jwt

        except Exception as e:
            logger.error("Failed to create club token: %s", e, exc_info=True)
            raise

    async def validate_club_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a club-scoped JWT token.

        Args:
            token: JWT token string

        Returns:
            Token payload with user and club info

        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Check cache first
            cache_key = f"club:token:{token[:16]}"
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
            required_claims = ["sub", "user_id", "club_id", "role", "token_type"]
            for claim in required_claims:
                if claim not in payload:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid token: missing {claim}",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

            if payload.get("token_type") != "club":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Validate role
            try:
                role = ClubRole(payload["role"])
                payload["role"] = role
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid role in token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            logger.debug("Validated club token for user %s on club %s",
                        payload["sub"], payload["club_id"])
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
            logger.error("Unexpected error validating club token: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication error",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def check_club_permission(
        self,
        user_id: str,
        club_id: str,
        required_role: ClubRole = ClubRole.MEMBER
    ) -> Dict[str, Any]:
        """
        Check if user has permission for a club with required role.

        Args:
            user_id: User ID
            club_id: Club ID
            required_role: Minimum required role

        Returns:
            Membership info if user has permission

        Raises:
            HTTPException: If permission denied
        """
        try:
            from second_brain_database.managers.club_manager import ClubManager

            club_manager = ClubManager()
            membership = await club_manager.check_club_access(user_id, club_id, required_role)

            if not membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions for this club",
                )

            return membership.model_dump()

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to check club permission: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission check failed",
            )

    async def check_vertical_permission(
        self,
        user_id: str,
        club_id: str,
        vertical_id: str,
        required_role: ClubRole = ClubRole.LEAD
    ) -> Dict[str, Any]:
        """
        Check if user has permission for a vertical within a club.

        Args:
            user_id: User ID
            club_id: Club ID
            vertical_id: Vertical ID
            required_role: Minimum required role

        Returns:
            Membership info if user has permission

        Raises:
            HTTPException: If permission denied
        """
        try:
            from second_brain_database.managers.club_manager import ClubManager

            club_manager = ClubManager()

            # Check basic club access
            membership = await club_manager.check_club_access(user_id, club_id, ClubRole.MEMBER)
            if not membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not a member of this club",
                )

            # Check if user is vertical lead or has higher club role
            if membership.role in [ClubRole.ADMIN, ClubRole.OWNER]:
                return membership.model_dump()

            # Check if user is lead of this specific vertical
            if membership.vertical_id == vertical_id and membership.role == ClubRole.LEAD:
                return membership.model_dump()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this vertical",
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to check vertical permission: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission check failed",
            )

    async def invalidate_club_tokens(self, user_id: str, club_id: str):
        """
        Invalidate all club tokens for a user on a specific club.

        Args:
            user_id: User ID
            club_id: Club ID
        """
        try:
            # For now, we'll rely on token expiration
            # In production, you might want to maintain a blacklist
            logger.info("Invalidating club tokens for user %s on club %s",
                       user_id, club_id)

        except Exception as e:
            logger.error("Failed to invalidate club tokens: %s", e, exc_info=True)

    def get_role_hierarchy(self) -> Dict[ClubRole, int]:
        """Get role hierarchy levels for comparison."""
        return {
            ClubRole.MEMBER: 0,
            ClubRole.LEAD: 1,
            ClubRole.ADMIN: 2,
            ClubRole.OWNER: 3
        }

    def has_role_level(self, user_role: ClubRole, required_role: ClubRole) -> bool:
        """Check if user role meets or exceeds required role level."""
        hierarchy = self.get_role_hierarchy()
        return hierarchy.get(user_role, 0) >= hierarchy.get(required_role, 0)


# Global club auth manager instance
club_auth_manager = ClubAuthManager()

# OAuth2 scheme for club tokens
oauth2_club_scheme = OAuth2PasswordBearer(tokenUrl="/auth/club/login")


async def get_current_club_user(token: str = Depends(oauth2_club_scheme)) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user for club operations.

    Returns user info with club context and role.
    """
    try:
        # Validate club token
        token_data = await club_auth_manager.validate_club_token(token)

        # Get full user info (assuming we have a way to get base user)
        # For now, we'll construct from token data
        user = {
            "username": token_data["sub"],
            "user_id": token_data["user_id"],
            "club_id": token_data["club_id"],
            "club_role": token_data["role"],
            "vertical_id": token_data.get("vertical_id")
        }

        logger.debug("Authenticated club user: %s for club %s with role %s",
                    user.get("username"), token_data["club_id"], token_data["role"].value)

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get current club user: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Club authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_club_role(
    required_role: ClubRole,
    current_user: Dict[str, Any] = Depends(get_current_club_user)
) -> Dict[str, Any]:
    """
    Dependency to require specific club role.

    Args:
        required_role: Minimum required role
        current_user: Current authenticated user with club context

    Returns:
        User info if role requirement met

    Raises:
        HTTPException: If role requirement not met
    """
    try:
        user_role = current_user.get("club_role")
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No club role assigned",
            )

        if not club_auth_manager.has_role_level(user_role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_role.value}, your role: {user_role.value}",
            )

        return current_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to check club role: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role validation failed",
        )


async def require_club_owner(
    current_user: Dict[str, Any] = Depends(get_current_club_user)
) -> Dict[str, Any]:
    """Require club owner role."""
    return await require_club_role(ClubRole.OWNER, current_user)


async def require_club_admin(
    current_user: Dict[str, Any] = Depends(get_current_club_user)
) -> Dict[str, Any]:
    """Require club admin role or higher."""
    return await require_club_role(ClubRole.ADMIN, current_user)


async def require_club_lead(
    current_user: Dict[str, Any] = Depends(get_current_club_user)
) -> Dict[str, Any]:
    """Require club lead role or higher."""
    return await require_club_role(ClubRole.LEAD, current_user)


async def require_club_member(
    current_user: Dict[str, Any] = Depends(get_current_club_user)
) -> Dict[str, Any]:
    """Require club member role or higher (any role)."""
    return await require_club_role(ClubRole.MEMBER, current_user)


async def require_vertical_lead(
    vertical_id: str,
    current_user: Dict[str, Any] = Depends(get_current_club_user)
) -> Dict[str, Any]:
    """
    Require vertical lead role for specific vertical.

    Args:
        vertical_id: Vertical ID to check lead permission for
        current_user: Current authenticated user

    Returns:
        User info if user is lead of the vertical

    Raises:
        HTTPException: If not lead of the vertical
    """
    try:
        # Check if user has admin/owner role (can manage any vertical)
        if current_user.get("club_role") in [ClubRole.ADMIN, ClubRole.OWNER]:
            return current_user

        # Check if user is lead of this specific vertical
        if (current_user.get("vertical_id") == vertical_id and
            current_user.get("club_role") == ClubRole.LEAD):
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Must be lead of this vertical",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to check vertical lead permission: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Permission validation failed",
        )