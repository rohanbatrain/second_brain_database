#!/usr/bin/env python3
"""
Test script to verify family management system setup.
"""

import asyncio
from datetime import datetime
import sys


async def test_family_models():
    """Test that family models can be imported and used."""
    try:
        from src.second_brain_database.routes.family.models import (
            CreateFamilyRequest,
            FamilyDocument,
            FamilyResponse,
            InvitationStatus,
            InviteMemberRequest,
            NotificationType,
        )

        print("✅ Successfully imported family models")

        # Test model creation
        create_request = CreateFamilyRequest(name="Test Family")
        print(f"✅ CreateFamilyRequest works: {create_request.name}")

        # Test enum values
        print(f"✅ NotificationType enum works: {NotificationType.SBD_SPEND}")
        print(f"✅ InvitationStatus enum works: {InvitationStatus.PENDING}")

        return True

    except Exception as e:
        print(f"❌ Failed to import or use family models: {e}")
        return False


async def test_database_connection():
    """Test database connection and collection creation."""
    try:
        from src.second_brain_database.database import db_manager

        await db_manager.connect()
        print("✅ Database connection successful")

        # Try to create family collections
        collections_to_create = [
            "families",
            "family_relationships",
            "family_invitations",
            "family_notifications",
            "family_token_requests",
        ]

        created_collections = []
        for collection_name in collections_to_create:
            try:
                await db_manager.database.create_collection(collection_name)
                created_collections.append(collection_name)
                print(f"✅ Created collection: {collection_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    created_collections.append(collection_name)
                    print(f"✅ Collection already exists: {collection_name}")
                else:
                    print(f"⚠️  Issue with collection {collection_name}: {e}")

        # Verify collections exist
        all_collections = await db_manager.database.list_collection_names()

        # Check for all expected family management collections
        expected_collections = {
            "families",
            "family_relationships",
            "family_invitations",
            "family_notifications",
            "family_token_requests",
        }
        found_collections = set(all_collections)
        family_management_collections = expected_collections.intersection(found_collections)
        missing_collections = expected_collections - found_collections

        print(f"✅ Family management collections found: {sorted(family_management_collections)}")

        if missing_collections:
            print(f"⚠️  Missing collections: {sorted(missing_collections)}")
        else:
            print("✅ All expected family management collections exist")

        await db_manager.disconnect()
        print("✅ Database disconnection successful")

        # Success if all expected collections exist
        return len(missing_collections) == 0

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False


async def test_migration_script():
    """Test that migration script can be imported."""
    try:
        from src.second_brain_database.migrations.family_collections_migration import FamilyCollectionsMigration

        migration = FamilyCollectionsMigration()
        print("✅ Migration script imported successfully")
        print(f"✅ Collections to create: {migration.collections_to_create}")

        return True

    except Exception as e:
        print(f"❌ Failed to import migration script: {e}")
        return False


async def main():
    """Run all tests."""
    print("🧪 Testing Family Management System Setup")
    print("=" * 50)

    tests = [
        ("Family Models", test_family_models),
        ("Database Connection", test_database_connection),
        ("Migration Script", test_migration_script),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}...")
        try:
            result = await test_func()
            results.append(result)
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {status}")
        except Exception as e:
            print(f"   ❌ FAILED with exception: {e}")
            results.append(False)

    print("\n" + "=" * 50)
    print("📊 Test Summary:")

    passed = sum(results)
    total = len(results)

    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASSED" if results[i] else "❌ FAILED"
        print(f"   {test_name}: {status}")

    print(f"\n🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Family management system setup is complete.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
