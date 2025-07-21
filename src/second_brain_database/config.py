"""
Configuration module for Second Brain Database.

This module provides robust, production-grade configuration and logging bootstrapping for the application.

Rationale and Best Practices:
----------------------------
- **Fail-fast, explicit config discovery:**
  The config file is discovered in the following order: (1) via the `SECOND_BRAIN_DATABASE_CONFIG_PATH` environment variable, (2) `.sbd` in the project root, (3) `.env` in the project root. If none are found, the application fails fast with a clear error. This prevents silent misconfiguration and ensures that secrets and environment variables are always loaded as intended.

- **Pydantic Settings with extra env support:**
  The `Settings` class uses Pydantic's `BaseSettings` to load all configuration from the environment or config file, and allows extra environment variables (e.g., for OpenTelemetry or other integrations) without error. This makes the config extensible and cloud/deployment friendly.

- **No circular imports:**
  The logging logic for config bootstrapping is self-contained in this module, copied from the main logging manager, to avoid circular imports. After the config is loaded and the main logging manager is available, the main logger can be safely used.

- **Security and best practices:**
  Secrets (e.g., JWT keys, Fernet keys, DB URLs) are never hardcoded and must be set via environment or config file. Validators enforce this at startup. This prevents accidental leaks and enforces secure deployment.

- **Extensive documentation and PEP 257 compliance:**
  All classes, functions, and the module itself are documented with rationale, usage, and best practices for future maintainers. This is critical for production systems where config and logging are foundational and mistakes can have security or reliability consequences.

How to extend/maintain:
-----------------------
- Add new config fields to the `Settings` class, and document them.
- If you change the config discovery logic, update this docstring and the error messages.

For more details, see the README and the comments in this file.
"""

import os
from typing import Optional, Any
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import SecretStr, field_validator
from pathlib import Path

# --- Constants ---
SBD_FILENAME: str = ".sbd"
DEFAULT_ENV_FILENAME: str = ".env"
CONFIG_ENV_VAR: str = "SECOND_BRAIN_DATABASE_CONFIG_PATH"
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# --- Config file discovery (no logging) ---
def get_config_path() -> Optional[str]:
    """
    Determine the config file path to use, in order of precedence:
    1. Environment variable SECOND_BRAIN_DATABASE_CONFIG_PATH
    2. .sbd in project root
    3. .env in project root
    Returns:
        Optional[str]: Path to config file, or None if not found.
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
    except (OSError, IOError) as exc:
        raise
else:
    raise RuntimeError(
        f"No config file found. Please provide a config file as {SBD_FILENAME} or {DEFAULT_ENV_FILENAME} in the project root, "
        f"or set the {CONFIG_ENV_VAR} environment variable to a valid config path."
    )

class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    All fields are loaded from the environment or the .sbd/.env file.
    """
    model_config: dict[str, Any] = {
        "env_file": CONFIG_PATH,
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "allow"  # Allow extra env vars not defined as fields
    }

    # Server configuration (loaded from environment)
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True

    # Base URL configuration
    BASE_URL: str = "http://localhost:8000"

    # JWT configuration (loaded from environment)
    SECRET_KEY: SecretStr  # Must be set in .sbd or environment
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # MongoDB configuration (loaded from environment)
    MONGODB_URL: str  # Must be set in .sbd or environment
    MONGODB_DATABASE: str
    MONGODB_CONNECTION_TIMEOUT: int = 10000
    MONGODB_SERVER_SELECTION_TIMEOUT: int = 5000

    # Authentication (optional)
    MONGODB_USERNAME: Optional[str] = None
    MONGODB_PASSWORD: Optional[SecretStr] = None

    # Redis configuration
    REDIS_URL: str  # Must be set in .sbd or environment

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
    FERNET_KEY: SecretStr  # Must be set in .sbd or environment

    # 2FA/Backup code config (loaded from .sbd if present)
    BACKUP_CODES_PENDING_TIME: int = 300  # 5 minutes
    BACKUP_CODES_CLEANUP_INTERVAL: int = 60  # 60 seconds by default

    # Cloudflare Turnstile config
    TURNSTILE_SITEKEY: SecretStr  # Must be set in .sbd or environment
    TURNSTILE_SECRET: SecretStr  # Must be set in .sbd or environment

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

    @field_validator("SECRET_KEY", "FERNET_KEY", "TURNSTILE_SITEKEY", "TURNSTILE_SECRET", mode="before")
    @classmethod
    def no_hardcoded_secrets(cls, v, info):
        if not v or "change" in str(v).lower() or "0000" in str(v) or str(v).strip() == "":
            raise ValueError(f"{info.field_name} must be set via environment or .sbd and not hardcoded!")
        return v

    @field_validator("MONGODB_URL", "REDIS_URL", mode="before")
    @classmethod
    def no_empty_urls(cls, v, info):
        if not v or str(v).strip() == "":
            raise ValueError(f"{info.field_name} must be set via environment or .sbd and not empty!")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return not self.DEBUG

    @property
    def docs_should_be_enabled(self) -> bool:
        """Determine if documentation should be enabled based on environment."""
        return self.DEBUG or self.DOCS_ENABLED

    @property
    def should_cache_docs(self) -> bool:
        """Determine if documentation should be cached."""
        return self.is_production and self.DOCS_CACHE_ENABLED

# Global settings instance
settings: Settings = Settings()
