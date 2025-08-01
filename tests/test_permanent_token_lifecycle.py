import pytest
from httpx import AsyncClient
from second_brain_database.main import app

import asyncio

@pytest.mark.asyncio
async def test_permanent_token_lifecycle():
    """
    Integration test for permanent token creation and retrieval.
    Pinpoints issues with token persistence and GET endpoint.
    """
    async with AsyncClient(base_url="http://localhost:8000") as ac:
        # 1. Register or login to get JWT (simulate or use test user)
        # For this test, assume a test user exists and we have a valid JWT
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyb2hhbmJhdHJhIiwiZXhwIjoxNzU0MDY2OTAyLCJpYXQiOjE3NTQwNjUxMDIsInRva2VuX3ZlcnNpb24iOjF9.-Pj5VlCasc2H2nSUsGmnaeowRSfeDqILcZQIgWJZ6KQ"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "User-Agent": "emotion_tracker/1.0.0",
        }

        # 2. Create a permanent token
        create_data = {
            "description": "Test integration token",
            "ip_restrictions": [],
            "expires_at": None
        }
        create_resp = await ac.post("/auth/permanent-tokens", json=create_data, headers=headers)
        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        token_data = create_resp.json()
        assert "token" in token_data, "No token returned on creation"
        token_id = token_data["token_id"]

        # 3. List permanent tokens
        list_resp = await ac.get("/auth/permanent-tokens", headers=headers)
        assert list_resp.status_code == 200, f"List failed: {list_resp.text}"
        tokens = list_resp.json().get("tokens", [])
        assert any(t["token_id"] == token_id for t in tokens), "Created token not found in list"

        # 4. Restart app (manual step if needed) and re-run list to check persistence
        # (You may need to run this part separately after restart)
        # list_resp2 = await ac.get("/auth/permanent-tokens", headers=headers)
        # assert list_resp2.status_code == 200
        # tokens2 = list_resp2.json().get("tokens", [])
        # assert any(t["token_id"] == token_id for t in tokens2), "Token not persisted after restart"

        # 5. Clean up: revoke the token
        del_resp = await ac.delete(f"/auth/permanent-tokens/{token_id}", headers=headers)
        assert del_resp.status_code == 200, f"Delete failed: {del_resp.text}"
        print("Permanent token lifecycle test passed.")
