"""
Refresh token endpoint implementation.

This module provides the enhanced refresh token functionality that uses
refresh tokens (not access tokens) to obtain new access tokens.
"""

from datetime import datetime
from fastapi import HTTPException, Request, status, Body
from jose import jwt, JWTError

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.models import Token
from second_brain_database.routes.auth.services.auth.login import create_access_token, create_refresh_token
from second_brain_database.routes.auth.services.security.tokens import is_token_blacklisted, blacklist_token
from second_brain_database.utils.logging_utils import log_performance

logger = get_logger(prefix="[Auth Refresh]")


@log_performance("refresh_access_token")
async def refresh_access_token(refresh_token_str: str, request_ip: str = None) -> Token:
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_token_str: The refresh token JWT string
        request_ip: IP address of the request (for logging)
    
    Returns:
        Token: New access token and optionally new refresh token
    
    Raises:
        HTTPException: If refresh token is invalid, expired, or user not found
    """
    try:
        # Get refresh token secret key
        refresh_secret_key = getattr(settings, "REFRESH_TOKEN_SECRET_KEY", None)
        if hasattr(refresh_secret_key, "get_secret_value"):
            refresh_secret_key = refresh_secret_key.get_secret_value()
        
        # Fallback to regular SECRET_KEY if not set (backward compatibility)
        if not refresh_secret_key or not isinstance(refresh_secret_key, (str, bytes)):
            logger.warning("REFRESH_TOKEN_SECRET_KEY not set, using SECRET_KEY")
            refresh_secret_key = getattr(settings, "SECRET_KEY", None)
            if hasattr(refresh_secret_key, "get_secret_value"):
                refresh_secret_key = refresh_secret_key.get_secret_value()

        # Decode refresh token
        payload = jwt.decode(refresh_token_str, refresh_secret_key, algorithms=[settings.ALGORITHM])

        # Verify token type
        if payload.get("type") != "refresh":
            logger.warning("Invalid token type: %s", payload.get("type"))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "invalid_token_type",
                    "message": "Token is not a refresh token",
                    "action": "login"
                },
            )

        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "invalid_token",
                    "message": "Invalid refresh token",
                    "action": "login"
                }
            )

        # Check if token is blacklisted
        if await is_token_blacklisted(refresh_token_str):
            logger.warning("Attempted use of blacklisted refresh token for user: %s from IP: %s", username, request_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "token_revoked",
                    "message": "Refresh token has been revoked",
                    "action": "login"
                },
            )

        # Get user and verify they exist and are active
        user = await db_manager.get_collection("users").find_one({"username": username})
        if not user:
            logger.warning("User not found for refresh token: %s", username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "user_not_found",
                    "message": "User not found",
                    "action": "login"
                },
            )
        
        if not user.get("is_active", True):
            logger.warning("Inactive user attempted token refresh: %s", username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "user_inactive",
                    "message": "User account is inactive",
                    "action": "login"
                },
            )

        # Generate new access token
        new_access_token = await create_access_token({"sub": username})

        response_data = {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

        # Token rotation (if enabled)
        if settings.ENABLE_TOKEN_ROTATION:
            # Blacklist old refresh token
            await blacklist_token(refresh_token_str, expires_in_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

            # Generate new refresh token
            new_refresh_token = await create_refresh_token({"sub": username})
            response_data["refresh_token"] = new_refresh_token
            response_data["refresh_expires_in"] = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400

            logger.info("Token refreshed with rotation for user: %s from IP: %s", username, request_ip)
        else:
            # Return same refresh token (no rotation)
            response_data["refresh_token"] = refresh_token_str
            response_data["refresh_expires_in"] = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
            logger.info("Token refreshed without rotation for user: %s from IP: %s", username, request_ip)

        return Token(**response_data)

    except jwt.ExpiredSignatureError:
        logger.warning("Expired refresh token used from IP: %s", request_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "refresh_token_expired",
                "message": "Refresh token has expired. Please login again.",
                "action": "login",
            },
        )
    except JWTError as e:
        logger.warning("Invalid refresh token from IP %s: %s", request_ip, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": "Invalid refresh token",
                "action": "login"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        ) from e
