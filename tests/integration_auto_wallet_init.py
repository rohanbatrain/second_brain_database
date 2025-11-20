#!/usr/bin/env python3
"""
Test script to verify auto-initialization of team wallets when workspaces are created.
"""

import asyncio
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from second_brain_database.config.config import settings
from second_brain_database.database.database import get_database
from second_brain_database.managers.team_wallet_manager import TeamWalletManager
from second_brain_database.managers.workspace_manager import WorkspaceManager


async def test_auto_wallet_initialization():
    """Test that wallets are automatically initialized when workspaces are created."""

    # Initialize managers
    db = get_database()
    workspace_manager = WorkspaceManager(db)
    wallet_manager = TeamWalletManager(db)

    # Create a test workspace
    test_user_id = "test_user_123"
    test_workspace_name = "Test Auto Wallet Workspace"

    print("Creating test workspace...")
    workspace = await workspace_manager.create_workspace(
        name=test_workspace_name, description="Test workspace for auto wallet initialization", owner_id=test_user_id
    )

    workspace_id = str(workspace["_id"])
    print(f"Created workspace: {workspace_id}")

    # Check if wallet was auto-initialized
    wallet_initialized = workspace.get("wallet_initialized", False)
    print(f"Wallet initialized flag: {wallet_initialized}")

    # Also check the sbd_account field directly
    sbd_account = workspace.get("sbd_account", {})
    account_username = sbd_account.get("account_username")
    print(f"SBD account username: {account_username}")

    # Verify wallet exists in wallet manager
    try:
        wallet_info = await wallet_manager.get_team_wallet_info(workspace_id, test_user_id)
        print(f"Wallet info retrieved successfully: {wallet_info.get('account_username')}")
        wallet_exists = True
    except Exception as e:
        print(f"Wallet retrieval failed: {e}")
        wallet_exists = False

    # Cleanup - delete test workspace
    print("Cleaning up test workspace...")
    await workspace_manager.delete_workspace(workspace_id, test_user_id)

    # Results
    success = wallet_initialized and account_username and wallet_exists
    print(f"\nTest Result: {'PASSED' if success else 'FAILED'}")
    print(f"- Wallet initialized flag: {wallet_initialized}")
    print(f"- SBD account exists: {bool(account_username)}")
    print(f"- Wallet retrievable: {wallet_exists}")

    return success


if __name__ == "__main__":
    success = asyncio.run(test_auto_wallet_initialization())
    sys.exit(0 if success else 1)
