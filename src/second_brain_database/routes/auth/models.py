"""Authentication models for user registration, login, and data validation."""
from datetime import datetime
from typing import Optional, List
import re
from pydantic import BaseModel, Field, EmailStr, field_validator

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
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
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
    """
    enabled: bool
    methods: Optional[list] = []
    pending: Optional[bool] = False  # Indicates if setup is pending verification

class TwoFASetupResponse(BaseModel):
    """
    Response model for 2FA setup, including secret and provisioning URI for TOTP.
    """
    enabled: bool
    methods: Optional[list] = []
    totp_secret: Optional[str] = None
    provisioning_uri: Optional[str] = None
    qr_code_url: Optional[str] = None
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