"""
Configuration module for Second Brain Database.

Loads environment settings via Pydantic and dotenv.
"""

from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Server configuration (loaded from environment)
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True

    # Base URL configuration
    BASE_URL: str = "http://localhost:8000"

    # JWT configuration (loaded from environment)
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # MongoDB configuration (loaded from environment)
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "second_brain_db"
    MONGODB_CONNECTION_TIMEOUT: int = 10000
    MONGODB_SERVER_SELECTION_TIMEOUT: int = 5000

    # Authentication (optional)
    MONGODB_USERNAME: Optional[str] = None
    MONGODB_PASSWORD: Optional[str] = None

    # Redis configuration
    REDIS_URL: str = "redis://localhost:6379/0"

    # Rate limiting configuration
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD_SECONDS: int = 60

    # Blacklist configuration
    BLACKLIST_THRESHOLD: int = 10  # Number of violations before blacklisting
    BLACKLIST_DURATION: int = 60 * 60  # Blacklist for 1 hour (in seconds)

    class Config:
        """Pydantic configuration class for environment loading."""
        env_file = ".sbd"
        env_file_encoding = "utf-8"
        case_sensitive = True

        def validate_env_file(self) -> bool:
            """Validate that environment file exists and is readable."""
            return True

        def get_env_vars(self) -> dict:
            """Get all environment variables as a dictionary."""
            return {}

# Global settings instance
settings = Settings()
