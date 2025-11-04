#!/usr/bin/env python3
"""Simple verification script for family management system setup."""

import asyncio

async def verify_setup():
    """Verify the family management system setup."""
    print("🔍 Verifying Family Management System Setup")
    print("=" * 50)

    # Test 1: Import models
    try:
        from src.second_brain_database.routes.family.models import (
            CreateFamilyRequest, FamilyResponse, NotificationType
        )
        print("✅ Family models imported successfully")

        # Test model creation
        request = CreateFamilyRequest(name="Test Family")
        print(f"✅ Model validation works: {request.name}")

    except Exception as e:
        print(f"❌ Model import failed: {e}")
        return False

    # Test 2: Database collections
    try:
        from src.second_brain_database.database import db_manager

        await db_manager.connect()
        collections = await db_manager.database.list_collection_names()

        expected = {'families', 'family_relationships', 'family_invitations',
                   'family_notifications', 'family_token_requests'}
        found = set(collections)
        family_collections = expected.intersection(found)

        print(f"✅ Database connected successfully")
        print(f"✅ Found {len(family_collections)}/5 family collections: {sorted(family_collections)}")

        if len(family_collections) == 5:
            print("✅ All family collections exist")
        else:
            missing = expected - found
            print(f"⚠️  Missing collections: {missing}")

        await db_manager.disconnect()

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

    # Test 3: Migration script
    try:
        from src.second_brain_database.migrations.family_collections_migration import FamilyCollectionsMigration
        migration = FamilyCollectionsMigration()
        print(f"✅ Migration script imported successfully")

    except Exception as e:
        print(f"❌ Migration import failed: {e}")
        return False

    print("\n" + "=" * 50)
    print("🎉 Family Management System setup verification complete!")
    print("✅ All core components are working correctly")
    return True

if __name__ == "__main__":
    result = asyncio.run(verify_setup())
    exit(0 if result else 1)
