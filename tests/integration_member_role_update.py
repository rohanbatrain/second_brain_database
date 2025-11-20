#!/usr/bin/env python3
"""
Simple test script to verify the member role update functionality works.
"""
import asyncio
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import uuid

from fastapi.testclient import TestClient

from second_brain_database.database import db_manager
from second_brain_database.main import app


async def test_member_role_update():
    """Test the member role update functionality."""
    print("Testing member role update functionality...")

    # Create test client
    client = TestClient(app)

    # Create test users
    owner_data = {
        "username": f"test_owner_{uuid.uuid4().hex[:8]}",
        "email": f"test_owner_{uuid.uuid4().hex[:8]}@example.com",
        "password": "TestPass123!",
    }

    member_data = {
        "username": f"test_member_{uuid.uuid4().hex[:8]}",
        "email": f"test_member_{uuid.uuid4().hex[:8]}@example.com",
        "password": "TestPass123!",
    }

    # Register and verify users
    for user_data in [owner_data, member_data]:
        # Register
        response = client.post("/auth/register", json=user_data)
        if response.status_code != 200:
            print(f"Failed to register user: {response.text}")
            return False

        # Get verification token from DB
        users_collection = db_manager.get_collection("users")
        user_doc = await users_collection.find_one({"email": user_data["email"]})
        if not user_doc:
            print(f"User not found in DB: {user_data['email']}")
            return False

        verification_token = user_doc.get("email_verification_token")
        if not verification_token:
            print(f"No verification token for user: {user_data['email']}")
            return False

        # Verify email
        response = client.get(f"/auth/verify-email?token={verification_token}")
        if response.status_code != 200:
            print(f"Failed to verify email: {response.text}")
            return False

    # Login users
    owner_login = client.post(
        "/auth/login", data={"username": owner_data["username"], "password": owner_data["password"]}
    )
    if owner_login.status_code != 200:
        print(f"Owner login failed: {owner_login.text}")
        return False

    member_login = client.post(
        "/auth/login", data={"username": member_data["username"], "password": member_data["password"]}
    )
    if member_login.status_code != 200:
        print(f"Member login failed: {member_login.text}")
        return False

    owner_token = owner_login.json()["access_token"]
    member_token = member_login.json()["access_token"]

    # Create workspace
    create_response = client.post(
        "/workspaces/",
        json={"name": "Test Workspace", "description": "A test workspace"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    if create_response.status_code != 200:
        print(f"Failed to create workspace: {create_response.text}")
        return False

    workspace_data = create_response.json()
    workspace_id = workspace_data["workspace_id"]
    print(f"Created workspace: {workspace_id}")

    # Add member to workspace
    add_response = client.post(
        f"/workspaces/{workspace_id}/members",
        json={"user_id_to_add": member_data["username"], "role": "editor"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    if add_response.status_code != 200:
        print(f"Failed to add member: {add_response.text}")
        return False

    print("Added member to workspace")

    # Update member role
    update_response = client.put(
        f"/workspaces/{workspace_id}/members/{member_data['username']}",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    if update_response.status_code != 200:
        print(f"Failed to update member role: {update_response.text}")
        return False

    updated_workspace = update_response.json()
    print(f"Updated member role successfully")

    # Verify the role was updated
    member_found = False
    for member in updated_workspace["members"]:
        if member["user_id"] == member_data["username"]:
            if member["role"] == "viewer":
                print("✅ Member role update verified successfully!")
                member_found = True
                break
            else:
                print(f"❌ Role not updated correctly. Expected 'viewer', got '{member['role']}'")
                return False

    if not member_found:
        print("❌ Member not found in updated workspace")
        return False

    print("🎉 All tests passed! Member role update functionality is working.")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_member_role_update())
    sys.exit(0 if success else 1)
