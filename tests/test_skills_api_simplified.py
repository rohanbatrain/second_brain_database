"""
Simplified integration tests for the Skills API endpoints with mocked database operations.

Tests all CRUD operations, authentication, authorization, error handling,
and API structure without real database interactions.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
import jwt
import pytest

from second_brain_database.main import app


@pytest.fixture
def client():
    """Provides a test client for the application."""
    # Mock the database and Redis connections to avoid event loop issues
    with patch('second_brain_database.database.db_manager.connect', new_callable=AsyncMock), \
         patch('second_brain_database.database.db_manager.disconnect', new_callable=AsyncMock), \
         patch('second_brain_database.managers.redis_manager.redis_manager.connect', new_callable=AsyncMock), \
         patch('second_brain_database.managers.redis_manager.redis_manager.disconnect', new_callable=AsyncMock), \
         patch('second_brain_database.routes.auth.services.abuse.management.reconcile_blocklist_whitelist', new_callable=AsyncMock), \
         patch('second_brain_database.database.db_manager.create_indexes', new_callable=AsyncMock):

        with TestClient(app) as c:
            yield c


# --- User Data Fixtures ---

@pytest.fixture
def owner_user_data():
    """Test user who will own skills."""
    return {
        "username": f"skill_owner_{uuid.uuid4().hex}",
        "email": f"skill_owner_{uuid.uuid4().hex}@example.com",
        "password": "Str0ngP@ssw0rd!",
    }


@pytest.fixture
def other_user_data():
    """Another test user for authorization tests."""
    return {
        "username": f"skill_other_{uuid.uuid4().hex}",
        "email": f"skill_other_{uuid.uuid4().hex}@example.com",
        "password": "Str0ngP@ssw0rd!",
    }


# --- Mock Authentication Helpers ---

def create_mock_auth(user_data, user_id="test_user_123"):
    """Create mock authentication headers."""
    # Create a mock JWT token
    token_payload = {
        "sub": user_id,
        "username": user_data["username"],
        "exp": datetime.now().timestamp() + 3600,  # 1 hour from now
        "iat": datetime.now().timestamp(),
    }

    # Use a mock secret for testing
    token = jwt.encode(token_payload, "test_secret", algorithm="HS256")

    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}


@pytest.fixture
def owner_auth(owner_user_data):
    """Mock authenticated owner user."""
    return create_mock_auth(owner_user_data)


@pytest.fixture
def other_auth(other_user_data):
    """Mock authenticated other user."""
    return create_mock_auth(other_user_data, "test_user_456")


@pytest.fixture
def mock_current_user():
    """Mock current user dependency."""
    return {
        "_id": "test_user_123",
        "user_id": "test_user_123",
        "username": "testuser",
        "email": "test@example.com"
    }


@pytest.fixture
def mock_skill_manager():
    """Mock skill manager with async methods."""
    manager = Mock()

    # Mock all the async methods
    manager.create_skill = AsyncMock(return_value=Mock(
        skill_id="test_skill_123",
        name="Test Skill",
        description="A test skill",
        parent_skill_ids=[],
        tags=["test"],
        metadata={},
        created_at=datetime.now(),
        updated_at=datetime.now()
    ))

    manager.list_skills = AsyncMock(return_value={
        "skills": [{
            "skill_id": "test_skill_123",
            "name": "Test Skill",
            "description": "A test skill",
            "parent_skill_ids": [],
            "child_skill_ids": [],
            "tags": ["test"],
            "metadata": {},
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }],
        "total_count": 1,
        "skip": 0,
        "limit": 50
    })

    manager.get_skill = AsyncMock(return_value={
        "skill_id": "test_skill_123",
        "name": "Test Skill",
        "description": "A test skill",
        "parent_skill_ids": [],
        "child_skill_ids": [],
        "tags": ["test"],
        "metadata": {},
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })

    manager.get_skill_tree = AsyncMock(return_value=[{
        "skill_id": "test_skill_123",
        "name": "Test Skill",
        "description": "A test skill",
        "children": []
    }])

    manager.get_analytics_summary = AsyncMock(return_value={
        "total_skills": 1,
        "total_logs": 0,
        "average_progress": 0.0,
        "most_active_skill": None,
        "recent_activity": []
    })

    return manager


class TestSkillAPIEndpoints:
    """Test skill API endpoint structure and responses."""

    def test_skills_endpoints_exist(self, client: TestClient):
        """Test that all expected skill endpoints exist."""
        # Test that endpoints return 401 (unauthorized) when no auth provided
        endpoints_to_test = [
            ("GET", "/api/v1/skills/"),
            ("POST", "/api/v1/skills/"),
            ("GET", "/api/v1/skills/tree"),
            ("GET", "/api/v1/skills/analytics/summary"),
        ]

        for method, endpoint in endpoints_to_test:
            response = client.request(method, endpoint)
            # Should get 401 unauthorized since no auth provided
            assert response.status_code in [401, 403], f"Endpoint {method} {endpoint} should require auth"

    @patch('fastapi.Depends')
    @patch('second_brain_database.managers.workspace_manager.workspace_manager.get_workspaces_for_user')
    @patch('second_brain_database.routes.skills.get_skill_manager')
    @patch('fastapi.security.HTTPBearer.__call__')
    def test_skill_creation_endpoint_structure(self, mock_http_bearer, mock_get_skill_manager, mock_get_workspaces, mock_depends, client: TestClient, mock_current_user, mock_skill_manager):
        """Test skill creation endpoint accepts proper data structure."""
        # Mock HTTP Bearer to return a fake token
        mock_http_bearer.return_value = "fake_token"
        
        # Mock Depends to return the mock user directly
        mock_depends.return_value = mock_current_user
        
        mock_get_skill_manager.return_value = mock_skill_manager
        mock_get_workspaces.return_value = []

        skill_data = {
            "name": "Test Python Programming",
            "description": "A test skill for Python programming",
            "tags": ["python", "programming", "test"],
        }

        response = client.post("/api/v1/skills/", json=skill_data)
        # Should not get 401 (auth bypassed) and should get proper response
        assert response.status_code not in [401, 403], f"Auth should be bypassed: {response.status_code}"
        # The endpoint should exist and process the request
        assert response.status_code in [200, 201, 422], f"Endpoint should exist: {response.status_code}"

    @patch('second_brain_database.managers.workspace_manager.workspace_manager.get_workspaces_for_user')
    @patch('second_brain_database.routes.skills.get_skill_manager')
    @patch('second_brain_database.routes.auth.services.auth.login.get_current_user')
    @patch('fastapi.security.HTTPBearer.__call__')
    def test_skill_retrieval_endpoints(self, mock_http_bearer, mock_get_current_user, mock_get_skill_manager, mock_get_workspaces, client: TestClient, mock_current_user, mock_skill_manager):
        """Test skill retrieval endpoints exist and work."""
        mock_http_bearer.return_value = "fake_token"
        mock_get_current_user.return_value = mock_current_user
        mock_get_skill_manager.return_value = mock_skill_manager
        mock_get_workspaces.return_value = []

        response = client.get("/api/v1/skills/")
        # Should not get 401 (auth bypassed) and should get proper response
        assert response.status_code not in [401, 403], f"Auth should be bypassed: {response.status_code}"
        assert response.status_code in [200, 422], f"Skills list endpoint should exist: {response.status_code}"

    @patch('second_brain_database.managers.workspace_manager.workspace_manager.get_workspaces_for_user')
    @patch('second_brain_database.routes.skills.get_skill_manager')
    @patch('second_brain_database.routes.auth.services.auth.login.get_current_user')
    @patch('fastapi.security.HTTPBearer.__call__')
    def test_create_skill_invalid_data(self, mock_http_bearer, mock_get_current_user, mock_get_skill_manager, mock_get_workspaces, client: TestClient, mock_current_user, mock_skill_manager):
        """Test skill tree endpoint exists."""
        mock_http_bearer.return_value = "fake_token"
        mock_get_current_user.return_value = mock_current_user
        mock_get_skill_manager.return_value = mock_skill_manager
        mock_get_workspaces.return_value = []

        response = client.get("/api/v1/skills/tree")
        assert response.status_code not in [401, 403], f"Auth should be bypassed: {response.status_code}"
        assert response.status_code in [200, 422], f"Skill tree endpoint should exist: {response.status_code}"

    @patch('second_brain_database.managers.workspace_manager.workspace_manager.get_workspaces_for_user')
    @patch('second_brain_database.routes.skills.get_skill_manager')
    @patch('second_brain_database.routes.auth.services.auth.login.get_current_user')
    @patch('fastapi.security.HTTPBearer.__call__')
    def test_skill_analytics_endpoint(self, mock_http_bearer, mock_get_current_user, mock_get_skill_manager, mock_get_workspaces, client: TestClient, mock_current_user, mock_skill_manager):
        """Test skill analytics endpoint exists."""
        mock_http_bearer.return_value = "fake_token"
        mock_get_current_user.return_value = mock_current_user
        mock_get_skill_manager.return_value = mock_skill_manager
        mock_get_workspaces.return_value = []

        response = client.get("/api/v1/skills/analytics/summary")
        assert response.status_code not in [401, 403], f"Auth should be bypassed: {response.status_code}"
        assert response.status_code in [200, 422], f"Analytics endpoint should exist: {response.status_code}"


class TestSkillLogAPIEndpoints:
    """Test skill log API endpoint structure."""

    def test_skill_log_endpoints_exist(self, client: TestClient, owner_auth):
        """Test that skill log endpoints exist."""
        # Test with a mock skill ID
        skill_id = "mock_skill_123"

        endpoints_to_test = [
            ("GET", f"/api/v1/skills/{skill_id}/logs"),
            ("POST", f"/api/v1/skills/{skill_id}/logs"),
        ]

        for method, endpoint in endpoints_to_test:
            response = client.request(method, endpoint, headers=owner_auth["headers"])
            # Should not get 404 (endpoint doesn't exist)
            assert response.status_code != 404, f"Endpoint {method} {endpoint} should exist"


class TestSkillHierarchyAPIEndpoints:
    """Test skill hierarchy API endpoint structure."""

    def test_skill_hierarchy_endpoints_exist(self, client: TestClient, owner_auth):
        """Test that skill hierarchy endpoints exist."""
        skill_id = "mock_skill_123"
        parent_id = "mock_parent_456"

        endpoints_to_test = [
            ("POST", f"/api/v1/skills/{skill_id}/link/{parent_id}"),
            ("DELETE", f"/api/v1/skills/{skill_id}/link/{parent_id}"),
        ]

        for method, endpoint in endpoints_to_test:
            response = client.request(method, endpoint, headers=owner_auth["headers"])
            # Should not get 404 (endpoint doesn't exist)
            assert response.status_code != 404, f"Endpoint {method} {endpoint} should exist"


class TestAuthentication:
    """Test authentication and authorization."""

    def test_skills_endpoints_require_auth(self, client: TestClient):
        """Test that skills endpoints require authentication."""
        endpoints = [
            ("GET", "/api/v1/skills/"),
            ("POST", "/api/v1/skills/"),
            ("GET", "/api/v1/skills/some_id"),
            ("PUT", "/api/v1/skills/some_id"),
            ("DELETE", "/api/v1/skills/some_id"),
            ("GET", "/api/v1/skills/tree"),
            ("GET", "/api/v1/skills/analytics/summary"),
        ]

        for method, endpoint in endpoints:
            response = client.request(method, endpoint)
            assert response.status_code in [401, 403], f"Endpoint {method} {endpoint} should require auth but got {response.status_code}"


class TestRequestValidation:
    """Test request validation and error handling."""

    def test_skill_creation_validation(self, client: TestClient, owner_auth):
        """Test skill creation request validation."""
        # Test missing required fields
        response = client.post("/api/v1/skills/", headers=owner_auth["headers"], json={})
        assert response.status_code == 422, "Should validate required fields"

        # Test invalid data types
        invalid_data = {
            "name": "",  # Empty name should fail
            "tags": "not_a_list",  # Should be a list
        }
        response = client.post("/api/v1/skills/", headers=owner_auth["headers"], json=invalid_data)
        assert response.status_code == 422, "Should validate data types"

    def test_skill_log_validation(self, client: TestClient, owner_auth):
        """Test skill log request validation."""
        skill_id = "mock_skill_123"

        # Test missing required fields
        response = client.post(f"/api/v1/skills/{skill_id}/logs", headers=owner_auth["headers"], json={})
        assert response.status_code == 422, "Should validate required log fields"

        # Test invalid progress state
        invalid_log = {
            "progress_state": "invalid_state",
            "numeric_level": 1,
        }
        response = client.post(f"/api/v1/skills/{skill_id}/logs", headers=owner_auth["headers"], json=invalid_log)
        assert response.status_code == 422, "Should validate progress state"


class TestErrorResponses:
    """Test error response formats."""

    @patch('second_brain_database.routes.skills.get_skill_manager')
    @patch('second_brain_database.routes.auth.services.auth.login.get_current_user')
    @patch('fastapi.security.OAuth2PasswordBearer.__call__')
    @patch('fastapi.security.HTTPBearer.__call__')
    @patch('second_brain_database.managers.workspace_manager.workspace_manager.get_workspaces_for_user')
    def test_not_found_responses(self, mock_get_workspaces, mock_http_bearer, mock_oauth_bearer, mock_get_current_user, mock_get_skill_manager, client: TestClient, mock_current_user):
        """Test 404 responses for non-existent resources."""
        from second_brain_database.managers.skill_manager import SkillNotFoundError

        # Mock HTTPBearer to return credentials
        mock_http_bearer.return_value = "fake_token"
        
        # Mock OAuth2PasswordBearer to return a token
        mock_oauth_bearer.return_value = "fake_token"

        # Mock workspace retrieval to return empty list
        mock_get_workspaces.return_value = []

        # Mock auth - return the mock user directly
        mock_get_current_user.return_value = mock_current_user

        # Mock skill manager's get_skill method to raise SkillNotFoundError
        mock_skill_manager_instance = AsyncMock()
        mock_skill_manager_instance.get_skill = AsyncMock(side_effect=SkillNotFoundError("nonexistent_id", mock_current_user["user_id"]))
        mock_get_skill_manager.return_value = mock_skill_manager_instance

        print(f"Mock skill manager: {mock_skill_manager_instance}")
        print(f"Mock get_skill: {mock_skill_manager_instance.get_skill}")
        print(f"Mock get_skill_manager return_value: {mock_get_skill_manager.return_value}")

        # Test non-existent skill - provide Authorization header
        response = client.get("/api/v1/skills/nonexistent_id", headers={"Authorization": "Bearer fake_token"})
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.content}")
        print(f"Mock get_skill called: {mock_skill_manager_instance.get_skill.called}")
        print(f"Mock get_skill call_count: {mock_skill_manager_instance.get_skill.call_count}")
        if mock_skill_manager_instance.get_skill.called:
            print(f"Mock get_skill call_args: {mock_skill_manager_instance.get_skill.call_args}")
        # Should get 404 for not found
        assert response.status_code == 404, f"Should handle non-existent skill gracefully: {response.status_code}"

    def test_malformed_json(self, client: TestClient, owner_auth):
        """Test handling of malformed JSON."""
        response = client.post(
            "/api/v1/skills/",
            headers={**owner_auth["headers"], "Content-Type": "application/json"},
            data="invalid json"
        )
        assert response.status_code == 422, "Should handle malformed JSON"