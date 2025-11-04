#!/usr/bin/env python3
"""
Test script to verify WebAuthn database collections and indexes are set up correctly.
"""
import asyncio
from datetime import datetime, timedelta
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src", "second_brain_database"))

from src.second_brain_database.database import db_manager
from src.second_brain_database.routes.auth.models import WebAuthnChallengeDocument, WebAuthnCredentialDocument


async def test_webauthn_db_setup():
    """Test WebAuthn database setup including collections and indexes."""
    try:
        # Connect to database
        print("Connecting to database...")
        await db_manager.connect()
        print("✓ Database connected successfully")

        # Create indexes
        print("Creating database indexes...")
        await db_manager.create_indexes()
        print("✓ Database indexes created successfully")

        # Test WebAuthn credentials collection
        print("Testing webauthn_credentials collection...")
        creds_collection = db_manager.get_collection("webauthn_credentials")

        # List indexes for webauthn_credentials
        creds_indexes = await creds_collection.list_indexes().to_list(length=None)
        print(f"✓ webauthn_credentials collection has {len(creds_indexes)} indexes:")
        for idx in creds_indexes:
            print(f"  - {idx['name']}: {idx.get('key', {})}")

        # Test WebAuthn challenges collection
        print("Testing webauthn_challenges collection...")
        challenges_collection = db_manager.get_collection("webauthn_challenges")

        # List indexes for webauthn_challenges
        challenges_indexes = await challenges_collection.list_indexes().to_list(length=None)
        print(f"✓ webauthn_challenges collection has {len(challenges_indexes)} indexes:")
        for idx in challenges_indexes:
            print(f"  - {idx['name']}: {idx.get('key', {})}")

        # Test inserting a sample credential document
        print("Testing credential document insertion...")
        test_cred = WebAuthnCredentialDocument(
            user_id="507f1f77bcf86cd799439011",
            credential_id="test_credential_id_12345",
            public_key="test_public_key_data",
            device_name="Test Device",
            authenticator_type="platform",
            transport=["internal"],
            aaguid="00000000-0000-0000-0000-000000000000",
        )

        result = await creds_collection.insert_one(test_cred.model_dump())
        print(f"✓ Test credential inserted with ID: {result.inserted_id}")

        # Test inserting a sample challenge document
        print("Testing challenge document insertion...")
        test_challenge = WebAuthnChallengeDocument(
            challenge="test_challenge_12345",
            user_id="507f1f77bcf86cd799439011",
            type="registration",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )

        result = await challenges_collection.insert_one(test_challenge.model_dump())
        print(f"✓ Test challenge inserted with ID: {result.inserted_id}")

        # Clean up test data
        print("Cleaning up test data...")
        await creds_collection.delete_one({"credential_id": "test_credential_id_12345"})
        await challenges_collection.delete_one({"challenge": "test_challenge_12345"})
        print("✓ Test data cleaned up")

        print("\n🎉 All WebAuthn database setup tests passed!")

    except Exception as e:
        print(f"❌ Error during database setup test: {e}")
        raise
    finally:
        # Disconnect from database
        await db_manager.disconnect()
        print("✓ Database disconnected")


if __name__ == "__main__":
    asyncio.run(test_webauthn_db_setup())
