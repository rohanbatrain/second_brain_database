"""
Browser session management system for OAuth2 authentication.

This module provides comprehensive session management for browser-based OAuth2 flows,
including secure session creation, validation, cleanup, and Redis-based storage.
Designed to work alongside JWT-based API authentication without interference.

Features:
- Secure HTTP-only, Secure, and SameSite cookie handling
- Redis-based session storage with automatic expiration
- Background session cleanup tasks
- CSRF token generation and validation
- Session fingerprinting for security
- Comprehensive audit logging
"""

import asyncio
import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[OAuth2 Session Manager]")

# Session configuration constants
SESSION_COOKIE_NAME = "sbd_session"
CSRF_COOKIE_NAME = "sbd_csrf"
SESSION_PREFIX = "oauth2:session:"
CSRF_PREFIX = "oauth2:csrf:"
SESSION_CLEANUP_PREFIX = "oauth2:cleanup:"

# Session security settings
SESSION_EXPIRE_MINUTES = 60  # 1 hour default session lifetime
CSRF_TOKEN_LENGTH = 32
SESSION_ID_LENGTH = 32
MAX_SESSIONS_PER_USER = 10  # Maximum concurrent sessions per user
CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes cleanup interval


class BrowserSession(BaseModel):
    """
    Browser session data model.
    
    Represents a browser session stored in Redis with security metadata.
    """
    
    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="User ID associated with session")
    username: str = Field(..., description="Username for quick reference")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation timestamp")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    last_accessed_at: datetime = Field(default_factory=datetime.utcnow, description="Last access timestamp")
    ip_address: str = Field(..., description="Client IP address")
    user_agent: str = Field(..., description="Client user agent string")
    csrf_token: str = Field(..., description="CSRF protection token")
    fingerprint: str = Field(..., description="Session fingerprint for security")
    is_active: bool = Field(default=True, description="Whether session is active")
    
    # OAuth2 specific fields
    oauth2_state: Optional[str] = Field(None, description="OAuth2 state parameter")
    oauth2_client_id: Optional[str] = Field(None, description="OAuth2 client ID")
    oauth2_redirect_uri: Optional[str] = Field(None, description="OAuth2 redirect URI")
    oauth2_scopes: Optional[List[str]] = Field(None, description="OAuth2 requested scopes")


