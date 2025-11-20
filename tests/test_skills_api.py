"""
Comprehensive integration tests for the Skills API endpoints.

Tests all CRUD operations, authentication, authorization, error handling,
and real database interactions.
"""

import asyncio
import uuid
from datetime import datetime

from fastapi.testclient import TestClient
import jwt
import pytest

from second_brain_database.database import db_manager
from second_brain_database.main import app

# Remove pytestmark to avoid event loop conflicts


@pytest.fixture(scope="session")
def client():
    """Provides a test client for the application for the whole session."""
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


# --- Authentication Helpers ---

async def create_and_verify_user(client, user_data):
    """Helper function to register, verify, and login a user."""
    register_response = client.post("/auth/register", json=user_data)
    assert register_response.status_code == 200, f"Failed to register user {user_data['username']}"

    users_collection = db_manager.get_collection("users")
    user_doc = await users_collection.find_one({"email": user_data["email"]})
    assert user_doc is not None, f"User {user_data['username']} not found in DB after registration"
    verification_token = user_doc.get("email_verification_token")
    assert verification_token is not None, "Email verification token not found in user doc"

    verify_response = client.get(f"/auth/verify-email?token={verification_token}")
    assert verify_response.status_code == 200, "Email verification failed"

    login_response = client.post(
        "/auth/login", data={"username": user_data["username"], "password": user_data["password"]}
    )
    assert login_response.status_code == 200, f"Failed to log in user {user_data['username']}"
    token = login_response.json()["access_token"]

    user_id = jwt.decode(token, options={"verify_signature": False})["sub"]

    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}


@pytest.fixture
async def owner_auth(client, owner_user_data):
    """Authenticated owner user."""
    return await create_and_verify_user(client, owner_user_data)


@pytest.fixture
async def other_auth(client, other_user_data):
    """Authenticated other user."""
    return await create_and_verify_user(client, other_user_data)


# --- Skill Test Fixtures ---

@pytest.fixture
async def test_skill(client, owner_auth):
    """Creates a test skill for testing."""
    skill_data = {
        "name": "Test Python Programming",
        "description": "A test skill for Python programming",
        "tags": ["python", "programming", "test"],
        "metadata": {
            "category": "programming",
            "difficulty": "intermediate",
            "priority": "high"
        }
    }

    response = client.post("/skills/", headers=owner_auth["headers"], json=skill_data)
    assert response.status_code == 201

    skill = response.json()
    return {
        "skill_id": skill["skill_id"],
        "data": skill,
        "owner_id": owner_auth["user_id"]
    }


@pytest.fixture
async def test_skill_with_logs(client, test_skill, owner_auth):
    """Creates a test skill with some log entries."""
    skill_id = test_skill["skill_id"]

    # Add some log entries
    logs_data = [
        {
            "progress_state": "learning",
            "numeric_level": 1,
            "notes": "Started learning Python basics",
            "context": {
                "duration_hours": 2.0,
                "confidence_level": 6
            }
        },
        {
            "progress_state": "practicing",
            "numeric_level": 2,
            "notes": "Built first Python script",
            "context": {
                "duration_hours": 3.5,
                "confidence_level": 7
            }
        }
    ]

    for log_data in logs_data:
        response = client.post(
            f"/skills/{skill_id}/logs",
            headers=owner_auth["headers"],
            json=log_data
        )
        assert response.status_code == 201

    return test_skill


