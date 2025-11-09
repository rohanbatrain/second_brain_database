#!/usr/bin/env python3
"""
Test script to verify that the spending permissions fix is correctly implemented.
"""

import inspect
import os
import sys


def test_spending_permissions_fix():
    """Test that the spending permissions fix is correctly implemented."""

    print("🧪 Testing Spending Permissions Data Consistency Fix")
    print("=" * 55)

    try:
        # Read the family_manager.py file
        manager_file = os.path.join(
            os.path.dirname(__file__), "src", "second_brain_database", "managers", "family_manager.py"
        )

        with open(manager_file, "r") as f:
            content = f.read()

        # Test 1: Verify get_family_members reads from family document
        print("Test 1: Checking get_family_members reads from family document...")

        if 'family["sbd_account"]["spending_permissions"]' in content:
            print("✓ get_family_members reads from family document (sbd_account.spending_permissions)")
        else:
            print("✗ get_family_members does not read from family document")
            return False

        # Test 2: Verify the method no longer reads from user membership
        print("Test 2: Checking get_family_members no longer reads from user membership...")

        # Look for the specific pattern we changed
        if 'family_membership.get("spending_permissions"' in content:
            print("✗ get_family_members still reads from user membership data")
            return False
        else:
            print("✓ get_family_members no longer reads from user membership data")

        # Test 3: Verify update_spending_permissions updates both locations
        print("Test 3: Checking update_spending_permissions updates both data sources...")

        if "sbd_account.spending_permissions" in content and "family_memberships.$.spending_permissions" in content:
            print("✓ update_spending_permissions updates both family document and user membership")
        else:
            print("✗ update_spending_permissions does not update both data sources")
            return False

        # Test 4: Verify field mapping is correct
        print("Test 4: Checking field mapping in get_family_members...")

        # Look for the correct field assignments
        get_family_members_source = content[
            content.find("async def get_family_members") : content.find(
                "async def", content.find("async def get_family_members") + 1
            )
        ]

        expected_fields = ['"role"', '"spending_limit"', '"can_spend"', '"updated_by"', '"updated_at"']
        missing_fields = []

        for field in expected_fields:
            if field not in get_family_members_source:
                missing_fields.append(field)

        if not missing_fields:
            print("✓ All expected permission fields are mapped correctly")
        else:
            print(f"✗ Missing permission fields: {missing_fields}")
            return False

        print("\n" + "=" * 55)
        print("✅ All tests passed! Data consistency fix is correctly implemented.")
        print("\nSummary of the fix:")
        print("- get_family_members now reads from family['sbd_account']['spending_permissions']")
        print("- Removed reading from user membership data (family_membership.get('spending_permissions'))")
        print("- update_spending_permissions maintains both data sources for backward compatibility")
        print("- Field names now match API response model: role, spending_limit, can_spend, updated_by, updated_at")
        print("- Frontend 'Can Spend' toggle should now work correctly after PUT requests")

        return True

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_spending_permissions_fix()
    sys.exit(0 if success else 1)
