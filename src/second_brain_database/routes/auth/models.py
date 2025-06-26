"""Authentication models for user registration, login, and data validation."""
from datetime import datetime
from typing import Optional, List, Any, Dict, TypedDict
import re
from pydantic import BaseModel, Field, EmailStr, field_validator
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Models]")

# Constants for password validation
PASSWORD_MIN_LENGTH: int = 8
USERNAME_MIN_LENGTH: int = 3
USERNAME_MAX_LENGTH: int = 50
PASSWORD_SPECIAL_CHARS: str = r"!@#$%^&*(),.?\":{}|<>"
USERNAME_REGEX: str = r'^[a-zA-Z0-9_-]+$'

class PasswordValidationResult(TypedDict):
    """
    A TypedDict representing the result of a password validation check.

    Attributes:
        valid (bool): Indicates whether the password passed validation.
        reason (str): Provides the reason for validation failure, or an explanatory message.
    """
    valid: bool
    reason: str

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
        password (str): The password to validate.
    Returns:
        bool: True if password meets all requirements, False otherwise.
    Side-effects:
        Logs warnings for each failed requirement.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
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
    if not re.search(f"[{PASSWORD_SPECIAL_CHARS}]", password):
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
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        description="Username must be 3-50 characters"
    )
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
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
        Args:
            v (str): The username to validate.
        Returns:
            str: The validated username in lowercase.
        Raises:
            ValueError: If username is invalid.
        Side-effects:
            Logs error if username is invalid.
        """
        if not re.match(USERNAME_REGEX, v):
            logger.error("Invalid username: %s", v)
            raise ValueError('Username must contain only alphanumeric characters, dashes, and underscores (no Unicode)')
        return v.lower()

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """
        Validate and normalize email address.
        Args:
            v (str): The email to validate.
        Returns:
            str: The validated email in lowercase.
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
    two_fa_enabled: bool = False
    totp_secret: Optional[str] = None
    backup_codes: Optional[List[str]] = None
    backup_codes_used: Optional[List[int]] = None
    reset_blocklist: Optional[List[str]] = Field(default_factory=list)
    reset_whitelist: Optional[List[str]] = Field(default_factory=list)
    # Deprecated/legacy fields are documented in the docstring above.

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
        min_length=PASSWORD_MIN_LENGTH,
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
    code: str

class TwoFAStatus(BaseModel):
    """
    Two-factor authentication status response model.

    Indicates whether 2FA is enabled and lists the enabled methods.
    If backup_codes is present, these are the one-time backup codes shown only after first successful 2FA verification.
    """
    enabled: bool
    methods: Optional[List[str]] = Field(default_factory=list)
    pending: Optional[bool] = False
    backup_codes: Optional[List[str]] = None

class TwoFASetupResponse(BaseModel):
    """
    Response model for 2FA setup, including secret and provisioning URI for TOTP.
    """
    enabled: bool
    methods: Optional[List[str]] = Field(default_factory=list)
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
    def check_username_or_email(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure that either username or email is provided for login.
        Args:
            values (dict): The input values.
        Returns:
            dict: The validated input values.
        Raises:
            ValueError: If neither username nor email is provided.
        """
        if not values.get('username') and not values.get('email'):
            logger.error("Login validation failed: missing username and email")
            raise ValueError('Either username or email must be provided for login.')
        return values

class LoginLog(BaseModel):
    """
    Model for logging login attempts.
    """
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    username: str
    email: Optional[str] = None
    outcome: str  # 'success' or 'failure'
    reason: Optional[str] = None
    mfa_status: Optional[bool] = None

class RegistrationLog(BaseModel):
    """
    Model for logging registration attempts.
    """
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    username: str
    email: str
    outcome: str  # 'success' or 'failure:reason'
    reason: Optional[str] = None
    plan: Optional[str] = None
    role: Optional[str] = None
