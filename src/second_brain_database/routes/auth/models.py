"""Authentication models for user registration, login, and data validation."""

from datetime import datetime
import re
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, EmailStr, Field, field_validator

from second_brain_database.docs.models import BaseDocumentedModel
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Models]")

# Constants for password validation
PASSWORD_MIN_LENGTH: int = 8
USERNAME_MIN_LENGTH: int = 3
USERNAME_MAX_LENGTH: int = 50
PASSWORD_SPECIAL_CHARS: str = r"!@#$%^&*(),.?\":{}|<>"
USERNAME_REGEX: str = r"^[a-zA-Z0-9_-]+$"


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


class UserIn(BaseDocumentedModel):
    """
    User input model for registration.

    Validates username format, email format, and ensures password meets
    minimum requirements. Username is automatically converted to lowercase
    for consistency.

    **Validation Rules:**
    - Username: 3-50 characters, alphanumeric with dashes/underscores only
    - Email: Valid email format, automatically converted to lowercase
    - Password: Minimum 8 characters with strength requirements
    """

    username: str = Field(
        ...,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        description="Unique username for the account. Must be 3-50 characters, containing only letters, numbers, dashes, and underscores. Will be converted to lowercase.",
        example="john_doe",
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address for account verification and communication. Will be converted to lowercase.",
        example="john.doe@example.com",
    )
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        description="Account password. Must be at least 8 characters and include uppercase, lowercase, number, and special character.",
        example="SecurePassword123!",
    )
    plan: Optional[str] = Field(
        default="free", description="User subscription plan. Defaults to 'free' for new registrations.", example="free"
    )
    team: Optional[List[str]] = Field(
        default_factory=list,
        description="List of team identifiers the user belongs to. Empty by default.",
        example=["team_alpha", "project_beta"],
    )
    role: Optional[str] = Field(
        default="user", description="User role in the system. Defaults to 'user' for standard accounts.", example="user"
    )
    is_verified: bool = Field(
        default=False,
        description="Email verification status. Always false for new registrations until email is verified.",
        example=False,
    )
    client_side_encryption: bool = Field(
        default=False,
        description="Whether the user wants to enable client-side encryption for their data.",
        example=False,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "email": "john.doe@example.com",
                "password": "SecurePassword123!",
                "plan": "free",
                "team": [],
                "role": "user",
                "is_verified": False,
                "client_side_encryption": False,
            }
        }
    }

    @field_validator("username")
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
            raise ValueError("Username must contain only alphanumeric characters, dashes, and underscores (no Unicode)")
        return v.lower()

    @field_validator("email")
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


class UserOut(BaseDocumentedModel):
    """
    User output model for API responses.

    Contains safe user information without sensitive data like passwords.
    Used in API responses to provide user profile information securely.

    **Security Note:** This model excludes sensitive fields like passwords,
    2FA secrets, and internal security tracking data.
    """

    username: str = Field(..., description="The user's unique username, always in lowercase", example="john_doe")
    email: str = Field(
        ..., description="The user's email address, used for communication and login", example="john.doe@example.com"
    )
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the user account was created",
        example="2024-01-01T10:00:00Z",
    )
    last_login: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of the user's last successful login",
        example="2024-01-01T15:30:00Z",
    )
    is_active: bool = Field(
        default=True, description="Whether the user account is active and can be used for login", example=True
    )
    plan: Optional[str] = Field(default="free", description="The user's current subscription plan", example="free")
    team: Optional[List[str]] = Field(
        default_factory=list,
        description="List of team identifiers the user belongs to",
        example=["team_alpha", "project_beta"],
    )
    role: Optional[str] = Field(
        default="user", description="The user's role in the system (user, admin, etc.)", example="user"
    )
    is_verified: bool = Field(
        default=False, description="Whether the user's email address has been verified", example=True
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "email": "john.doe@example.com",
                "created_at": "2024-01-01T10:00:00Z",
                "last_login": "2024-01-01T15:30:00Z",
                "is_active": True,
                "plan": "free",
                "team": ["team_alpha"],
                "role": "user",
                "is_verified": True,
            }
        }
    }


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
    last_login: Optional[datetime] = Field(
        default_factory=datetime.utcnow, description="UTC time when the user last logged in"
    )
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


