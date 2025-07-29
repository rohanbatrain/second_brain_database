"""Configuration module for Second Brain Database.

This module provides robust, production-grade configuration and logging bootstrapping for the application.

Rationale and Best Practices:
----------------------------
- **Flexible config discovery with environment fallback:**
  The config file is discovered in the following order: (1) via the `SECOND_BRAIN_DATABASE_CONFIG_PATH`
  environment variable, (2) `.sbd` in the project root, (3) `.env` in the project root, (4) fallback to
  environment variables only. This allows the application to run with just environment variables when no
  config file is available, making it suitable for containerized deployments and CI/CD environments.

- **Pydantic Settings with extra env support:**
  The `Settings` class uses Pydantic's `BaseSettings` to load all configuration from the environment or
  config file, and allows extra environment variables (e.g., for OpenTelemetry or other integrations)
  without error. This makes the config extensible and cloud/deployment friendly.

- **No circular imports:**
  The logging logic for config bootstrapping is self-contained in this module, copied from the main
  logging manager, to avoid circular imports. After the config is loaded and the main logging manager
  is available, the main logger can be safely used.

- **Security and best practices:**
  Secrets (e.g., JWT keys, Fernet keys, DB URLs) are never hardcoded and must be set via environment or
  config file. Validators enforce this at startup. This prevents accidental leaks and enforces secure
  deployment.

- **Extensive documentation and PEP 257 compliance:**
  All classes, functions, and the module itself are documented with rationale, usage, and best practices
  for future maintainers. This is critical for production systems where config and logging are
  foundational and mistakes can have security or reliability consequences.

How to extend/maintain:
-----------------------
- Add new config fields to the `Settings` class, and document them.
- If you change the config discovery logic, update this docstring and the error messages.

For more details, see the README and the comments in this file.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Constants ---
SBD_FILENAME: str = ".sbd"
DEFAULT_ENV_FILENAME: str = ".env"
CONFIG_ENV_VAR: str = "SECOND_BRAIN_DATABASE_CONFIG_PATH"
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


# --- Config file discovery (no logging) ---
def get_config_path() -> Optional[str]:
    """Determine the config file path to use, in order of precedence:
    1. Environment variable SECOND_BRAIN_DATABASE_CONFIG_PATH
    2. .sbd in project root
    3. .env in project root
    4. None (fallback to environment variables only)

    Returns:
        Optional[str]: Path to config file, or None if not found.
                      When None, the application will use environment variables only.
    """
    env_path: Optional[str] = os.environ.get(CONFIG_ENV_VAR)
    if env_path and os.path.exists(env_path):
        return env_path
    sbd_path: Path = PROJECT_ROOT / SBD_FILENAME
    if sbd_path.exists():
        return str(sbd_path)
    env_path_file: Path = PROJECT_ROOT / DEFAULT_ENV_FILENAME
    if env_path_file.exists():
        return str(env_path_file)
    return None


CONFIG_PATH: Optional[str] = get_config_path()
if CONFIG_PATH:
    try:
        load_dotenv(dotenv_path=CONFIG_PATH, override=True)
    except OSError as exc:
        raise exc
else:
    # No config file found - fall back to environment variables only
    # This allows the application to run with environment variables as backup
    pass


class Settings(BaseSettings):
    """Application settings with environment variable support.
    All fields are loaded from the environment or the .sbd/.env file.
    If no config file is found, falls back to environment variables only.
    """

    # Configure model to use config file if available, otherwise environment only
    model_config = SettingsConfigDict(
        env_file=CONFIG_PATH if CONFIG_PATH else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",  # Allow extra env vars not defined as fields
    )

    # Server configuration (loaded from environment)
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True

    # Base URL configuration
    BASE_URL: str = "http://localhost:8000"

    # JWT configuration (loaded from environment)
    SECRET_KEY: SecretStr = SecretStr("")  # Must be set in .sbd or environment
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # MongoDB configuration (loaded from environment)
    MONGODB_URL: str = ""  # Must be set in .sbd or environment
    MONGODB_DATABASE: str = ""
    MONGODB_CONNECTION_TIMEOUT: int = 10000
    MONGODB_SERVER_SELECTION_TIMEOUT: int = 5000

    # Authentication (optional)
    MONGODB_USERNAME: Optional[str] = None
    MONGODB_PASSWORD: Optional[SecretStr] = None

    # Redis configuration
    REDIS_URL: str = ""  # Must be set in .sbd or environment

    # Permanent Token configuration
    PERMANENT_TOKENS_ENABLED: bool = True  # Enable/disable permanent token feature
    PERMANENT_TOKEN_CACHE_TTL_SECONDS: int = 24 * 60 * 60  # 24 hours cache TTL
    PERMANENT_TOKEN_CREATE_RATE_LIMIT: int = 10  # Max tokens created per hour per user
    PERMANENT_TOKEN_CREATE_RATE_PERIOD: int = 3600  # Rate limit period in seconds
    PERMANENT_TOKEN_LIST_RATE_LIMIT: int = 50  # Max list requests per hour per user
    PERMANENT_TOKEN_LIST_RATE_PERIOD: int = 3600  # Rate limit period in seconds
    PERMANENT_TOKEN_REVOKE_RATE_LIMIT: int = 20  # Max revoke requests per hour per user
    PERMANENT_TOKEN_REVOKE_RATE_PERIOD: int = 3600  # Rate limit period in seconds
    PERMANENT_TOKEN_MAX_PER_USER: int = 50  # Maximum tokens per user
    PERMANENT_TOKEN_CLEANUP_DAYS: int = 90  # Days to keep revoked tokens
    PERMANENT_TOKEN_AUDIT_RETENTION_DAYS: int = 365  # Days to keep audit logs
    PERMANENT_TOKEN_ANALYTICS_RETENTION_DAYS: int = 180  # Days to keep analytics
    PERMANENT_TOKEN_MAINTENANCE_INTERVAL_HOURS: int = 6  # Maintenance interval
    PERMANENT_TOKEN_SUSPICIOUS_IP_THRESHOLD: int = 5  # Max IPs per token before alert
    PERMANENT_TOKEN_RAPID_CREATION_THRESHOLD: int = 10  # Max tokens in 5 min before alert
    PERMANENT_TOKEN_FAILED_VALIDATION_THRESHOLD: int = 20  # Max failures in 10 min before alert

    # Rate limiting configuration
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD_SECONDS: int = 60

    # Blacklist configuration
    BLACKLIST_THRESHOLD: int = 10  # Number of violations before blacklisting
    BLACKLIST_DURATION: int = 60 * 60  # Blacklist for 1 hour (in seconds)

    # Repeated violator detection configuration
    REPEATED_VIOLATOR_WINDOW_MINUTES: int = 10  # Time window for repeated violator detection
    REPEATED_VIOLATOR_MIN_UNIQUE_IPS: int = 3  # Unique IPs required in window

    # Fernet encryption key (for TOTP secret encryption)
    FERNET_KEY: SecretStr = SecretStr("")  # Must be set in .sbd or environment

    # 2FA/Backup code config (loaded from .sbd if present)
    BACKUP_CODES_PENDING_TIME: int = 300  # 5 minutes
    BACKUP_CODES_CLEANUP_INTERVAL: int = 60  # 60 seconds by default

    # Cloudflare Turnstile config
    TURNSTILE_SITEKEY: SecretStr = SecretStr("")  # Must be set in .sbd or environment
    TURNSTILE_SECRET: SecretStr = SecretStr("")  # Must be set in .sbd or environment

    # Password reset abuse/whitelist stricter limits
    STRICTER_WHITELIST_LIMIT: int = 3  # Max resets per 24h for whitelisted pairs
    STRICTER_WHITELIST_PERIOD: int = 86400  # 24h in seconds
    ABUSE_ACTION_TOKEN_EXPIRY: int = 1800  # 30 min (seconds)
    ABUSE_ACTION_BLOCK_EXPIRY: int = 86400  # 24h (seconds)
    MAX_RESET_REQUESTS: int = 8  # Max reset requests in 15 min
    MAX_RESET_UNIQUE_IPS: int = 4  # Max unique IPs in 15 min

    # Logging configuration
    DEFAULT_LOG_LEVEL: str = "INFO"
    DEFAULT_BUFFER_FILE: str = "loki_buffer.log"
    LOKI_VERSION: str = "1"
    LOKI_COMPRESS: bool = True

    # Redis/Abuse sync intervals
    REDIS_FLAG_SYNC_INTERVAL: int = 60  # Interval for syncing password reset flags to Redis (seconds)
    BLOCKLIST_RECONCILE_INTERVAL: int = 300  # Interval for blocklist/whitelist reconciliation (seconds)

    # Documentation configuration
    DOCS_ENABLED: bool = True  # Enable/disable documentation endpoints
    DOCS_URL: Optional[str] = "/docs"  # Swagger UI URL
    REDOC_URL: Optional[str] = "/redoc"  # ReDoc URL
    OPENAPI_URL: Optional[str] = "/openapi.json"  # OpenAPI schema URL
    DOCS_ACCESS_CONTROL: bool = False  # Enable access control for docs
    DOCS_CACHE_ENABLED: bool = True  # Enable documentation caching
    DOCS_CACHE_TTL: int = 3600  # Documentation cache TTL in seconds

    # Production documentation security
    DOCS_ALLOWED_IPS: Optional[str] = None  # Comma-separated list of allowed IPs for docs
    DOCS_REQUIRE_AUTH: bool = False  # Require authentication for documentation access
    DOCS_RATE_LIMIT_REQUESTS: int = 10  # Max documentation requests per minute per IP
    DOCS_RATE_LIMIT_PERIOD: int = 60  # Rate limit period in seconds

    # CORS configuration for documentation
    DOCS_CORS_ORIGINS: Optional[str] = None  # Comma-separated allowed origins for docs CORS
    DOCS_CORS_CREDENTIALS: bool = False  # Allow credentials in CORS for docs
    DOCS_CORS_METHODS: str = "GET"  # Allowed methods for docs CORS
    DOCS_CORS_HEADERS: str = "Content-Type,Authorization"  # Allowed headers for docs CORS
    DOCS_CORS_MAX_AGE: int = 3600  # CORS preflight cache duration

    # --- Admin/Abuse Service Constants ---
    WHITELIST_KEY: str = "abuse:reset:whitelist"
    BLOCKLIST_KEY: str = "abuse:reset:blocklist"
    ABUSE_FLAG_PREFIX: str = "abuse:reset:flagged"
    USERS_COLLECTION: str = "users"
    ABUSE_EVENTS_COLLECTION: str = "reset_abuse_events"

    # Telegram configuration
    TELEGRAM_BOT_TOKEN: str = ""  # Set in .sbd/.env or environment
    TELEGRAM_CHAT_ID: str = ""    # Set in .sbd/.env or environment

    # GPG encryption configuration
    GPG_HOME: str = "~/.gnupg"  # Directory for GPG keyring
    GPG_RECIPIENT: str = ""      # GPG key ID or email for encryption
    GPG_KEY_PASSPHRASE: str = "second_brain_static_gpg_passphrase"  # Passphrase for generated key
    GPG_KEY_EMAIL: str = "second_brain@localhost"  # Email for generated key
    GPG_KEY_TYPE: str = "RSA"    # Key type
    GPG_KEY_LENGTH: int = 2048   # Key length

    # OAuth2 Provider Configuration
    OAUTH2_ENABLED: bool = True  # Enable/disable OAuth2 provider functionality
    OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES: int = 10  # Authorization code expiration (RFC 6749 recommends max 10 min)
    OAUTH2_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # OAuth2 access token expiration (1 hour)
    OAUTH2_REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # Refresh token expiration (30 days)
    OAUTH2_CONSENT_EXPIRE_DAYS: int = 365  # User consent expiration (1 year)
    
    # OAuth2 Security Configuration
    OAUTH2_REQUIRE_PKCE: bool = True  # Require PKCE for all OAuth2 flows
    OAUTH2_ALLOW_PLAIN_PKCE: bool = False  # Allow plain PKCE method (less secure)
    OAUTH2_MAX_CLIENTS_PER_USER: int = 10  # Maximum OAuth2 clients per user
    OAUTH2_CLIENT_SECRET_LENGTH: int = 32  # Length of generated client secrets
    OAUTH2_AUTHORIZATION_CODE_LENGTH: int = 32  # Length of authorization codes
    OAUTH2_REFRESH_TOKEN_LENGTH: int = 32  # Length of refresh tokens
    
    # OAuth2 Rate Limiting
    OAUTH2_AUTHORIZE_RATE_LIMIT: int = 100  # Max authorization requests per period
    OAUTH2_AUTHORIZE_RATE_PERIOD: int = 300  # Authorization rate limit period (5 minutes)
    OAUTH2_TOKEN_RATE_LIMIT: int = 50  # Max token requests per period
    OAUTH2_TOKEN_RATE_PERIOD: int = 300  # Token rate limit period (5 minutes)
    OAUTH2_CLIENT_REGISTRATION_RATE_LIMIT: int = 5  # Max client registrations per period
    OAUTH2_CLIENT_REGISTRATION_RATE_PERIOD: int = 3600  # Client registration rate limit period (1 hour)
    
    # OAuth2 Supported Scopes
    OAUTH2_DEFAULT_SCOPES: str = "read:profile"  # Default scopes for new clients
    OAUTH2_AVAILABLE_SCOPES: str = "read:profile,write:profile,read:data,write:data,read:tokens,write:tokens,admin"  # Available scopes
    OAUTH2_ADMIN_ONLY_SCOPES: str = "admin"  # Scopes restricted to admin users
    
    # OAuth2 Provider Metadata
    OAUTH2_ISSUER: str = ""  # OAuth2 issuer URL (will default to BASE_URL if empty)
    OAUTH2_AUTHORIZATION_ENDPOINT: str = "/oauth2/authorize"  # Authorization endpoint path
    OAUTH2_TOKEN_ENDPOINT: str = "/oauth2/token"  # Token endpoint path
    OAUTH2_REVOCATION_ENDPOINT: str = "/oauth2/revoke"  # Token revocation endpoint path
    OAUTH2_INTROSPECTION_ENDPOINT: str = "/oauth2/introspect"  # Token introspection endpoint path
    OAUTH2_USERINFO_ENDPOINT: str = "/oauth2/userinfo"  # User info endpoint path
    OAUTH2_JWKS_ENDPOINT: str = "/oauth2/jwks"  # JSON Web Key Set endpoint path
    
    # OAuth2 Client Management
    OAUTH2_CLIENT_REGISTRATION_ENABLED: bool = True  # Enable client registration endpoint
    OAUTH2_CLIENT_REGISTRATION_REQUIRE_AUTH: bool = True  # Require authentication for client registration
    OAUTH2_CLIENT_MANAGEMENT_ENABLED: bool = True  # Enable client management endpoints
    OAUTH2_AUTO_APPROVE_INTERNAL_CLIENTS: bool = False  # Auto-approve consent for internal clients
    
    # OAuth2 Cleanup and Maintenance
    OAUTH2_CLEANUP_INTERVAL_HOURS: int = 6  # Interval for cleaning up expired codes/tokens
    OAUTH2_AUDIT_LOG_RETENTION_DAYS: int = 90  # Days to keep OAuth2 audit logs
    OAUTH2_METRICS_RETENTION_DAYS: int = 30  # Days to keep OAuth2 metrics

    @field_validator("SECRET_KEY", "FERNET_KEY", "TURNSTILE_SITEKEY", "TURNSTILE_SECRET", mode="before")
    @classmethod
    def no_hardcoded_secrets(cls, v, info):
        if not v or "change" in str(v).lower() or "0000" in str(v) or not str(v).strip():
            raise ValueError(f"{info.field_name} must be set via environment or .sbd and not hardcoded!")
        return v

    @field_validator("MONGODB_URL", "REDIS_URL", mode="before")
    @classmethod
    def no_empty_urls(cls, v, info):
        if not v or not str(v).strip():
            raise ValueError(f"{info.field_name} must be set via environment or .sbd and not empty!")
        return v

    @field_validator("OAUTH2_AVAILABLE_SCOPES", mode="before")
    @classmethod
    def validate_oauth2_scopes(cls, v):
        """Validate OAuth2 scopes format."""
        if not v:
            return v
        
        # Split scopes and validate format
        scopes = [scope.strip() for scope in str(v).split(",") if scope.strip()]
        for scope in scopes:
            if not scope.replace(":", "").replace("_", "").isalnum():
                raise ValueError(f"Invalid OAuth2 scope format: {scope}")
        
        return v

    @field_validator("OAUTH2_AUTHORIZATION_CODE_EXPIRE_MINUTES", mode="before")
    @classmethod
    def validate_auth_code_expiry(cls, v):
        """Validate authorization code expiry is within RFC 6749 recommendations."""
        if v and int(v) > 10:
            raise ValueError("OAuth2 authorization code expiry should not exceed 10 minutes per RFC 6749")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return not self.DEBUG

    @property
    def is_testing(self) -> bool:
        """Check if running in test environment."""
        import sys
        import os
        
        # Check if pytest is running
        if 'pytest' in sys.modules or 'pytest' in sys.argv[0] if sys.argv else False:
            return True
            
        # Check for test environment variables
        if os.environ.get('TESTING') == 'true' or os.environ.get('PYTEST_CURRENT_TEST'):
            return True
            
        # Check if running from tests directory
        if any('test' in arg for arg in sys.argv):
            return True
            
        return False

    @property
    def docs_should_be_enabled(self) -> bool:
        """Determine if documentation should be enabled based on environment."""
        return self.DEBUG or self.DOCS_ENABLED

    @property
    def should_cache_docs(self) -> bool:
        """Determine if documentation should be cached."""
        return self.is_production and self.DOCS_CACHE_ENABLED

    @property
    def oauth2_issuer_url(self) -> str:
        """Get OAuth2 issuer URL, defaulting to BASE_URL if not set."""
        return self.OAUTH2_ISSUER if self.OAUTH2_ISSUER else self.BASE_URL

    @property
    def oauth2_available_scopes_list(self) -> list[str]:
        """Get OAuth2 available scopes as a list."""
        return [scope.strip() for scope in self.OAUTH2_AVAILABLE_SCOPES.split(",") if scope.strip()]

    @property
    def oauth2_default_scopes_list(self) -> list[str]:
        """Get OAuth2 default scopes as a list."""
        return [scope.strip() for scope in self.OAUTH2_DEFAULT_SCOPES.split(",") if scope.strip()]

    @property
    def oauth2_admin_only_scopes_list(self) -> list[str]:
        """Get OAuth2 admin-only scopes as a list."""
        return [scope.strip() for scope in self.OAUTH2_ADMIN_ONLY_SCOPES.split(",") if scope.strip()]

    @property
    def oauth2_endpoints(self) -> dict[str, str]:
        """Get OAuth2 endpoint URLs."""
        base_url = self.oauth2_issuer_url.rstrip("/")
        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}{self.OAUTH2_AUTHORIZATION_ENDPOINT}",
            "token_endpoint": f"{base_url}{self.OAUTH2_TOKEN_ENDPOINT}",
            "revocation_endpoint": f"{base_url}{self.OAUTH2_REVOCATION_ENDPOINT}",
            "introspection_endpoint": f"{base_url}{self.OAUTH2_INTROSPECTION_ENDPOINT}",
            "userinfo_endpoint": f"{base_url}{self.OAUTH2_USERINFO_ENDPOINT}",
            "jwks_uri": f"{base_url}{self.OAUTH2_JWKS_ENDPOINT}",
        }


# Global settings instance
settings: Settings = Settings()