class SessionManager:
    """
    Manages browser sessions for OAuth2 authentication flows.
    
    Provides secure session creation, validation, cleanup, and Redis storage
    with comprehensive security features and audit logging.
    """
    
    def __init__(self):
        """Initialize the session manager."""
        self.logger = logger
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_cleanup_running = False
    
    async def create_session(
        self,
        user: Dict[str, Any],
        request: Request,
        response: Response,
        oauth2_context: Optional[Dict[str, Any]] = None
    ) -> BrowserSession:
        """
        Create a new browser session with secure cookies.
        
        Args:
            user: User document from database
            request: FastAPI request object
            response: FastAPI response object for setting cookies
            oauth2_context: Optional OAuth2 context (state, client_id, etc.)
            
        Returns:
            BrowserSession: Created session object
            
        Raises:
            HTTPException: If session creation fails
        """
        try:
            # Generate secure session ID and CSRF token
            session_id = self._generate_session_id()
            csrf_token = self._generate_csrf_token()
            
            # Extract client information
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            
            # Create session fingerprint for security
            fingerprint = self._create_session_fingerprint(client_ip, user_agent)
            
            # Calculate expiration
            expires_at = datetime.utcnow() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
            
            # Create session object
            session = BrowserSession(
                session_id=session_id,
                user_id=str(user["_id"]),
                username=user["username"],
                expires_at=expires_at,
                ip_address=client_ip,
                user_agent=user_agent,
                csrf_token=csrf_token,
                fingerprint=fingerprint
            )
            
            # Add OAuth2 context if provided
            if oauth2_context:
                session.oauth2_state = oauth2_context.get("state")
                session.oauth2_client_id = oauth2_context.get("client_id")
                session.oauth2_redirect_uri = oauth2_context.get("redirect_uri")
                session.oauth2_scopes = oauth2_context.get("scopes", [])
            
            # Store session in Redis
            await self._store_session(session)
            
            # Set secure cookies
            self._set_session_cookies(response, session_id, csrf_token, expires_at)
            
            # Clean up old sessions for this user
            await self._cleanup_user_sessions(user["_id"])
            
            # Log session creation
            self.logger.info(
                "Created browser session for user %s from IP %s",
                user["username"],
                client_ip,
                extra={
                    "user_id": str(user["_id"]),
                    "session_id": session_id,
                    "ip_address": client_ip,
                    "user_agent": user_agent,
                    "oauth2_client_id": session.oauth2_client_id
                }
            )
            
            return session
            
        except Exception as e:
            self.logger.error("Failed to create browser session: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )
    
    async def validate_session(
        self,
        request: Request,
        require_csrf: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Validate browser session from cookies.
        
        Args:
            request: FastAPI request object
            require_csrf: Whether to require CSRF token validation
            
        Returns:
            Optional[Dict[str, Any]]: User data if session is valid, None otherwise
        """
        try:
            # Get session ID from cookie
            session_id = request.cookies.get(SESSION_COOKIE_NAME)
            if not session_id:
                return None
            
            # Get session from Redis
            session = await self._get_session(session_id)
            if not session:
                return None
            
            # Check if session is expired
            if datetime.utcnow() > session.expires_at:
                await self._delete_session(session_id)
                self.logger.info("Expired session removed: %s", session_id)
                return None
            
            # Validate session fingerprint
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            current_fingerprint = self._create_session_fingerprint(client_ip, user_agent)
            
            if current_fingerprint != session.fingerprint:
                await self._delete_session(session_id)
                self.logger.warning(
                    "Session fingerprint mismatch for user %s, session invalidated",
                    session.username,
                    extra={
                        "user_id": session.user_id,
                        "session_id": session_id,
                        "expected_fingerprint": session.fingerprint,
                        "actual_fingerprint": current_fingerprint
                    }
                )
                return None
            
            # Validate CSRF token if required
            if require_csrf:
                csrf_token = request.cookies.get(CSRF_COOKIE_NAME)
                if not csrf_token or csrf_token != session.csrf_token:
                    self.logger.warning(
                        "CSRF token validation failed for user %s",
                        session.username,
                        extra={
                            "user_id": session.user_id,
                            "session_id": session_id
                        }
                    )
                    return None
            
            # Update last accessed time
            session.last_accessed_at = datetime.utcnow()
            await self._store_session(session)
            
            # Return user data
            return {
                "_id": session.user_id,
                "username": session.username,
                "session_id": session_id,
                "csrf_token": session.csrf_token,
                "oauth2_context": {
                    "state": session.oauth2_state,
                    "client_id": session.oauth2_client_id,
                    "redirect_uri": session.oauth2_redirect_uri,
                    "scopes": session.oauth2_scopes
                } if session.oauth2_state else None
            }
            
        except Exception as e:
            self.logger.error("Failed to validate session: %s", e, exc_info=True)
            return None
    
    async def destroy_session(self, request: Request, response: Response) -> bool:
        """
        Destroy browser session and clear cookies.
        
        Args:
            request: FastAPI request object
            response: FastAPI response object for clearing cookies
            
        Returns:
            bool: True if session was destroyed, False if no session found
        """
        try:
            session_id = request.cookies.get(SESSION_COOKIE_NAME)
            if not session_id:
                return False
            
            # Get session for logging
            session = await self._get_session(session_id)
            
            # Delete session from Redis
            await self._delete_session(session_id)
            
            # Clear cookies
            self._clear_session_cookies(response)
            
            # Log session destruction
            if session:
                self.logger.info(
                    "Destroyed browser session for user %s",
                    session.username,
                    extra={
                        "user_id": session.user_id,
                        "session_id": session_id
                    }
                )
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to destroy session: %s", e, exc_info=True)
            return False
    
    async def update_oauth2_context(
        self,
        session_id: str,
        oauth2_context: Dict[str, Any]
    ) -> bool:
        """
        Update OAuth2 context for an existing session.
        
        Args:
            session_id: Session identifier
            oauth2_context: OAuth2 context to store
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            session = await self._get_session(session_id)
            if not session:
                return False
            
            # Update OAuth2 context
            session.oauth2_state = oauth2_context.get("state")
            session.oauth2_client_id = oauth2_context.get("client_id")
            session.oauth2_redirect_uri = oauth2_context.get("redirect_uri")
            session.oauth2_scopes = oauth2_context.get("scopes", [])
            
            # Store updated session
            await self._store_session(session)
            
            self.logger.debug(
                "Updated OAuth2 context for session %s",
                session_id,
                extra={
                    "session_id": session_id,
                    "client_id": session.oauth2_client_id,
                    "state": session.oauth2_state
                }
            )
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to update OAuth2 context: %s", e, exc_info=True)
            return False
    
    async def start_cleanup_task(self) -> None:
        """Start the background session cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            return
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("Started session cleanup background task")
    
    async def stop_cleanup_task(self) -> None:
        """Stop the background session cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped session cleanup background task")
    
    # Private methods
    
    def _generate_session_id(self) -> str:
        """Generate a secure session ID."""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(SESSION_ID_LENGTH))
    
    def _generate_csrf_token(self) -> str:
        """Generate a secure CSRF token."""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(CSRF_TOKEN_LENGTH))
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct client IP
        return getattr(request.client, "host", "unknown")
    
    def _create_session_fingerprint(self, ip_address: str, user_agent: str) -> str:
        """Create session fingerprint for security validation."""
        fingerprint_data = f"{ip_address}:{user_agent}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()
    
    def _set_session_cookies(
        self,
        response: Response,
        session_id: str,
        csrf_token: str,
        expires_at: datetime
    ) -> None:
        """Set secure session cookies."""
        # Calculate max_age in seconds
        max_age = int((expires_at - datetime.utcnow()).total_seconds())
        
        # Set session cookie (HTTP-only, Secure, SameSite)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            max_age=max_age,
            httponly=True,
            secure=not settings.DEBUG,  # Use secure cookies in production
            samesite="lax"  # Allow cross-site navigation
        )
        
        # Set CSRF cookie (accessible to JavaScript for forms)
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=csrf_token,
            max_age=max_age,
            httponly=False,  # Accessible to JavaScript
            secure=not settings.DEBUG,
            samesite="lax"
        )
    
    def _clear_session_cookies(self, response: Response) -> None:
        """Clear session cookies."""
        response.delete_cookie(key=SESSION_COOKIE_NAME)
        response.delete_cookie(key=CSRF_COOKIE_NAME)
    
    async def _store_session(self, session: BrowserSession) -> None:
        """Store session in Redis with expiration."""
        session_key = f"{SESSION_PREFIX}{session.session_id}"
        session_data = session.model_dump_json()
        
        # Calculate TTL in seconds
        ttl_seconds = int((session.expires_at - datetime.utcnow()).total_seconds())
        
        # Store in Redis with expiration
        await redis_manager.setex(session_key, ttl_seconds, session_data)
        
        # Also store user session mapping for cleanup
        user_sessions_key = f"oauth2:user_sessions:{session.user_id}"
        await redis_manager.setex(f"{user_sessions_key}:{session.session_id}", ttl_seconds, "1")
    
    async def _get_session(self, session_id: str) -> Optional[BrowserSession]:
        """Get session from Redis."""
        session_key = f"{SESSION_PREFIX}{session_id}"
        session_data = await redis_manager.get(session_key)
        
        if not session_data:
            return None
        
        try:
            return BrowserSession.model_validate_json(session_data)
        except Exception as e:
            self.logger.error("Failed to parse session data: %s", e)
            await self._delete_session(session_id)
            return None
    
    async def _delete_session(self, session_id: str) -> None:
        """Delete session from Redis."""
        session_key = f"{SESSION_PREFIX}{session_id}"
        await redis_manager.delete(session_key)
    
    async def _cleanup_user_sessions(self, user_id: str) -> None:
        """Clean up old sessions for a user, keeping only the most recent ones."""
        try:
            user_sessions_pattern = f"oauth2:user_sessions:{user_id}:*"
            session_keys = await redis_manager.keys(user_sessions_pattern)
            
            if len(session_keys) <= MAX_SESSIONS_PER_USER:
                return
            
            # Get session details for sorting
            sessions_with_time = []
            for key in session_keys:
                session_id = key.split(":")[-1]
                session = await self._get_session(session_id)
                if session:
                    sessions_with_time.append((session.last_accessed_at, session_id))
            
            # Sort by last accessed time (oldest first)
            sessions_with_time.sort(key=lambda x: x[0])
            
            # Remove oldest sessions
            sessions_to_remove = len(sessions_with_time) - MAX_SESSIONS_PER_USER
            for i in range(sessions_to_remove):
                _, session_id = sessions_with_time[i]
                await self._delete_session(session_id)
                await redis_manager.delete(f"oauth2:user_sessions:{user_id}:{session_id}")
            
            self.logger.info(
                "Cleaned up %d old sessions for user %s",
                sessions_to_remove,
                user_id
            )
            
        except Exception as e:
            self.logger.error("Failed to cleanup user sessions: %s", e, exc_info=True)
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions."""
        self._is_cleanup_running = True
        
        try:
            while self._is_cleanup_running:
                try:
                    await self._cleanup_expired_sessions()
                    await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error("Error in session cleanup loop: %s", e, exc_info=True)
                    await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        finally:
            self._is_cleanup_running = False
    
    async def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions from Redis."""
        try:
            # Get all session keys
            session_keys = await redis_manager.keys(f"{SESSION_PREFIX}*")
            
            expired_count = 0
            for session_key in session_keys:
                session_data = await redis_manager.get(session_key)
                if not session_data:
                    continue
                
                try:
                    session = BrowserSession.model_validate_json(session_data)
                    if datetime.utcnow() > session.expires_at:
                        await redis_manager.delete(session_key)
                        # Also clean up user session mapping
                        await redis_manager.delete(f"oauth2:user_sessions:{session.user_id}:{session.session_id}")
                        expired_count += 1
                except Exception as e:
                    # Invalid session data, remove it
                    await redis_manager.delete(session_key)
                    expired_count += 1
            
            if expired_count > 0:
                self.logger.info("Cleaned up %d expired sessions", expired_count)
                
        except Exception as e:
            self.logger.error("Failed to cleanup expired sessions: %s", e, exc_info=True)


# Global session manager instance
session_manager = SessionManager()