class Token(BaseDocumentedModel):
    """
    JWT token response model.

    Contains the access token and token type for authentication.
    Returned after successful login, registration, or token refresh operations.

    **Usage:** Include the access_token in the Authorization header as:
    `Authorization: Bearer <access_token>`

    **Security:** Tokens expire after 30 minutes by default and should be refreshed
    using the `/auth/refresh` endpoint before expiration.
    """

    access_token: str = Field(
        ...,
        description="JWT access token for API authentication. Include in Authorization header as 'Bearer <token>'",
        example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsImV4cCI6MTY0MDk5NTIwMH0.example_signature",
    )
    token_type: str = Field(
        default="bearer", description="Token type, always 'bearer' for JWT tokens", example="bearer"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsImV4cCI6MTY0MDk5NTIwMH0.example_signature",
                "token_type": "bearer",
            }
        }
    }


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
        ..., min_length=PASSWORD_MIN_LENGTH, description="New password must be at least 8 characters"
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


class LoginRequest(BaseDocumentedModel):
    """
    Login request model supporting 2FA fields.

    Accepts either username or email (at least one required), password, and optional 2FA code/method.
    Supports both standard login and two-factor authentication flows.

    **Authentication Flow:**
    1. Standard login: Provide username/email and password
    2. 2FA login: Include two_fa_code and two_fa_method after initial attempt

    **Supported 2FA Methods:** totp, backup
    """

    username: Optional[str] = Field(
        None, description="Username for login. Either username or email must be provided.", example="john_doe"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Email address for login. Either username or email must be provided.",
        example="john.doe@example.com",
    )
    password: str = Field(..., description="User's password for authentication", example="SecurePassword123!")
    two_fa_code: Optional[str] = Field(
        None,
        description="Two-factor authentication code. Required if 2FA is enabled for the account.",
        example="123456",
    )
    two_fa_method: Optional[str] = Field(
        None,
        description="Two-factor authentication method. Options: 'totp' (authenticator app), 'backup' (backup codes)",
        example="totp",
    )
    client_side_encryption: bool = Field(
        default=False, description="Whether to enable client-side encryption for this session", example=False
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Standard Login",
                    "summary": "Login with username and password",
                    "value": {
                        "username": "john_doe",
                        "password": "SecurePassword123!",
                        "client_side_encryption": False,
                    },
                },
                {
                    "name": "Email Login",
                    "summary": "Login with email and password",
                    "value": {
                        "email": "john.doe@example.com",
                        "password": "SecurePassword123!",
                        "client_side_encryption": False,
                    },
                },
                {
                    "name": "2FA Login",
                    "summary": "Login with 2FA authentication",
                    "value": {
                        "username": "john_doe",
                        "password": "SecurePassword123!",
                        "two_fa_code": "123456",
                        "two_fa_method": "totp",
                        "client_side_encryption": False,
                    },
                },
            ]
        }
    }

    @classmethod
    def model_validate(cls, data):
        # Pydantic v2: use model_validate for cross-field validation
        obj = super().model_validate(data)
        if not obj.username and not obj.email:
            raise ValueError("Either username or email must be provided.")
        return obj


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


# Permanent Token Models


