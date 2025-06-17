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
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
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
    created_at: datetime
    is_active: bool = True
    failed_login_attempts: int = 0
    last_login: Optional[datetime] = None
    plan: Optional[str] = "free"
    team: Optional[List[str]] = Field(default_factory=list)
    role: Optional[str] = "user"
    is_verified: bool = False
    # 2FA fields
    two_fa_enabled: bool = False
    two_fa_methods: Optional[List[str]] = Field(default_factory=list, description="Enabled 2FA methods: 'totp', 'email', 'passkey'")
    totp_secret: Optional[str] = None
    passkeys: Optional[list] = Field(default_factory=list, description="List of registered passkeys (public keys, credential IDs, etc.)")
    email_otp_secret: Optional[str] = None

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

class LoginRequest(BaseModel):
    """
    Login request model supporting 2FA fields.
    Accepts username, password, and optional 2FA code/method.
    """
    username: str
    password: str
    two_fa_code: Optional[str] = None
    two_fa_method: Optional[str] = None
