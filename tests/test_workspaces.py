import uuid

from fastapi.testclient import TestClient
import jwt
import pytest

from second_brain_database.database import db_manager
from second_brain_database.main import app

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
def client():
    """Provides a test client for the application for the whole session."""
    with TestClient(app) as c:
        yield c


# --- User Data Fixtures (can be module-scoped) ---


@pytest.fixture(scope="module")
def owner_user_data():
    return {
        "username": f"owner_{uuid.uuid4().hex}",
        "email": f"owner_{uuid.uuid4().hex}@example.com",
        "password": "Str0ngP@ssw0rd!",
    }


@pytest.fixture(scope="module")
def member_user_data():
    return {
        "username": f"member_{uuid.uuid4().hex}",
        "email": f"member_{uuid.uuid4().hex}@example.com",
        "password": "Str0ngP@ssw0rd!",
    }


@pytest.fixture(scope="module")
def non_member_user_data():
    return {
        "username": f"nonmember_{uuid.uuid4().hex}",
        "email": f"nonmember_{uuid.uuid4().hex}@example.com",
        "password": "Str0ngP@ssw0rd!",
    }


# --- Verified User and Auth Header Fixtures (function-scoped) ---


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
    return await create_and_verify_user(client, owner_user_data)


@pytest.fixture
async def member_auth(client, member_user_data):
    return await create_and_verify_user(client, member_user_data)


@pytest.fixture
async def non_member_auth(client, non_member_user_data):
    return await create_and_verify_user(client, non_member_user_data)


# --- Workspace Test Fixture (function-scoped) ---


@pytest.fixture
async def test_workspace(client, owner_auth, member_auth):
    """Creates a workspace and adds a member for testing access control."""
    create_response = client.post(
        "/workspaces/",
        headers=owner_auth["headers"],
        json={"name": "Shared Test Workspace", "description": "A workspace for access tests"},
    )
    assert create_response.status_code == 201
    workspace_data = create_response.json()
    workspace_id = workspace_data["workspace_id"]

    add_member_response = client.post(
        f"/workspaces/{workspace_id}/members",
        headers=owner_auth["headers"],
        json={"user_id_to_add": member_auth["user_id"], "role": "editor"},
    )
    assert add_member_response.status_code == 200

    return {"workspace_id": workspace_id, "owner_id": owner_auth["user_id"], "member_id": member_auth["user_id"]}


# --- Test Classes ---


class TestWorkspaceCreation:
    async def test_create_workspace_success(self, client: TestClient, owner_auth):
        response = client.post(
            "/workspaces/",
            headers=owner_auth["headers"],
            json={"name": "Creation Success Test", "description": "A test workspace"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Creation Success Test"
        assert data["owner_id"] == owner_auth["user_id"]
        assert len(data["members"]) == 1
        assert data["members"][0]["role"] == "admin"

    async def test_create_workspace_invalid_name(self, client: TestClient, owner_auth):
        response = client.post("/workspaces/", headers=owner_auth["headers"], json={"name": "a"})
        assert response.status_code == 422


class TestWorkspaceAccess:
    async def test_get_workspace_as_member_success(self, client: TestClient, owner_auth, test_workspace):
        response = client.get(f"/workspaces/{test_workspace['workspace_id']}", headers=owner_auth["headers"])
        assert response.status_code == 200
        assert response.json()["workspace_id"] == test_workspace["workspace_id"]

    async def test_get_workspace_as_non_member_fail(self, client: TestClient, non_member_auth, test_workspace):
        response = client.get(f"/workspaces/{test_workspace['workspace_id']}", headers=non_member_auth["headers"])
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"


class TestMemberManagement:
    async def test_add_member_as_non_admin_fail(self, client: TestClient, member_auth, non_member_auth, test_workspace):
        response = client.post(
            f"/workspaces/{test_workspace['workspace_id']}/members",
            headers=member_auth["headers"],  # Using member's headers
            json={"user_id_to_add": non_member_auth["user_id"], "role": "viewer"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"

    async def test_remove_owner_fail(self, client: TestClient, owner_auth, test_workspace):
        response = client.delete(
            f"/workspaces/{test_workspace['workspace_id']}/members/{test_workspace['owner_id']}",
            headers=owner_auth["headers"],
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "OWNER_CANNOT_BE_REMOVED"


class TestWorkspaceUpdate:
    async def test_update_workspace_success(self, client: TestClient, owner_auth, test_workspace):
        response = client.put(
            f"/workspaces/{test_workspace['workspace_id']}",
            headers=owner_auth["headers"],
            json={"name": "Updated Workspace Name", "description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Workspace Name"
        assert data["description"] == "Updated description"

    async def test_update_workspace_as_non_admin_fail(self, client: TestClient, member_auth, test_workspace):
        response = client.put(
            f"/workspaces/{test_workspace['workspace_id']}",
            headers=member_auth["headers"],
            json={"name": "Should Not Update"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"


class TestWorkspaceDeletion:
    async def test_delete_workspace_success(self, client: TestClient, owner_auth):
        # Create a workspace to delete
        create_response = client.post(
            "/workspaces/",
            headers=owner_auth["headers"],
            json={"name": "Workspace to Delete", "description": "Will be deleted"},
        )
        assert create_response.status_code == 201
        workspace_id = create_response.json()["workspace_id"]

        # Delete the workspace
        delete_response = client.delete(f"/workspaces/{workspace_id}", headers=owner_auth["headers"])
        assert delete_response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/workspaces/{workspace_id}", headers=owner_auth["headers"])
        assert get_response.status_code == 404

    async def test_delete_workspace_as_non_owner_fail(self, client: TestClient, member_auth, test_workspace):
        response = client.delete(f"/workspaces/{test_workspace['workspace_id']}", headers=member_auth["headers"])
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"