class PermanentTokenRequest(BaseDocumentedModel):
    """
    Request model for creating a new permanent token.

    Permanent tokens provide long-lived authentication for integrations, automation,
    and server-to-server communication. They don't expire unless manually revoked.

    **Use Cases:**
    - CI/CD pipeline authentication
    - Third-party application integrations
    - Automated scripts and background jobs
    - Server-to-server communication

    **Security:** Tokens are generated with cryptographically secure randomness
    and stored as SHA-256 hashes in the database.
    """

    description: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional description to identify the token's purpose. Helps with token management and auditing.",
        example="CI/CD Pipeline Token for GitHub Actions",
    )
    ip_restrictions: Optional[List[str]] = Field(
        None,
        description="Optional list of IP addresses or CIDR blocks that can use this token. Leave empty for no restrictions.",
        example=["192.168.1.0/24", "10.0.0.0/8"],
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Optional expiration date for the token. If not provided, token will not expire.",
        example="2024-12-31T23:59:59Z",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "CI/CD Token",
                    "summary": "Token for continuous integration",
                    "value": {
                        "description": "GitHub Actions CI/CD Pipeline",
                        "ip_restrictions": ["192.30.252.0/22", "185.199.108.0/22"],
                        "expires_at": None,
                    },
                },
                {
                    "name": "Integration Token",
                    "summary": "Token for third-party integration",
                    "value": {
                        "description": "Slack Bot Integration",
                        "ip_restrictions": [],
                        "expires_at": "2024-12-31T23:59:59Z",
                    },
                },
                {
                    "name": "Development Token",
                    "summary": "Token for local development",
                    "value": {
                        "description": "Local Development Environment",
                        "ip_restrictions": ["127.0.0.1/32", "192.168.1.0/24"],
                        "expires_at": "2024-06-30T23:59:59Z",
                    },
                },
            ]
        }
    }


class PermanentTokenResponse(BaseDocumentedModel):
    """
    Response model for permanent token creation.

    Contains the actual token (only returned once) and metadata.

    **IMPORTANT SECURITY NOTE:** The token value is only returned once during creation.
    Store it securely as it cannot be retrieved again. If lost, you must create a new token.

    **Token Format:** Permanent tokens start with 'sbd_permanent_' followed by a secure random string.
    """

    token: str = Field(
        ...,
        description="The permanent API token. Store this securely - it will not be shown again!",
        example="sbd_permanent_1234567890abcdef1234567890abcdef1234567890abcdef",
    )
    token_id: str = Field(
        ...,
        description="Unique identifier for the token, used for management operations",
        example="pt_1234567890abcdef",
    )
    created_at: datetime = Field(
        ..., description="UTC timestamp when the token was created", example="2024-01-01T12:00:00Z"
    )
    description: Optional[str] = Field(
        None,
        description="Description provided during token creation",
        example="CI/CD Pipeline Token for GitHub Actions",
    )
    expires_at: Optional[datetime] = Field(
        None, description="UTC timestamp when the token expires, or null if it never expires", example=None
    )
    ip_restrictions: Optional[List[str]] = Field(
        None,
        description="List of IP addresses or CIDR blocks that can use this token",
        example=["192.168.1.0/24", "10.0.0.0/8"],
    )
    last_used_at: Optional[datetime] = Field(
        None, description="UTC timestamp when the token was last used (null for new tokens)", example=None
    )
    usage_count: int = Field(
        default=0, description="Number of times the token has been used for authentication", example=0
    )
    is_revoked: bool = Field(default=False, description="Whether the token has been revoked", example=False)

    model_config = {
        "json_schema_extra": {
            "example": {
                "token": "sbd_permanent_1234567890abcdef1234567890abcdef1234567890abcdef",
                "token_id": "pt_1234567890abcdef",
                "created_at": "2024-01-01T12:00:00Z",
                "description": "CI/CD Pipeline Token for GitHub Actions",
                "expires_at": None,
                "ip_restrictions": ["192.30.252.0/22"],
                "last_used_at": None,
                "usage_count": 0,
                "is_revoked": False,
            }
        }
    }


