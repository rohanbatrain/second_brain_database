"""Authentication models for user registration, login, and data validation."""
from datetime import datetime
from typing import Optional, List
import re
from pydantic import BaseModel, Field, EmailStr, field_validator
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Models]")

def validate_password_strength(password: str) -> bool:
    """
    Validate password strength requirements.

    Password must contain:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: The password to validate

    Returns:
        bool: True if password meets all requirements, False otherwise
    """
    if len(password) < 8:
        logger.warning("Password validation failed: too short")
        return False
    if not re.search(r"[A-Z]", password):
        logger.warning("Password validation failed: missing uppercase letter")
        return False
    if not re.search(r"[a-z]", password):
        logger.warning("Password validation failed: missing lowercase letter")
        return False
    if not re.search(r"\d", password):
        logger.warning("Password validation failed: missing digit")
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        logger.warning("Password validation failed: missing special character")
        return False
    return True

class UserIn(BaseModel):
    """
    User input model for registration.

    Validates username format, email format, and ensures password meets
    minimum requirements. Username is automatically converted to lowercase
    for consistency.
    """
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username must be 3-50 characters"
    )
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters"
    )
    plan: Optional[str] = "free"
    team: Optional[List[str]] = Field(default_factory=list)
    role: Optional[str] = "user"
    is_verified: bool = False
    client_side_encryption: bool = False

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Validate username contains only alphanumeric characters, dashes, and underscores. Unicode is not allowed.
        """
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            logger.error(f"Invalid username: {v}")
            raise ValueError('Username must contain only alphanumeric characters, dashes, and underscores (no Unicode)')
        return v.lower()

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """
        Validate and normalize email address.

        Args:
            v: The email to validate

        Returns:
            str: The validated email in lowercase
        """
        return v.lower()

class UserOut(BaseModel):
    """
    User output model for API responses.

    Contains safe user information without sensitive data like passwords.
    """
    username: str
    email: str
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="UTC time when the user was created")
    last_login: Optional[datetime] = Field(default_factory=datetime.utcnow, description="UTC time when the user last logged in")
    is_active: bool = True
    plan: Optional[str] = "free"
    team: Optional[List[str]] = Field(default_factory=list)
    role: Optional[str] = "user"
    is_verified: bool = False

class UserInDB(BaseModel):
    """
    User database model representing the complete user document.

    Contains all user fields including sensitive data like hashed passwords
    and security-related fields for authentication tracking.
    """
    username: str
    email: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow, description="UTC time when the user was created")
    is_active: bool = True
    failed_login_attempts: int = 0
    last_login: Optional[datetime] = Field(default_factory=datetime.utcnow, description="UTC time when the user last logged in")
    plan: Optional[str] = "free"
    team: Optional[List[str]] = Field(default_factory=list)
    role: Optional[str] = "user"
    is_verified: bool = False
    # 2FA fields (TOTP only)
    two_fa_enabled: bool = False
    totp_secret: Optional[str] = None
    backup_codes: Optional[List[str]] = None
    backup_codes_used: Optional[List[int]] = None
    reset_blocklist: Optional[list] = Field(default_factory=list)
    reset_whitelist: Optional[list] = Field(default_factory=list)
    # The following legacy fields are deprecated and should not be used:
    # abuse_flags: Optional[dict] = Field(default_factory=dict)
    # abuse_history: Optional[list] = Field(default_factory=list)
    #
    # All abuse events and flags are now tracked in the reset_abuse_events collection (MongoDB)
    # and managed via admin endpoints and service logic. These fields are retained for backward compatibility only.
    #
    # Remove or ignore these fields in new code. Use the new event-based system for all abuse review and escalation.
    """
    ---
    Password reset abuse prevention fields (MongoDB persistence):
    - reset_blocklist: List of IPs (as strings) currently blocked from password reset for this user.
      Example: ["127.0.0.1", "203.0.113.5"]
    - reset_whitelist: List of IPs (as strings) currently whitelisted for password reset for this user.
      Example: ["10.0.0.2"]
    ---
    To add an event (example mongosh):
      db.users.updateOne({email: "user@example.com"}, {$push: {abuse_history: {timestamp: new Date().toISOString(), ip: "127.0.0.1", reason: "too many reset attempts", action: "block"}}})
    To query for repeated violators (strict, in Python):
      # See service.py for a helper function to check for N+ abuse events from different IPs in a short window.
    ---
    These fields are stored directly in the MongoDB user document. You can edit them using any MongoDB admin tool (e.g., MongoDB Compass, mongosh):
    Example update (add an IP to blocklist):
      db.users.updateOne({email: "user@example.com"}, {$addToSet: {reset_blocklist: "203.0.113.5"}})
    Example update (remove an IP from whitelist):
      db.users.updateOne({email: "user@example.com"}, {$pull: {reset_whitelist: "10.0.0.2"}})
    Example update (set abuse flag):
      db.users.updateOne({email: "user@example.com"}, {$set: {"abuse_flags.127.0.0.1": {blocked_until: "2025-06-24T12:00:00Z", reason: "manual block"}}})
    ---
    These fields are periodically synced to Redis for fast in-memory checks. MongoDB is the source of truth.
    """

class Token(BaseModel):
    """
    JWT token response model.

    Contains the access token and token type for authentication.
    """
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """
    Token payload data extracted from JWT.

    Used internally for token validation and user identification.
    """
    username: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    """
    Password change request model.

    Contains the old password for verification and new password to set.
    New password must meet the same strength requirements as registration.
    """
    old_password: str
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password must be at least 8 characters"
    )

class TwoFASetupRequest(BaseModel):
    """
    Two-factor authentication setup request model.

    Specifies the method to enable for 2FA.
    """
    method: str  # 'totp', 'email', or 'passkey'

class TwoFAVerifyRequest(BaseModel):
    """
    Two-factor authentication verification request model.

    Contains the method and code for verification.
    """
    method: str
    code: str  # For TOTP or email OTP; for passkey, this could be a challenge response

class TwoFAStatus(BaseModel):
    """
    Two-factor authentication status response model.

    Indicates whether 2FA is enabled and lists the enabled methods.
    If backup_codes is present, these are the one-time backup codes shown only after first successful 2FA verification.
    """
    enabled: bool
    methods: Optional[list] = []
    pending: Optional[bool] = False  # Indicates if setup is pending verification
    backup_codes: Optional[list] = None  # Only present after first successful 2FA verification

class TwoFASetupResponse(BaseModel):
    """
    Response model for 2FA setup, including secret and provisioning URI for TOTP.
    """
    enabled: bool
    methods: Optional[list] = []
    totp_secret: Optional[str] = None
    provisioning_uri: Optional[str] = None
    qr_code_data: Optional[str] = None
    backup_codes: Optional[List[str]] = None

class LoginRequest(BaseModel):
    """
    Login request model supporting 2FA fields.
    Accepts either username or email (at least one required), password, and optional 2FA code/method.
    """
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str
    two_fa_code: Optional[str] = None
    two_fa_method: Optional[str] = None
    client_side_encryption: bool = False

    @classmethod
    @field_validator('*', mode='before')
    def check_username_or_email(cls, values):
        if not values.get('username') and not values.get('email'):
            raise ValueError('Either username or email must be provided for login.')
        return values

class LoginLog(BaseModel):
    """
    Model for logging login attempts.
    """
    timestamp: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    username: str
    email: str | None = None
    outcome: str  # 'success' or 'failure'
    reason: str | None = None
    mfa_status: bool | None = None

class RegistrationLog(BaseModel):
    """
    Model for logging registration attempts.
    """
    timestamp: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    username: str
    email: str
    outcome: str  # 'success' or 'failure:reason'
    reason: str | None = None
    plan: str | None = None
    role: str | None = None