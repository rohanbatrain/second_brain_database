"""Authentication models for user registration, login, and data validation."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, EmailStr

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

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Validate username contains only alphanumeric characters, dashes, and underscores.

        Args:
            v: The username to validate

        Returns:
            str: The validated username in lowercase

        Raises:
            ValueError: If username contains invalid characters
        """
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username must contain only alphanumeric characters, dashes, and underscores')
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
