"""
Pytest configuration for MCP integration tests.

Provides fixtures and configuration for testing MCP components
with proper mocking of dependencies and test environment setup.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# @pytest.fixture(scope="function")
# def event_loop():
#     """Create an instance of the default event loop for the test session."""
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for MCP tests."""
    settings = Mock()
    settings.MCP_ENABLED = True
    settings.MCP_SERVER_NAME = "TestMCP"
    settings.MCP_SERVER_VERSION = "1.0.0"
    settings.MCP_SERVER_PORT = 3001
    settings.MCP_SERVER_HOST = "localhost"
    settings.MCP_SECURITY_ENABLED = True
    settings.MCP_AUDIT_ENABLED = True
    settings.MCP_RATE_LIMIT_ENABLED = True
    settings.MCP_RATE_LIMIT_REQUESTS = 100
    settings.MCP_RATE_LIMIT_PERIOD = 60
    settings.MCP_MAX_CONCURRENT_TOOLS = 50
    settings.MCP_REQUEST_TIMEOUT = 30
    settings.MCP_DEBUG_MODE = False
    settings.ENV_PREFIX = "test"
    settings.REDIS_URL = "redis://localhost:6379/0"

    # Add missing settings for rate limiting
    settings.RATE_LIMIT_ENABLED = True
    settings.RATE_LIMIT_REQUESTS = 100
    settings.RATE_LIMIT_PERIOD = 60

    # Add logging settings to prevent validation errors
    settings.LOG_LEVEL = "INFO"
    settings.ENV = "test"
    settings.LOKI_BUFFER_FILE = "test_loki_buffer.log"
    settings.LOKI_VERSION = "1"

    # Add documentation settings to prevent validation errors
    settings.docs_should_be_enabled = True
    settings.DEBUG = False
    settings.DOCS_ENABLED = True
    settings.is_production = False
    settings.DOCS_URL = "/docs"
    settings.REDOC_URL = "/redoc"
    settings.OPENAPI_URL = "/openapi.json"
    settings.DOCS_ACCESS_CONTROL = True
    settings.DOCS_CACHE_ENABLED = True
    settings.DOCS_CACHE_TTL = 3600

    # Add Qdrant/Vector settings to prevent Mock objects in tests
    settings.QDRANT_HOST = "localhost"
    settings.QDRANT_PORT = 6333
    settings.QDRANT_HTTPS = False
    settings.QDRANT_API_KEY = None
    settings.QDRANT_TIMEOUT = 60
    settings.QDRANT_ENABLED = False  # Disable for tests by default
    settings.LLAMAINDEX_ENABLED = False  # Disable for tests by default

    return settings


@pytest.fixture
def mock_db_manager():
    """Mock database manager for MCP tests."""
    db_manager = AsyncMock()
    db_manager.connect = AsyncMock()
    db_manager.disconnect = AsyncMock()
    db_manager.get_collection = AsyncMock()
    return db_manager


@pytest.fixture
def mock_security_manager():
    """Mock security manager for MCP tests."""
    security_manager = AsyncMock()
    security_manager.check_rate_limit = AsyncMock()
    security_manager.validate_user_permissions = AsyncMock(return_value=True)
    security_manager.get_client_ip = Mock(return_value="127.0.0.1")
    security_manager.get_client_user_agent = Mock(return_value="TestClient/1.0")
    return security_manager


@pytest.fixture
def mock_redis_manager():
    """Mock Redis manager for MCP tests."""
    redis_manager = AsyncMock()
    redis_conn = AsyncMock()
    redis_manager.get_redis = AsyncMock(return_value=redis_conn)
    return redis_manager


@pytest.fixture
def mock_logger():
    """Mock logger for MCP tests."""
    logger = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    return logger


@pytest.fixture(autouse=True)
def mock_dependencies(mock_settings, mock_db_manager, mock_security_manager, mock_redis_manager, mock_logger):
    """Auto-mock common dependencies for all MCP tests."""
    with (
        patch("second_brain_database.config.settings", mock_settings),
        patch("second_brain_database.database.db_manager", mock_db_manager),
        patch("second_brain_database.managers.security_manager.security_manager", mock_security_manager),
        patch("second_brain_database.managers.redis_manager.redis_manager", mock_redis_manager),
        patch("second_brain_database.managers.logging_manager.get_logger", return_value=mock_logger),
    ):
        yield


@pytest.fixture
def sample_fastapi_user():
    """Sample FastAPI user object for testing."""
    return {
        "_id": "test_user_123",
        "username": "test_user",
        "email": "test@example.com",
        "role": "user",
        "permissions": ["family:read", "family:write", "profile:read"],
        "workspaces": [{"_id": "workspace_1", "name": "Test Workspace", "role": "member"}],
        "family_memberships": [{"family_id": "family_1", "role": "admin"}, {"family_id": "family_2", "role": "member"}],
        "trusted_ip_lockdown": False,
        "trusted_user_agent_lockdown": False,
        "trusted_ips": [],
        "trusted_user_agents": [],
    }


@pytest.fixture
def sample_admin_user():
    """Sample admin user object for testing."""
    return {
        "_id": "admin_user_123",
        "username": "admin_user",
        "email": "admin@example.com",
        "role": "admin",
        "permissions": ["admin", "family:read", "family:write", "profile:read", "system:read"],
        "workspaces": [],
        "family_memberships": [],
        "trusted_ip_lockdown": False,
        "trusted_user_agent_lockdown": False,
        "trusted_ips": [],
        "trusted_user_agents": [],
    }


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.slow = pytest.mark.slow