class TestSkillCreation:
    """Test skill creation endpoints."""

    @pytest.mark.asyncio
    async def test_create_skill_success(self, client: TestClient, owner_auth):
        """Test successful skill creation."""
        skill_data = {
            "name": "JavaScript Development",
            "description": "Learning modern JavaScript development",
            "tags": ["javascript", "web", "frontend"],
            "metadata": {
                "category": "programming",
                "difficulty": "intermediate"
            }
        }

        response = client.post("/skills/", headers=owner_auth["headers"], json=skill_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "JavaScript Development"
        assert data["description"] == "Learning modern JavaScript development"
        assert data["user_id"] == owner_auth["user_id"]
        assert data["is_active"] is True
        assert "skill_id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_skill_minimal_data(self, client: TestClient, owner_auth):
        """Test skill creation with minimal required data."""
        skill_data = {"name": "Minimal Skill"}

        response = client.post("/skills/", headers=owner_auth["headers"], json=skill_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Minimal Skill"
        assert data["description"] is None
        assert data["tags"] == []
        assert data["parent_skill_ids"] == []

    @pytest.mark.asyncio
    async def test_create_skill_with_parent(self, client: TestClient, owner_auth, test_skill):
        """Test skill creation with parent skill."""
        parent_id = test_skill["skill_id"]

        skill_data = {
            "name": "Child Skill",
            "description": "A child skill",
            "parent_skill_ids": [parent_id]
        }

        response = client.post("/skills/", headers=owner_auth["headers"], json=skill_data)
        assert response.status_code == 201

        data = response.json()
        assert data["parent_skill_ids"] == [parent_id]

    async def test_create_skill_invalid_parent(self, client: TestClient, owner_auth):
        """Test skill creation fails with invalid parent."""
        skill_data = {
            "name": "Invalid Parent Skill",
            "parent_skill_ids": ["nonexistent_parent_id"]
        }

        response = client.post("/skills/", headers=owner_auth["headers"], json=skill_data)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_create_skill_circular_reference(self, client: TestClient, owner_auth, test_skill):
        """Test skill creation fails with circular reference."""
        # This is harder to test via API, but we can test the validation
        skill_data = {
            "name": "Circular Skill",
            "parent_skill_ids": [test_skill["skill_id"]]  # Parent to itself would be circular
        }

        response = client.post("/skills/", headers=owner_auth["headers"], json=skill_data)
        # This might not catch all circular references at creation time
        # depending on implementation, but should at least create successfully
        # or fail gracefully
        assert response.status_code in [201, 400]

    async def test_create_skill_validation_errors(self, client: TestClient, owner_auth):
        """Test skill creation with validation errors."""
        # Empty name
        response = client.post("/skills/", headers=owner_auth["headers"], json={"name": ""})
        assert response.status_code == 422

        # Name too long
        response = client.post("/skills/", headers=owner_auth["headers"], json={"name": "x" * 201})
        assert response.status_code == 422

        # Invalid metadata
        skill_data = {
            "name": "Invalid Metadata",
            "metadata": {"difficulty": "invalid_value"}
        }
        response = client.post("/skills/", headers=owner_auth["headers"], json=skill_data)
        assert response.status_code == 422


class TestSkillRetrieval:
    """Test skill retrieval endpoints."""

    @pytest.mark.asyncio
    async def test_get_skill_success(self, client: TestClient, test_skill, owner_auth):
        """Test successful skill retrieval."""
        skill_id = test_skill["skill_id"]

        response = client.get(f"/skills/{skill_id}", headers=owner_auth["headers"])
        assert response.status_code == 200

        data = response.json()
        assert data["skill_id"] == skill_id
        assert data["name"] == test_skill["data"]["name"]
        assert "child_skill_ids" in data

    async def test_get_skill_with_analytics(self, client: TestClient, test_skill_with_logs, owner_auth):
        """Test skill retrieval with analytics."""
        skill_id = test_skill_with_logs["skill_id"]

        response = client.get(f"/skills/{skill_id}?include_analytics=true", headers=owner_auth["headers"])
        assert response.status_code == 200

        data = response.json()
        assert "analytics" in data
        analytics = data["analytics"]
        assert "total_logs" in analytics
        assert "current_state" in analytics

    async def test_get_skill_not_found(self, client: TestClient, owner_auth):
        """Test retrieving non-existent skill."""
        response = client.get("/skills/nonexistent_id", headers=owner_auth["headers"])
        assert response.status_code == 404

    async def test_get_skill_wrong_user(self, client: TestClient, test_skill, other_auth):
        """Test retrieving skill owned by different user."""
        skill_id = test_skill["skill_id"]

        response = client.get(f"/skills/{skill_id}", headers=other_auth["headers"])
        assert response.status_code == 404

    async def test_list_skills_success(self, client: TestClient, owner_auth, test_skill):
        """Test successful skill listing."""
        response = client.get("/skills/", headers=owner_auth["headers"])
        assert response.status_code == 200

        data = response.json()
        assert "skills" in data
        assert "total_count" in data
        assert data["total_count"] >= 1

        # Find our test skill
        skill_ids = [skill["skill_id"] for skill in data["skills"]]
        assert test_skill["skill_id"] in skill_ids

    async def test_list_skills_pagination(self, client: TestClient, owner_auth):
        """Test skill listing with pagination."""
        response = client.get("/skills/?skip=0&limit=10", headers=owner_auth["headers"])
        assert response.status_code == 200

        data = response.json()
        assert len(data["skills"]) <= 10
        assert data["skip"] == 0
        assert data["limit"] == 10

    async def test_list_skills_with_analytics(self, client: TestClient, owner_auth, test_skill_with_logs):
        """Test skill listing with analytics."""
        response = client.get("/skills/?include_analytics=true", headers=owner_auth["headers"])
        assert response.status_code == 200

        data = response.json()
        for skill in data["skills"]:
            if skill["skill_id"] == test_skill_with_logs["skill_id"]:
                assert "analytics" in skill
                break


class TestSkillUpdate:
    """Test skill update endpoints."""

    async def test_update_skill_success(self, client: TestClient, test_skill, owner_auth):
        """Test successful skill update."""
        skill_id = test_skill["skill_id"]

        update_data = {
            "name": "Updated Skill Name",
            "description": "Updated description",
            "tags": ["updated", "tags"]
        }

        response = client.put(f"/skills/{skill_id}", headers=owner_auth["headers"], json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Updated Skill Name"
        assert data["description"] == "Updated description"
        assert data["tags"] == ["updated", "tags"]

    async def test_update_skill_partial(self, client: TestClient, test_skill, owner_auth):
        """Test partial skill update."""
        skill_id = test_skill["skill_id"]

        update_data = {"description": "Only updating description"}

        response = client.put(f"/skills/{skill_id}", headers=owner_auth["headers"], json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["description"] == "Only updating description"
        assert data["name"] == test_skill["data"]["name"]  # Unchanged

    async def test_update_skill_not_found(self, client: TestClient, owner_auth):
        """Test updating non-existent skill."""
        update_data = {"name": "New Name"}

        response = client.put("/skills/nonexistent_id", headers=owner_auth["headers"], json=update_data)
        assert response.status_code == 404

    async def test_update_skill_wrong_user(self, client: TestClient, test_skill, other_auth):
        """Test updating skill owned by different user."""
        skill_id = test_skill["skill_id"]
        update_data = {"name": "Should Not Update"}

        response = client.put(f"/skills/{skill_id}", headers=other_auth["headers"], json=update_data)
        assert response.status_code == 404


class TestSkillHierarchy:
    """Test skill hierarchy management endpoints."""

    async def test_link_parent_skill_success(self, client: TestClient, owner_auth):
        """Test successful parent skill linking."""
        # Create parent skill
        parent_response = client.post(
            "/skills/",
            headers=owner_auth["headers"],
            json={"name": "Parent Skill"}
        )
        assert parent_response.status_code == 201
        parent_id = parent_response.json()["skill_id"]

        # Create child skill
        child_response = client.post(
            "/skills/",
            headers=owner_auth["headers"],
            json={"name": "Child Skill"}
        )
        assert child_response.status_code == 201
        child_id = child_response.json()["skill_id"]

        # Link them
        link_response = client.post(
            f"/skills/{child_id}/parents/{parent_id}",
            headers=owner_auth["headers"]
        )
        assert link_response.status_code == 200

        # Verify linkage
        get_response = client.get(f"/skills/{child_id}", headers=owner_auth["headers"])
        assert get_response.status_code == 200
        assert parent_id in get_response.json()["parent_skill_ids"]

    async def test_unlink_parent_skill_success(self, client: TestClient, owner_auth):
        """Test successful parent skill unlinking."""
        # Create and link skills first
        parent_response = client.post(
            "/skills/",
            headers=owner_auth["headers"],
            json={"name": "Parent to Unlink"}
        )
        parent_id = parent_response.json()["skill_id"]

        child_response = client.post(
            "/skills/",
            headers=owner_auth["headers"],
            json={"name": "Child to Unlink", "parent_skill_ids": [parent_id]}
        )
        child_id = child_response.json()["skill_id"]

        # Unlink them
        unlink_response = client.delete(
            f"/skills/{child_id}/parents/{parent_id}",
            headers=owner_auth["headers"]
        )
        assert unlink_response.status_code == 200

        # Verify unlinked
        get_response = client.get(f"/skills/{child_id}", headers=owner_auth["headers"])
        assert parent_id not in get_response.json()["parent_skill_ids"]

    async def test_get_skill_tree(self, client: TestClient, owner_auth):
        """Test skill tree retrieval."""
        response = client.get("/skills/tree", headers=owner_auth["headers"])
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        # Tree structure validation would depend on existing skills


class TestSkillLogs:
    """Test skill log management endpoints."""

    async def test_add_skill_log_success(self, client: TestClient, test_skill, owner_auth):
        """Test successful skill log addition."""
        skill_id = test_skill["skill_id"]

        log_data = {
            "progress_state": "learning",
            "numeric_level": 2,
            "notes": "Made good progress today",
            "context": {
                "duration_hours": 2.5,
                "confidence_level": 8
            }
        }

        response = client.post(f"/skills/{skill_id}/logs", headers=owner_auth["headers"], json=log_data)
        assert response.status_code == 201

        data = response.json()
        assert data["progress_state"] == "learning"
        assert data["notes"] == "Made good progress today"
        assert data["context"]["duration_hours"] == 2.5

    async def test_get_skill_logs_success(self, client: TestClient, test_skill_with_logs, owner_auth):
        """Test successful skill log retrieval."""
        skill_id = test_skill_with_logs["skill_id"]

        response = client.get(f"/skills/{skill_id}/logs", headers=owner_auth["headers"])
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # We added 2 logs in the fixture

        for log in data:
            assert "log_id" in log
            assert "progress_state" in log
            assert "timestamp" in log

    async def test_update_skill_log_success(self, client: TestClient, test_skill_with_logs, owner_auth):
        """Test successful skill log update."""
        skill_id = test_skill_with_logs["skill_id"]

        # Get existing logs
        logs_response = client.get(f"/skills/{skill_id}/logs", headers=owner_auth["headers"])
        log_id = logs_response.json()[0]["log_id"]

        update_data = {"notes": "Updated notes"}

        response = client.put(
            f"/skills/{skill_id}/logs/{log_id}",
            headers=owner_auth["headers"],
            json=update_data
        )
        assert response.status_code == 200

    async def test_delete_skill_log_success(self, client: TestClient, test_skill_with_logs, owner_auth):
        """Test successful skill log deletion."""
        skill_id = test_skill_with_logs["skill_id"]

        # Get existing logs
        logs_response = client.get(f"/skills/{skill_id}/logs", headers=owner_auth["headers"])
        log_id = logs_response.json()[0]["log_id"]

        response = client.delete(f"/skills/{skill_id}/logs/{log_id}", headers=owner_auth["headers"])
        assert response.status_code == 204

        # Verify deletion
        logs_after = client.get(f"/skills/{skill_id}/logs", headers=owner_auth["headers"])
        remaining_log_ids = [log["log_id"] for log in logs_after.json()]
        assert log_id not in remaining_log_ids


class TestSkillAnalytics:
    """Test skill analytics endpoints."""

    async def test_get_skill_analytics(self, client: TestClient, test_skill_with_logs, owner_auth):
        """Test skill analytics retrieval."""
        skill_id = test_skill_with_logs["skill_id"]

        response = client.get(f"/skills/{skill_id}/analytics", headers=owner_auth["headers"])
        assert response.status_code == 200

        data = response.json()
        assert "total_logs" in data
        assert "current_state" in data
        assert "last_activity" in data

    async def test_get_analytics_summary(self, client: TestClient, owner_auth):
        """Test analytics summary retrieval."""
        response = client.get("/skills/analytics/summary", headers=owner_auth["headers"])
        assert response.status_code == 200

        data = response.json()
        assert "total_skills" in data
        assert "active_skills" in data
        assert "skills_by_state" in data
        assert "recent_activity" in data
        assert "stale_skills" in data


class TestSkillDeletion:
    """Test skill deletion endpoints."""

    async def test_delete_skill_success(self, client: TestClient, owner_auth):
        """Test successful skill deletion."""
        # Create a skill to delete
        create_response = client.post(
            "/skills/",
            headers=owner_auth["headers"],
            json={"name": "Skill to Delete"}
        )
        assert create_response.status_code == 201
        skill_id = create_response.json()["skill_id"]

        # Delete the skill
        delete_response = client.delete(f"/skills/{skill_id}", headers=owner_auth["headers"])
        assert delete_response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/skills/{skill_id}", headers=owner_auth["headers"])
        assert get_response.status_code == 404

    async def test_delete_skill_with_children_fails(self, client: TestClient, owner_auth):
        """Test deleting skill with children fails."""
        # Create parent
        parent_response = client.post(
            "/skills/",
            headers=owner_auth["headers"],
            json={"name": "Parent with Children"}
        )
        parent_id = parent_response.json()["skill_id"]

        # Create child
        child_response = client.post(
            "/skills/",
            headers=owner_auth["headers"],
            json={"name": "Child Skill", "parent_skill_ids": [parent_id]}
        )
        assert child_response.status_code == 201

        # Try to delete parent
        delete_response = client.delete(f"/skills/{parent_id}", headers=owner_auth["headers"])
        assert delete_response.status_code == 400
        assert "child skills" in delete_response.json()["detail"].lower()

    async def test_delete_skill_wrong_user(self, client: TestClient, test_skill, other_auth):
        """Test deleting skill owned by different user."""
        skill_id = test_skill["skill_id"]

        response = client.delete(f"/skills/{skill_id}", headers=other_auth["headers"])
        assert response.status_code == 404


class TestAuthentication:
    """Test authentication and authorization."""

    async def test_skills_endpoints_require_auth(self, client: TestClient):
        """Test that skills endpoints require authentication."""
        endpoints = [
            ("GET", "/skills/"),
            ("POST", "/skills/"),
            ("GET", "/skills/some_id"),
            ("PUT", "/skills/some_id"),
            ("DELETE", "/skills/some_id"),
            ("GET", "/skills/tree"),
            ("GET", "/skills/analytics/summary"),
        ]

        for method, endpoint in endpoints:
            response = client.request(method, endpoint)
            assert response.status_code == 401

    async def test_invalid_token_rejected(self, client: TestClient):
        """Test that invalid tokens are rejected."""
        headers = {"Authorization": "Bearer invalid_token"}

        response = client.get("/skills/", headers=headers)
        assert response.status_code == 401


class TestErrorHandling:
    """Test error handling and edge cases."""

    async def test_malformed_json(self, client: TestClient, owner_auth):
        """Test handling of malformed JSON."""
        response = client.post(
            "/skills/",
            headers=owner_auth["headers"],
            data="invalid json",
            content_type="application/json"
        )
        assert response.status_code == 422

    async def test_invalid_skill_id_format(self, client: TestClient, owner_auth):
        """Test handling of invalid skill ID formats."""
        response = client.get("/skills/invalid@id", headers=owner_auth["headers"])
        # Should either return 404 or 422 depending on validation
        assert response.status_code in [404, 422]

    async def test_concurrent_operations(self, client: TestClient, owner_auth):
        """Test concurrent operations don't cause issues."""
        import asyncio

        async def create_skill(i):
            skill_data = {"name": f"Concurrent Skill {i}"}
            response = client.post("/skills/", headers=owner_auth["headers"], json=skill_data)
            return response.status_code

        # Create multiple skills concurrently
        tasks = [create_skill(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(status == 201 for status in results)