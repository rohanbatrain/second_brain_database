#!/usr/bin/env python3
"""
Test Database Connection

This script tests the database connection to help diagnose the MCP database issue.
"""

import asyncio
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_database_connection():
    """Test database connection and provide diagnostics."""
    print("🔍 Testing database connection...")

    try:
        # Test 1: Import database manager
        print("1. Importing database manager...")
        from second_brain_database.database import db_manager

        print("   ✅ Database manager imported successfully")

        # Test 2: Connect to database
        print("2. Connecting to database...")
        try:
            if not hasattr(db_manager, "client") or db_manager.client is None:
                print("   📡 Database not connected, connecting now...")
                await db_manager.connect()
                print("   ✅ Database connected successfully")
            else:
                print("   ✅ Database already connected")
        except Exception as e:
            print(f"   ❌ Database connection error: {e}")
            return False

        # Test 3: Check if database is healthy
        print("3. Checking database health...")
        try:
            is_connected = await db_manager.health_check()
            if is_connected:
                print("   ✅ Database connection is healthy")
            else:
                print("   ❌ Database health check failed")
                return False
        except Exception as e:
            print(f"   ❌ Database health check error: {e}")
            return False

        # Test 4: Try to get a collection
        print("4. Testing collection access...")
        try:
            users_collection = db_manager.get_collection("users")
            print("   ✅ Users collection accessed successfully")
        except Exception as e:
            print(f"   ❌ Collection access error: {e}")
            return False

        # Test 5: Try a simple query
        print("5. Testing database query...")
        try:
            # Try to count documents (should work even if collection is empty)
            count = await users_collection.count_documents({})
            print(f"   ✅ Query successful - Users collection has {count} documents")
        except Exception as e:
            print(f"   ❌ Query error: {e}")
            return False

        # Test 6: Test MCP database integration
        print("6. Testing MCP database integration...")
        try:
            from second_brain_database.integrations.mcp.database_integration import initialize_mcp_database

            mcp_db_initialized = await initialize_mcp_database()
            if mcp_db_initialized:
                print("   ✅ MCP database integration initialized successfully")
            else:
                print("   ❌ MCP database integration failed")
                return False
        except Exception as e:
            print(f"   ❌ MCP database integration error: {e}")
            return False

        print("\n🎉 All database tests passed!")
        return True

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False


async def test_family_manager():
    """Test family manager initialization."""
    print("\n🔍 Testing family manager...")

    try:
        # Import family manager
        from second_brain_database.database import db_manager
        from second_brain_database.managers.family_manager import FamilyManager
        from second_brain_database.managers.redis_manager import redis_manager
        from second_brain_database.managers.security_manager import security_manager

        print("1. Creating family manager instance...")
        family_manager = FamilyManager(
            db_manager=db_manager, security_manager=security_manager, redis_manager=redis_manager
        )
        print("   ✅ Family manager created successfully")

        # Test family limits check (this is where the error occurs)
        print("2. Testing family limits check...")
        try:
            # This should trigger the database connection check
            limits_result = await family_manager.check_family_limits("test-user-id")
            print("   ✅ Family limits check completed")
        except Exception as e:
            print(f"   ❌ Family limits check failed: {e}")
            return False

        print("✅ Family manager tests passed!")
        return True

    except Exception as e:
        print(f"❌ Family manager test failed: {e}")
        return False


async def main():
    """Main test function."""
    print("🚀 Database Connection Test Suite")
    print("=" * 50)

    # Test database connection
    db_success = await test_database_connection()

    if db_success:
        # Test family manager
        fm_success = await test_family_manager()

        if fm_success:
            print("\n🎉 All tests passed! Database and family manager are working correctly.")
            print("\n💡 If MCP tools are still failing, the issue might be:")
            print("   1. Database connection timing during MCP server startup")
            print("   2. Different database connection context in MCP vs FastAPI")
            print("   3. Missing database initialization in MCP server lifecycle")
        else:
            print("\n❌ Family manager tests failed.")
    else:
        print("\n❌ Database connection tests failed.")
        print("\n🔧 Troubleshooting steps:")
        print("   1. Make sure MongoDB is running:")
        print("      brew services start mongodb-community")
        print("      # or")
        print("      sudo systemctl start mongod")
        print("   2. Check MongoDB connection string in .sbd file")
        print("   3. Verify MongoDB is listening on port 27017:")
        print("      netstat -an | grep 27017")


if __name__ == "__main__":
    asyncio.run(main())
