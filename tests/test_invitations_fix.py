#!/usr/bin/env python3
"""
Simple test to verify get_family_invitations fix
"""

import asyncio
from datetime import datetime, timezone
import sys
import uuid

# Add the src directory to the path
sys.path.insert(0, "src")

from second_brain_database.database import db_manager
from second_brain_database.managers.family_manager import family_manager


async def test_get_family_invitations():
    """Test that get_family_invitations returns invitations with proper enrichment."""
    try:
        print("Testing get_family_invitations fix...")

        # Use existing family from database
        family_id = "fam_3f710ce1562b4798"
        admin_user_id = "68fa58425b23fa650c712534"  # From the existing family data

        print(f"Testing with existing family: {family_id}")

        # Test get_family_invitations
        print("Testing get_family_invitations...")
        invitations = await family_manager.get_family_invitations(family_id, admin_user_id)

        print(f"Retrieved {len(invitations)} invitations")

        if len(invitations) == 0:
            print("❌ FAIL: No invitations returned")
            return False

        # Check if our invitation is in the results
        found_invitation = None
        for inv in invitations:
            if inv.get("invitation_id") == "inv_4125936f05fd41c5":  # From the database
                found_invitation = inv
                break

        if not found_invitation:
            print("❌ FAIL: Expected invitation not found in results")
            print("Available invitations:")
            for inv in invitations:
                print(f"  - {inv.get('invitation_id')}: {inv.get('invitee_email')}")
            return False

        print("✓ PASS: Invitation found in results")

        # Check required fields for filtering
        required_fields = ["invitee_email", "invitee_username", "inviter_username", "family_name"]
        missing_fields = []

        for field in required_fields:
            if field not in found_invitation:
                missing_fields.append(field)
            elif found_invitation[field] in ["Unknown", "Unknown Family"]:
                missing_fields.append(f"{field} (has 'Unknown' value)")

        if missing_fields:
            print(f"❌ FAIL: Missing or invalid fields: {missing_fields}")
            print(f"Invitation data: {found_invitation}")
            return False

        print("✓ PASS: All required fields present and valid")
        print(
            f"Invitation details: inviter_username={found_invitation['inviter_username']}, family_name={found_invitation['family_name']}"
        )

        return True

    except Exception as e:
        print(f"❌ FAIL: Exception during test: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    try:
        print("Initializing database connection...")
        await db_manager.initialize()

        success = await test_get_family_invitations()

        if success:
            print("\n🎉 SUCCESS: get_family_invitations fix is working!")
        else:
            print("\n💥 FAILURE: get_family_invitations fix needs more work")

        return success

    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        print("Closing database connection...")
        await db_manager.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
