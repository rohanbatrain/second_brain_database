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
from typing import Optional, List, Dict, Any

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
    # Redis configuration
    # REDIS_URL is the effective URL used by the app. It can be provided directly
    # or will be constructed from REDIS_STORAGE_URI or host/port/credentials below.
    REDIS_URL: Optional[str] = None
    REDIS_STORAGE_URI: Optional[str] = None
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USERNAME: Optional[str] = None
    REDIS_PASSWORD: Optional[SecretStr] = None

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
    
    # Family-specific rate limiting configuration
    FAMILY_CREATE_RATE_LIMIT: int = 2  # Max families created per hour per user
    FAMILY_INVITE_RATE_LIMIT: int = 10  # Max invitations sent per hour per user
    FAMILY_ADMIN_ACTION_RATE_LIMIT: int = 5  # Max admin actions per hour per user
    FAMILY_MEMBER_ACTION_RATE_LIMIT: int = 20  # Max member actions per hour per user
    
    # Family limits configuration for billing integration
    DEFAULT_MAX_FAMILIES_ALLOWED: int = 1  # Default max families per user
    DEFAULT_MAX_MEMBERS_PER_FAMILY: int = 5  # Default max members per family
    FAMILY_LIMITS_GRACE_PERIOD_DAYS: int = 30  # Grace period for limit downgrades
    ENABLE_FAMILY_USAGE_TRACKING: bool = True  # Track usage for billing
    FAMILY_USAGE_TRACKING_RETENTION_DAYS: int = 365  # How long to keep usage data

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
    
    # General CORS configuration for API
    CORS_ENABLED: bool = True  # Enable CORS for the entire API
    CORS_ORIGINS: str = "http://localhost:3000,https://agentchat.vercel.app"  # Comma-separated allowed origins

    # --- Voice agent integrations ---
    # Ollama local LLM host (include scheme), default to local Ollama HTTP server
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3.2:latest"  # default model name to use with Ollama (using full model)
    
    # Multiple model support - comma-separated list of available models
    OLLAMA_AVAILABLE_MODELS: str = "llama3.2:latest,gemma3:1b,deepseek-r1:1.5b"  # Available models for selection
    OLLAMA_REASONING_MODEL: str = "deepseek-r1:1.5b"  # Specialized reasoning model
    OLLAMA_FAST_MODEL: str = "llama3.2:latest"  # Fast response model with tool support
    OLLAMA_AUTO_MODEL_SELECTION: bool = True  # Enable automatic model selection based on query type
    
    # Celery Settings
    CELERY_BROKER_URL: str = ""  # Defaults to REDIS_URL
    CELERY_RESULT_BACKEND: str = ""  # Defaults to REDIS_URL
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    
    # LangSmith Observability
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "SecondBrainDatabase"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_TRACING: bool = False
    
    # AI Agent Configuration
    AI_MODEL_POOL_SIZE: int = 5  # Number of model instances in pool
    AI_MAX_CONCURRENT_SESSIONS: int = 100  # Max concurrent AI sessions
    AI_SESSION_TIMEOUT: int = 3600  # Session timeout in seconds (1 hour)
    AI_MODEL_RESPONSE_TIMEOUT: int = 120  # Model response timeout in seconds
    AI_WORKFLOW_TIMEOUT: int = 600  # Workflow timeout in seconds (10 minutes)
    AI_MODEL_TEMPERATURE: float = 0.7  # Model temperature (0.0-2.0)
    AI_DEFAULT_AGENT: str = "personal"  # Default agent type

    # Voice processing configuration
    VOICE_SAMPLE_RATE: int = 16000  # Audio sample rate for processing
    VOICE_CHUNK_SIZE: int = 1024  # Audio chunk size for streaming
    VOICE_MAX_AUDIO_LENGTH: int = 30  # Max audio length in seconds for STT
    VOICE_TTS_VOICE: str = "en"  # TTS voice/language

    # --- FastMCP Server Configuration ---
    # MCP Server basic configuration
    MCP_ENABLED: bool = True  # Enable/disable MCP server
    MCP_SERVER_NAME: str = "SecondBrainMCP"  # MCP server name
    MCP_SERVER_VERSION: str = "1.0.0"  # MCP server version
    MCP_DEBUG_MODE: bool = False  # Enable debug mode for MCP server
    
    # Modern FastMCP 2.x transport configuration
    MCP_TRANSPORT: str = "stdio"  # "stdio" for local clients, "http" for remote/production
    MCP_HTTP_HOST: str = "127.0.0.1"  # Host for HTTP transport (use 0.0.0.0 for production)
    MCP_HTTP_PORT: int = 8001  # Port for HTTP transport
    MCP_HTTP_CORS_ENABLED: bool = False  # Enable CORS for HTTP transport
    MCP_HTTP_CORS_ORIGINS: str = "*"  # Allowed CORS origins (comma-separated)
    
    # MCP Security configuration
    MCP_SECURITY_ENABLED: bool = True  # Enable security for MCP tools
    MCP_REQUIRE_AUTH: bool = True  # Require authentication for MCP tools
    MCP_AUTH_TOKEN: Optional[SecretStr] = None  # Bearer token for HTTP transport authentication
    MCP_AUDIT_ENABLED: bool = True  # Enable audit logging for MCP operations
    
    # MCP Rate limiting configuration
    MCP_RATE_LIMIT_ENABLED: bool = True  # Enable rate limiting for MCP tools
    MCP_RATE_LIMIT_REQUESTS: int = 100  # Max MCP requests per period per user
    MCP_RATE_LIMIT_PERIOD: int = 60  # Rate limit period in seconds
    MCP_RATE_LIMIT_BURST: int = 10  # Burst limit for MCP requests
    
    # MCP Performance configuration
    MCP_MAX_CONCURRENT_TOOLS: int = 50  # Maximum concurrent tool executions
    MCP_REQUEST_TIMEOUT: int = 30  # Request timeout in seconds
    MCP_TOOL_EXECUTION_TIMEOUT: int = 60  # Tool execution timeout in seconds
    
    # MCP Tool configuration
    MCP_TOOLS_ENABLED: bool = True  # Enable MCP tools
    MCP_RESOURCES_ENABLED: bool = True  # Enable MCP resources
    MCP_PROMPTS_ENABLED: bool = True  # Enable MCP prompts
    
    # MCP Tool Access Control (Individual tool categories)
    MCP_FAMILY_TOOLS_ENABLED: bool = True  # Enable family management tools
    MCP_AUTH_TOOLS_ENABLED: bool = True  # Enable authentication tools
    MCP_PROFILE_TOOLS_ENABLED: bool = True  # Enable profile management tools
    MCP_SHOP_TOOLS_ENABLED: bool = True  # Enable shop and asset tools
    MCP_WORKSPACE_TOOLS_ENABLED: bool = True  # Enable workspace tools
    MCP_ADMIN_TOOLS_ENABLED: bool = False  # Enable admin tools (default: false for security)
    MCP_SYSTEM_TOOLS_ENABLED: bool = False  # Enable system management tools (default: false for security)
    
    # MCP Access control configuration
    MCP_ALLOWED_ORIGINS: Optional[str] = None  # Comma-separated allowed origins for MCP
    MCP_IP_WHITELIST: Optional[str] = None  # Comma-separated IP whitelist for MCP access
    MCP_CORS_ENABLED: bool = False  # Enable CORS for MCP server
    
    # MCP Monitoring configuration
    MCP_METRICS_ENABLED: bool = True  # Enable metrics collection for MCP
    MCP_HEALTH_CHECK_ENABLED: bool = True  # Enable health check endpoints
    MCP_PERFORMANCE_MONITORING: bool = True  # Enable performance monitoring
    
    # MCP Error handling configuration
    MCP_ERROR_RECOVERY_ENABLED: bool = True  # Enable error recovery mechanisms
    MCP_CIRCUIT_BREAKER_ENABLED: bool = True  # Enable circuit breaker pattern
    MCP_RETRY_ENABLED: bool = True  # Enable retry logic for failed operations
    MCP_RETRY_MAX_ATTEMPTS: int = 3  # Maximum retry attempts
    MCP_RETRY_BACKOFF_FACTOR: float = 2.0  # Exponential backoff factor
    
    # MCP Cache configuration
    MCP_CACHE_ENABLED: bool = True  # Enable caching for MCP operations
    MCP_CACHE_TTL: int = 300  # Cache TTL in seconds (5 minutes)
    MCP_CONTEXT_CACHE_TTL: int = 60  # User context cache TTL in seconds

    # --- LangChain/LangGraph AI Configuration (DISABLED) ---
    # LANGCHAIN_ENABLED: bool = True  # Enable/disable LangChain agents
    # LANGCHAIN_MODEL_PROVIDER: str = "ollama"  # openai, ollama, anthropic
    # LANGCHAIN_DEFAULT_MODEL: str = "llama3.2:1b"  # Default model for agents (llama3.2 supports tool calling)
    # LANGCHAIN_TEMPERATURE: float = 0.7  # Temperature for LLM responses
    # LANGCHAIN_MAX_TOKENS: int = 2048  # Max tokens per response
    # LANGCHAIN_MEMORY_TTL: int = 3600  # Memory TTL in seconds (1 hour)
    # LANGCHAIN_CONVERSATION_HISTORY_LIMIT: int = 50  # Max messages in history
    # LANGCHAIN_RATE_LIMIT_REQUESTS: int = 100  # Max AI requests per period
    # LANGCHAIN_MAX_CONCURRENT_SESSIONS: int = 1000  # Max concurrent AI sessions
    # LANGCHAIN_TRACING_V2: str = "false"  # LangSmith tracing (set to API key to enable)
    # LANGCHAIN_PROJECT: str = "SecondBrainDatabase"  # LangSmith project name

    # --- Admin/Abuse Service Constants ---
    WHITELIST_KEY: str = "abuse:reset:whitelist"
    BLOCKLIST_KEY: str = "abuse:reset:blocklist"
    ABUSE_FLAG_PREFIX: str = "abuse:reset:flagged"
    USERS_COLLECTION: str = "users"
    ABUSE_EVENTS_COLLECTION: str = "reset_abuse_events"

    @field_validator("SECRET_KEY", "FERNET_KEY", "TURNSTILE_SITEKEY", "TURNSTILE_SECRET", mode="before")
    @classmethod
    def no_hardcoded_secrets(cls, v, info):
        if not v or "change" in str(v).lower() or "0000" in str(v) or not str(v).strip():
            raise ValueError(f"{info.field_name} must be set via environment or .sbd and not hardcoded!")
        return v

    @field_validator("MONGODB_URL", mode="before")
    @classmethod
    def no_empty_urls(cls, v, info):
        if not v or not str(v).strip():
            raise ValueError(f"{info.field_name} must be set via environment or .sbd and not empty!")
        return v

    @field_validator("MCP_RATE_LIMIT_REQUESTS", "MCP_MAX_CONCURRENT_TOOLS", mode="before")
    @classmethod
    def validate_positive_integers(cls, v, info):
        """Validate that MCP numeric settings are positive."""
        value = int(v)
        if value <= 0:
            raise ValueError(f"{info.field_name} must be a positive integer")
        return value

    @field_validator("MCP_REQUEST_TIMEOUT", "MCP_TOOL_EXECUTION_TIMEOUT", mode="before")
    @classmethod
    def validate_timeout_values(cls, v, info):
        """Validate timeout values are reasonable."""
        timeout = int(v)
        if timeout < 1 or timeout > 300:
            raise ValueError(f"{info.field_name} must be between 1 and 300 seconds")
        return timeout

    @field_validator("MCP_RETRY_BACKOFF_FACTOR", mode="before")
    @classmethod
    def validate_backoff_factor(cls, v):
        """Validate retry backoff factor is reasonable."""
        factor = float(v)
        if factor < 1.0 or factor > 10.0:
            raise ValueError("MCP_RETRY_BACKOFF_FACTOR must be between 1.0 and 10.0")
        return factor

    @field_validator("AI_MODEL_POOL_SIZE", "AI_MAX_CONCURRENT_SESSIONS", mode="before")
    @classmethod
    def validate_ai_positive_integers(cls, v, info):
        """Validate that AI numeric settings are positive."""
        value = int(v)
        if value <= 0:
            raise ValueError(f"{info.field_name} must be a positive integer")
        return value

    @field_validator("AI_SESSION_TIMEOUT", "AI_MODEL_RESPONSE_TIMEOUT", "AI_WORKFLOW_TIMEOUT", mode="before")
    @classmethod
    def validate_ai_timeout_values(cls, v, info):
        """Validate AI timeout values are reasonable."""
        timeout = int(v)
        if timeout < 1 or timeout > 7200:  # Max 2 hours
            raise ValueError(f"{info.field_name} must be between 1 and 7200 seconds")
        return timeout

    @field_validator("AI_MODEL_TEMPERATURE", mode="before")
    @classmethod
    def validate_ai_temperature(cls, v):
        """Validate AI model temperature is in valid range."""
        temp = float(v)
        if temp < 0.0 or temp > 2.0:
            raise ValueError("AI_MODEL_TEMPERATURE must be between 0.0 and 2.0")
        return temp

    @field_validator("AI_DEFAULT_AGENT", mode="before")
    @classmethod
    def validate_ai_default_agent(cls, v):
        """Validate AI default agent is a valid agent type."""
        valid_agents = ["personal", "family", "workspace", "commerce", "security", "voice"]
        if v not in valid_agents:
            raise ValueError(f"AI_DEFAULT_AGENT must be one of: {', '.join(valid_agents)}")
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

    @property
    def mcp_should_be_enabled(self) -> bool:
        """Determine if MCP server should be enabled based on configuration."""
        return self.MCP_ENABLED and not (self.is_production and not self.MCP_SECURITY_ENABLED)

    @property
    def mcp_allowed_origins_list(self) -> list:
        """Get list of allowed origins for MCP CORS."""
        if not self.MCP_ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.MCP_ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def mcp_ip_whitelist_list(self) -> list:
        """Get list of whitelisted IPs for MCP access."""
        if not self.MCP_IP_WHITELIST:
            return []
        return [ip.strip() for ip in self.MCP_IP_WHITELIST.split(",") if ip.strip()]

    # ai_should_be_enabled method removed with AI orchestration system

    @property
    def ai_enabled_agents(self) -> list:
        """Get list of enabled AI agents."""
        agents = []
        if self.AI_FAMILY_AGENT_ENABLED:
            agents.append("family")
        if self.AI_PERSONAL_AGENT_ENABLED:
            agents.append("personal")
        if self.AI_WORKSPACE_AGENT_ENABLED:
            agents.append("workspace")
        if self.AI_COMMERCE_AGENT_ENABLED:
            agents.append("commerce")
        if self.AI_SECURITY_AGENT_ENABLED:
            agents.append("security")
        if self.AI_VOICE_AGENT_ENABLED:
            agents.append("voice")
        return agents

    @property
    def ai_model_config(self) -> dict:
        """Get AI model configuration for Ollama integration."""
        return {
            "host": self.OLLAMA_HOST,
            "model": self.OLLAMA_MODEL,
            "pool_size": self.AI_MODEL_POOL_SIZE,
            "timeout": self.AI_MODEL_RESPONSE_TIMEOUT,
            "max_tokens": self.AI_MODEL_MAX_TOKENS,
            "temperature": self.AI_MODEL_TEMPERATURE,
            "streaming": self.AI_MODEL_STREAMING_ENABLED,
            "available_models": self.ollama_available_models_list,
            "reasoning_model": self.OLLAMA_REASONING_MODEL,
            "fast_model": self.OLLAMA_FAST_MODEL,
            "auto_selection": self.OLLAMA_AUTO_MODEL_SELECTION
        }

    @property
    def ollama_available_models_list(self) -> list:
        """Get list of available Ollama models."""
        if not self.OLLAMA_AVAILABLE_MODELS:
            return [self.OLLAMA_MODEL]
        return [model.strip() for model in self.OLLAMA_AVAILABLE_MODELS.split(",") if model.strip()]

    @property
    def ai_performance_config(self) -> dict:
        """Get AI performance configuration."""
        return {
            "target_latency": self.AI_RESPONSE_TARGET_LATENCY,
            "cache_enabled": self.AI_CACHE_ENABLED,
            "cache_ttl": self.AI_CACHE_TTL,
            "conversation_cache_ttl": self.AI_CONVERSATION_CACHE_TTL,
            "context_preload": self.AI_CONTEXT_PRELOAD_ENABLED,
            "model_warmup": self.AI_MODEL_WARMUP_ENABLED
        }


# Global settings instance
settings: Settings = Settings()

# Compute effective REDIS_URL if not explicitly provided.
# Precedence: explicit REDIS_URL -> REDIS_STORAGE_URI -> constructed from host/port/db and optional credentials.
if not settings.REDIS_URL:
    if settings.REDIS_STORAGE_URI:
        settings.REDIS_URL = settings.REDIS_STORAGE_URI
    else:
        # Build credentials part
        creds = ""
        if settings.REDIS_USERNAME or settings.REDIS_PASSWORD:
            username = settings.REDIS_USERNAME or ""
            password = settings.REDIS_PASSWORD.get_secret_value() if settings.REDIS_PASSWORD else ""
            # If only password present, use :password@ form
            if username and password:
                creds = f"{username}:{password}@"
            elif password and not username:
                creds = f":{password}@"

        settings.REDIS_URL = f"redis://{creds}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
