#!/usr/bin/env python3
"""
Interactive User Agent lockdown testing script.

This script allows you to manually test User Agent lockdown functionality
by creating test users and simulating requests with different User Agents.
"""

import asyncio
from datetime import datetime, timedelta
import sys
from unittest.mock import MagicMock

from bson import ObjectId

# Add the src directory to the path
sys.path.insert(0, "src")

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager

logger = get_logger(prefix="[INTERACTIVE_UA_TEST]")


class InteractiveUserAgentTester:
    """Interactive tester for User Agent lockdown."""

    def __init__(self):
        self.users_collection = None
        self.current_user = None

    async def setup(self):
        """Setup the testing environment."""
        print("🔧 Setting up User Agent lockdown testing environment...")
        await db_manager.connect()
        self.users_collection = db_manager.get_collection("users")
        print("✅ Environment ready!")

    async def cleanup(self):
        """Clean up resources."""
        await db_manager.disconnect()
        print("🧹 Cleanup complete!")

    def create_mock_request(self, user_agent: str, ip: str = "192.168.1.100"):
        """Create a mock request with specified User Agent."""
        mock_request = MagicMock()
        mock_request.headers = {"user-agent": user_agent} if user_agent else {}
        mock_request.client = MagicMock()
        mock_request.client.host = ip
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/test"
        return mock_request

    async def create_test_user(self):
        """Create a new test user for User Agent lockdown testing."""
        print("\n📝 Creating a new test user...")

        # Get user preferences
        username = input("Enter username (or press Enter for auto-generated): ").strip()
        if not username:
            timestamp = int(datetime.utcnow().timestamp())
            username = f"ua_test_user_{timestamp}"

        email = input("Enter email (or press Enter for auto-generated): ").strip()
        if not email:
            timestamp = int(datetime.utcnow().timestamp())
            email = f"ua_test_{timestamp}@example.com"

        # Ask about User Agent lockdown
        enable_lockdown = input("Enable User Agent lockdown? (y/N): ").strip().lower() == "y"

        trusted_user_agents = []
        if enable_lockdown:
            print("\nEnter trusted User Agents (press Enter on empty line to finish):")
            while True:
                ua = input("User Agent: ").strip()
                if not ua:
                    break
                trusted_user_agents.append(ua)

        # Create user document
        user_id = ObjectId()
        user = {
            "_id": user_id,
            "username": username,
            "email": email,
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "trusted_user_agent_lockdown": enable_lockdown,
            "trusted_user_agents": trusted_user_agents,
            "trusted_user_agent_lockdown_codes": [],
            "temporary_user_agent_bypasses": [],
        }

        await self.users_collection.insert_one(user)
        self.current_user = user

        print(f"\n✅ Created user: {username}")
        print(f"   Email: {email}")
        print(f"   User Agent Lockdown: {'Enabled' if enable_lockdown else 'Disabled'}")
        if trusted_user_agents:
            print(f"   Trusted User Agents: {len(trusted_user_agents)}")
            for i, ua in enumerate(trusted_user_agents, 1):
                print(f"     {i}. {ua}")

        return user

    async def load_existing_user(self):
        """Load an existing user for testing."""
        print("\n🔍 Loading existing user...")

        search_term = input("Enter username or email to search: ").strip()
        if not search_term:
            print("❌ Search term required")
            return None

        # Search for user
        user = await self.users_collection.find_one(
            {
                "$or": [
                    {"username": {"$regex": search_term, "$options": "i"}},
                    {"email": {"$regex": search_term, "$options": "i"}},
                ]
            }
        )

        if not user:
            print(f"❌ No user found matching '{search_term}'")
            return None

        self.current_user = user
        print(f"\n✅ Loaded user: {user['username']}")
        print(f"   Email: {user['email']}")
        print(f"   User Agent Lockdown: {'Enabled' if user.get('trusted_user_agent_lockdown', False) else 'Disabled'}")

        trusted_uas = user.get("trusted_user_agents", [])
        if trusted_uas:
            print(f"   Trusted User Agents: {len(trusted_uas)}")
            for i, ua in enumerate(trusted_uas, 1):
                print(f"     {i}. {ua}")

        return user

    async def test_user_agent_access(self):
        """Test access with a specific User Agent."""
        if not self.current_user:
            print("❌ No user selected. Please create or load a user first.")
            return

        print(f"\n🧪 Testing User Agent access for user: {self.current_user['username']}")

        # Get User Agent to test
        user_agent = input("Enter User Agent to test (or press Enter for common examples): ").strip()

        if not user_agent:
            # Show common User Agent examples
            common_uas = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
                "curl/7.68.0",
                "Python-urllib/3.8",
                "BadBot/1.0",
            ]

            print("\nCommon User Agent examples:")
            for i, ua in enumerate(common_uas, 1):
                print(f"  {i}. {ua}")

            choice = input("\nSelect a number (1-6) or enter custom User Agent: ").strip()

            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(common_uas):
                    user_agent = common_uas[choice_num - 1]
                else:
                    print("❌ Invalid choice")
                    return
            except ValueError:
                user_agent = choice

        if not user_agent:
            print("❌ User Agent required")
            return

        print(f"\n🔍 Testing User Agent: {user_agent}")

        # Create mock request
        request = self.create_mock_request(user_agent)

        # Test the User Agent lockdown
        try:
            await security_manager.check_user_agent_lockdown(request, self.current_user)
            print("✅ ACCESS GRANTED - User Agent is allowed")

            # Show why it was allowed
            if not self.current_user.get("trusted_user_agent_lockdown", False):
                print("   Reason: User Agent lockdown is disabled")
            elif user_agent in self.current_user.get("trusted_user_agents", []):
                print("   Reason: User Agent is in trusted list")
            else:
                print("   Reason: Temporary bypass or other exception")

        except Exception as e:
            print("❌ ACCESS DENIED - User Agent is blocked")
            print(f"   Reason: {str(e)}")

            # Show why it was blocked
            if self.current_user.get("trusted_user_agent_lockdown", False):
                trusted_uas = self.current_user.get("trusted_user_agents", [])
                if not trusted_uas:
                    print("   Details: No trusted User Agents configured")
                else:
                    print("   Details: User Agent not in trusted list")
                    print(f"   Trusted User Agents: {trusted_uas}")

    async def modify_user_agent_settings(self):
        """Modify User Agent lockdown settings for current user."""
        if not self.current_user:
            print("❌ No user selected. Please create or load a user first.")
            return

        print(f"\n⚙️  Modifying User Agent settings for: {self.current_user['username']}")

        current_lockdown = self.current_user.get("trusted_user_agent_lockdown", False)
        current_trusted = self.current_user.get("trusted_user_agents", [])

        print(f"Current lockdown status: {'Enabled' if current_lockdown else 'Disabled'}")
        print(f"Current trusted User Agents: {len(current_trusted)}")

        # Ask what to modify
        print("\nWhat would you like to do?")
        print("1. Toggle User Agent lockdown on/off")
        print("2. Add trusted User Agent")
        print("3. Remove trusted User Agent")
        print("4. Clear all trusted User Agents")
        print("5. Add temporary bypass")

        choice = input("Enter choice (1-5): ").strip()

        if choice == "1":
            new_lockdown = not current_lockdown
            await self.users_collection.update_one(
                {"_id": self.current_user["_id"]}, {"$set": {"trusted_user_agent_lockdown": new_lockdown}}
            )
            self.current_user["trusted_user_agent_lockdown"] = new_lockdown
            print(f"✅ User Agent lockdown {'enabled' if new_lockdown else 'disabled'}")

        elif choice == "2":
            new_ua = input("Enter User Agent to add: ").strip()
            if new_ua and new_ua not in current_trusted:
                await self.users_collection.update_one(
                    {"_id": self.current_user["_id"]}, {"$push": {"trusted_user_agents": new_ua}}
                )
                self.current_user["trusted_user_agents"].append(new_ua)
                print(f"✅ Added trusted User Agent: {new_ua}")
            else:
                print("❌ Invalid or duplicate User Agent")

        elif choice == "3":
            if not current_trusted:
                print("❌ No trusted User Agents to remove")
                return

            print("Current trusted User Agents:")
            for i, ua in enumerate(current_trusted, 1):
                print(f"  {i}. {ua}")

            try:
                remove_idx = int(input("Enter number to remove: ")) - 1
                if 0 <= remove_idx < len(current_trusted):
                    ua_to_remove = current_trusted[remove_idx]
                    await self.users_collection.update_one(
                        {"_id": self.current_user["_id"]}, {"$pull": {"trusted_user_agents": ua_to_remove}}
                    )
                    self.current_user["trusted_user_agents"].remove(ua_to_remove)
                    print(f"✅ Removed trusted User Agent: {ua_to_remove}")
                else:
                    print("❌ Invalid selection")
            except ValueError:
                print("❌ Invalid number")

        elif choice == "4":
            confirm = input("Are you sure you want to clear all trusted User Agents? (y/N): ").strip().lower()
            if confirm == "y":
                await self.users_collection.update_one(
                    {"_id": self.current_user["_id"]}, {"$set": {"trusted_user_agents": []}}
                )
                self.current_user["trusted_user_agents"] = []
                print("✅ Cleared all trusted User Agents")
            else:
                print("❌ Cancelled")

        elif choice == "5":
            bypass_ua = input("Enter User Agent for temporary bypass: ").strip()
            if not bypass_ua:
                print("❌ User Agent required")
                return

            try:
                minutes = int(input("Enter bypass duration in minutes (default 5): ") or "5")
            except ValueError:
                minutes = 5

            bypass = {
                "user_agent": bypass_ua,
                "expires_at": (datetime.utcnow() + timedelta(minutes=minutes)).isoformat(),
                "created_at": datetime.utcnow().isoformat(),
                "reason": "manual_test_bypass",
            }

            await self.users_collection.update_one(
                {"_id": self.current_user["_id"]}, {"$push": {"temporary_user_agent_bypasses": bypass}}
            )

            if "temporary_user_agent_bypasses" not in self.current_user:
                self.current_user["temporary_user_agent_bypasses"] = []
            self.current_user["temporary_user_agent_bypasses"].append(bypass)

            print(f"✅ Added temporary bypass for '{bypass_ua}' (expires in {minutes} minutes)")

        else:
            print("❌ Invalid choice")

    async def show_user_info(self):
        """Show detailed information about current user."""
        if not self.current_user:
            print("❌ No user selected. Please create or load a user first.")
            return

        user = await self.users_collection.find_one({"_id": self.current_user["_id"]})
        if not user:
            print("❌ User not found in database")
            return

        self.current_user = user  # Refresh current user data

        print(f"\n👤 User Information: {user['username']}")
        print(f"   Email: {user['email']}")
        print(f"   Created: {user['created_at']}")
        print(f"   Active: {user.get('is_active', False)}")

        print(f"\n🔒 User Agent Lockdown Settings:")
        print(f"   Enabled: {user.get('trusted_user_agent_lockdown', False)}")

        trusted_uas = user.get("trusted_user_agents", [])
        print(f"   Trusted User Agents: {len(trusted_uas)}")
        for i, ua in enumerate(trusted_uas, 1):
            print(f"     {i}. {ua}")

        bypasses = user.get("temporary_user_agent_bypasses", [])
        if bypasses:
            print(f"\n⏰ Temporary Bypasses: {len(bypasses)}")
            current_time = datetime.utcnow().isoformat()
            for i, bypass in enumerate(bypasses, 1):
                status = "Active" if bypass.get("expires_at", "") > current_time else "Expired"
                print(
                    f"     {i}. {bypass.get('user_agent', 'Unknown')} - {status} (expires: {bypass.get('expires_at', 'Unknown')})"
                )

    async def cleanup_test_data(self):
        """Clean up test users created during this session."""
        print("\n🧹 Cleaning up test data...")

        confirm = input("Delete all test users created with 'ua_test_user_' prefix? (y/N): ").strip().lower()
        if confirm != "y":
            print("❌ Cancelled")
            return

        result = await self.users_collection.delete_many({"username": {"$regex": "^ua_test_user_"}})

        print(f"✅ Deleted {result.deleted_count} test users")

    async def run_interactive_session(self):
        """Run the interactive testing session."""
        print("🚀 Interactive User Agent Lockdown Tester")
        print("=" * 50)

        await self.setup()

        try:
            while True:
                print("\n📋 Main Menu:")
                print("1. Create new test user")
                print("2. Load existing user")
                print("3. Test User Agent access")
                print("4. Modify User Agent settings")
                print("5. Show current user info")
                print("6. Cleanup test data")
                print("7. Exit")

                choice = input("\nEnter your choice (1-7): ").strip()

                if choice == "1":
                    await self.create_test_user()
                elif choice == "2":
                    await self.load_existing_user()
                elif choice == "3":
                    await self.test_user_agent_access()
                elif choice == "4":
                    await self.modify_user_agent_settings()
                elif choice == "5":
                    await self.show_user_info()
                elif choice == "6":
                    await self.cleanup_test_data()
                elif choice == "7":
                    print("👋 Goodbye!")
                    break
                else:
                    print("❌ Invalid choice. Please try again.")

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!")
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
        finally:
            await self.cleanup()


async def main():
    """Main entry point."""
    tester = InteractiveUserAgentTester()
    await tester.run_interactive_session()


if __name__ == "__main__":
    asyncio.run(main())