class PermanentTokenInfo(BaseDocumentedModel):
    """
    Model for permanent token metadata (without the actual token).

    Used for listing tokens and displaying token information.
    This model provides safe token information without exposing the actual token value.

    **Security:** The actual token value is never included in this model for security reasons.
    """

    token_id: str = Field(
        ...,
        description="Unique identifier for the token, used for management operations like revocation",
        example="pt_1234567890abcdef",
    )
    description: Optional[str] = Field(
        None,
        description="User-provided description to identify the token's purpose",
        example="CI/CD Pipeline Token for GitHub Actions",
    )
    created_at: datetime = Field(
        ..., description="UTC timestamp when the token was created", example="2024-01-01T12:00:00Z"
    )
    last_used_at: Optional[datetime] = Field(
        None,
        description="UTC timestamp when the token was last used for authentication, or null if never used",
        example="2024-01-01T15:30:00Z",
    )
    usage_count: int = Field(
        default=0, description="Total number of times this token has been used for authentication", example=42
    )
    expires_at: Optional[datetime] = Field(
        None, description="UTC timestamp when the token expires, or null if it never expires", example=None
    )
    ip_restrictions: Optional[List[str]] = Field(
        None,
        description="List of IP addresses or CIDR blocks that can use this token",
        example=["192.168.1.0/24", "10.0.0.0/8"],
    )
    is_revoked: bool = Field(
        default=False, description="Whether the token has been revoked and can no longer be used", example=False
    )
    revoked_at: Optional[datetime] = Field(
        None, description="UTC timestamp when the token was revoked, or null if still active", example=None
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Active Token",
                    "summary": "An active permanent token with usage history",
                    "value": {
                        "token_id": "pt_1234567890abcdef",
                        "description": "CI/CD Pipeline Token for GitHub Actions",
                        "created_at": "2024-01-01T12:00:00Z",
                        "last_used_at": "2024-01-01T15:30:00Z",
                        "usage_count": 42,
                        "expires_at": None,
                        "ip_restrictions": ["192.30.252.0/22"],
                        "is_revoked": False,
                        "revoked_at": None,
                    },
                },
                {
                    "name": "Revoked Token",
                    "summary": "A revoked permanent token",
                    "value": {
                        "token_id": "pt_abcdef1234567890",
                        "description": "Old Development Token",
                        "created_at": "2023-12-01T10:00:00Z",
                        "last_used_at": "2023-12-15T14:20:00Z",
                        "usage_count": 15,
                        "expires_at": None,
                        "ip_restrictions": ["127.0.0.1/32"],
                        "is_revoked": True,
                        "revoked_at": "2023-12-20T09:00:00Z",
                    },
                },
            ]
        }
    }


class PermanentTokenListResponse(BaseDocumentedModel):
    """
    Response model for listing permanent tokens.

    Contains array of token metadata without actual token values.
    Provides comprehensive overview of all tokens for a user including usage statistics.

    **Security:** Token values are never included in list responses for security reasons.
    """

    tokens: List[PermanentTokenInfo] = Field(
        default_factory=list,
        description="List of permanent tokens for the user, including both active and revoked tokens",
    )
    total_count: int = Field(default=0, description="Total number of tokens (active + revoked)", example=5)
    active_count: int = Field(default=0, description="Number of active (non-revoked) tokens", example=3)
    revoked_count: int = Field(default=0, description="Number of revoked tokens", example=2)

    model_config = {
        "json_schema_extra": {
            "example": {
                "tokens": [
                    {
                        "token_id": "pt_1234567890abcdef",
                        "description": "CI/CD Pipeline Token for GitHub Actions",
                        "created_at": "2024-01-01T12:00:00Z",
                        "last_used_at": "2024-01-01T15:30:00Z",
                        "usage_count": 42,
                        "expires_at": None,
                        "ip_restrictions": ["192.30.252.0/22"],
                        "is_revoked": False,
                        "revoked_at": None,
                    },
                    {
                        "token_id": "pt_abcdef1234567890",
                        "description": "Mobile App Integration",
                        "created_at": "2024-01-02T09:00:00Z",
                        "last_used_at": "2024-01-02T10:15:00Z",
                        "usage_count": 15,
                        "expires_at": "2024-12-31T23:59:59Z",
                        "ip_restrictions": [],
                        "is_revoked": False,
                        "revoked_at": None,
                    },
                ],
                "total_count": 2,
                "active_count": 2,
                "revoked_count": 0,
            }
        }
    }


class PermanentTokenCacheData(BaseModel):
    """
    Model for data stored in Redis cache.

    Contains user metadata for fast token validation.
    """

    user_id: str = Field(..., description="String representation of user ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="User email")
    role: str = Field(default="user", description="User role")
    is_verified: bool = Field(default=False, description="Email verification status")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")


class TokenRevocationResponse(BaseDocumentedModel):
    """
    Response model for token revocation.

    Confirms successful token revocation and provides revocation details.
    Once a token is revoked, it cannot be used for authentication and cannot be restored.

    **Security:** Revoked tokens are immediately invalidated and removed from cache.
    """

    message: str = Field(
        ..., description="Confirmation message indicating successful revocation", example="Token revoked successfully"
    )
    token_id: str = Field(..., description="Unique identifier of the revoked token", example="pt_1234567890abcdef")
    revoked_at: datetime = Field(
        ..., description="UTC timestamp when the token was revoked", example="2024-01-01T16:00:00Z"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Token revoked successfully",
                "token_id": "pt_1234567890abcdef",
                "revoked_at": "2024-01-01T16:00:00Z",
            }
        }
    }


class PermanentTokenDocument(BaseModel):
    """
    Database document model for permanent tokens collection.

    Represents the complete document structure stored in MongoDB.
    """

    user_id: str = Field(..., description="ObjectId of the token owner")
    token_id: str = Field(..., description="Unique token identifier for management operations")
    token_hash: str = Field(..., description="SHA-256 hash of the token")
    description: Optional[str] = Field(None, max_length=255, description="Optional token description")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Token creation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    is_revoked: bool = Field(default=False, description="Revocation status")
    revoked_at: Optional[datetime] = Field(None, description="Revocation timestamp")


# WebAuthn support removed


class AuthMethodsResponse(BaseDocumentedModel):
    """
    Response model for authentication methods query.

    Contains information about available authentication methods,
    user preferences, and recent authentication activity.

    **Fields:**
    - available_methods: List of authentication methods available to the user
    - preferred_method: User's preferred authentication method
    - has_password: Whether the user has a password set
    - recent_auth_methods: List of recently used authentication methods
    - last_auth_method: The most recently used authentication method
    """

    available_methods: List[str] = Field(
        default_factory=list,
        description="List of authentication methods available to the user",
        example=["password"],
    )
    preferred_method: Optional[str] = Field(
        None,
        description="User's preferred authentication method",
        example="password",
    )
    has_password: bool = Field(
        default=True,
        description="Whether the user has a password set",
        example=True,
    )
    recent_auth_methods: List[str] = Field(
        default_factory=list,
        description="List of recently used authentication methods",
        example=["password", "password"],
    )
    last_auth_method: Optional[str] = Field(
        None,
        description="The most recently used authentication method",
        example="password",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "available_methods": ["password"],
                "preferred_method": "password",
                "has_password": True,
                "recent_auth_methods": ["password", "password"],
                "last_auth_method": "password",
            }
        }
    }


class AuthPreferenceResponse(BaseDocumentedModel):
    """
    Response model for authentication preference updates.

    Confirms successful update of user's preferred authentication method.

    **Fields:**
    - message: Confirmation message
    - preferred_method: The newly set preferred authentication method
    """

    message: str = Field(
        ...,
        description="Confirmation message indicating successful preference update",
        example="Authentication preference updated successfully",
    )
    preferred_method: str = Field(
        ...,
        description="The newly set preferred authentication method",
        example="password",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Authentication preference updated successfully",
                "preferred_method": "password",
            }
        }
    }


class AuthFallbackResponse(BaseDocumentedModel):
    """
    Response model for authentication fallback options.

    Provides information about alternative authentication methods
    available when a primary method fails.

    **Fields:**
    - fallback_available: Whether fallback options are available
    - available_fallbacks: List of available fallback authentication methods
    - recommended_fallback: Recommended fallback method to try
    """

    fallback_available: bool = Field(
        default=False,
        description="Whether fallback authentication options are available",
        example=True,
    )
    available_fallbacks: List[str] = Field(
        default_factory=list,
        description="List of available fallback authentication methods",
        example=["password"],
    )
    recommended_fallback: Optional[str] = Field(
        None,
        description="Recommended fallback authentication method",
        example="password",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "fallback_available": True,
                "available_fallbacks": ["password"],
                "recommended_fallback": "password",
            }
        }
    }



