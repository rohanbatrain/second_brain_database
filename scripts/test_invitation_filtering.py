#!/usr/bin/env python3
"""
Test script to verify invitation filtering logic for GET /family/{family_id}/invitations endpoint.

This script simulates the filtering conditions:
1. Has recipient info (invitee_email OR invitee_username)
2. Has inviter OR family info (inviter_username not "Unknown" OR family_name not "Unknown Family")
3. Not in bad expired state (if expired, status must be "pending")

Usage:
    python scripts/test_invitation_filtering.py
"""

from datetime import datetime, timezone, timedelta


def test_invitation_filtering():
    """Test the invitation filtering logic with various scenarios."""

    # Test cases simulating various invitation states
    test_invitations = [
        {
            "name": "Valid invitation - all fields present",
            "invitation": {
                "invitation_id": "inv_001",
                "invitee_email": "test@example.com",
                "invitee_username": "testuser",
                "inviter_username": "admin_user",
                "family_name": "Smith Family",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            },
            "expected": True
        },
        {
            "name": "Missing invitee info - should be filtered out",
            "invitation": {
                "invitation_id": "inv_002",
                "invitee_email": "",
                "invitee_username": "",
                "inviter_username": "admin_user",
                "family_name": "Smith Family",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            },
            "expected": False
        },
        {
            "name": "Has invitee email only - should pass",
            "invitation": {
                "invitation_id": "inv_003",
                "invitee_email": "test@example.com",
                "invitee_username": "",
                "inviter_username": "admin_user",
                "family_name": "Smith Family",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            },
            "expected": True
        },
        {
            "name": "Has invitee username only - should pass",
            "invitation": {
                "invitation_id": "inv_004",
                "invitee_email": "",
                "invitee_username": "testuser",
                "inviter_username": "admin_user",
                "family_name": "Smith Family",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            },
            "expected": True
        },
        {
            "name": "Unknown inviter and family - should be filtered out",
            "invitation": {
                "invitation_id": "inv_005",
                "invitee_email": "test@example.com",
                "invitee_username": "testuser",
                "inviter_username": "Unknown",
                "family_name": "Unknown Family",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            },
            "expected": False
        },
        {
            "name": "Known inviter, unknown family - should pass",
            "invitation": {
                "invitation_id": "inv_006",
                "invitee_email": "test@example.com",
                "invitee_username": "testuser",
                "inviter_username": "admin_user",
                "family_name": "Unknown Family",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            },
            "expected": True
        },
        {
            "name": "Unknown inviter, known family - should pass",
            "invitation": {
                "invitation_id": "inv_007",
                "invitee_email": "test@example.com",
                "invitee_username": "testuser",
                "inviter_username": "Unknown",
                "family_name": "Smith Family",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            },
            "expected": True
        },
        {
            "name": "Expired with pending status - should pass",
            "invitation": {
                "invitation_id": "inv_008",
                "invitee_email": "test@example.com",
                "invitee_username": "testuser",
                "inviter_username": "admin_user",
                "family_name": "Smith Family",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
            },
            "expected": True
        },
        {
            "name": "Expired with accepted status - should be filtered out",
            "invitation": {
                "invitation_id": "inv_009",
                "invitee_email": "test@example.com",
                "invitee_username": "testuser",
                "inviter_username": "admin_user",
                "family_name": "Smith Family",
                "status": "accepted",
                "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
            },
            "expected": False
        },
        {
            "name": "Expired with declined status - should be filtered out",
            "invitation": {
                "invitation_id": "inv_010",
                "invitee_email": "test@example.com",
                "invitee_username": "testuser",
                "inviter_username": "admin_user",
                "family_name": "Smith Family",
                "status": "declined",
                "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
            },
            "expected": False
        },
    ]

    passed = 0
    failed = 0

    print("=" * 80)
    print("Testing Invitation Filtering Logic")
    print("=" * 80)

    for test_case in test_invitations:
        invitation = test_case["invitation"]
        expected = test_case["expected"]

        # Apply filtering logic
        invitee_email = invitation.get("invitee_email") or ""
        invitee_username = invitation.get("invitee_username") or ""
        has_recipient_info = (invitee_email.strip() != "") or (invitee_username.strip() != "")

        inviter_username = invitation.get("inviter_username", "Unknown")
        family_name = invitation.get("family_name", "Unknown Family")
        has_inviter_or_family_info = (
            (inviter_username and inviter_username != "Unknown") or
            (family_name and family_name != "Unknown Family")
        )

        invitation_status = invitation.get("status", "")
        expires_at = invitation.get("expires_at")
        is_expired = False
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            is_expired = datetime.now(timezone.utc) > expires_at

        # Determine if invitation should be filtered out
        skip_expired = is_expired and invitation_status != "pending"
        skip_missing_fields = not (has_recipient_info and has_inviter_or_family_info)
        should_include = not (skip_expired or skip_missing_fields)

        # Check if result matches expected
        if should_include == expected:
            passed += 1
            status = "✓ PASS"
        else:
            failed += 1
            status = "✗ FAIL"

        print(f"\n{status} - {test_case['name']}")
        print(f"  Invitation ID: {invitation['invitation_id']}")
        print(f"  Has Recipient Info: {has_recipient_info}")
        print(f"  Has Inviter/Family Info: {has_inviter_or_family_info}")
        print(f"  Expired: {is_expired}, Status: {invitation_status}")
        print(f"  Expected Include: {expected}, Actual Include: {should_include}")

    print("\n" + "=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed out of {len(test_invitations)} total")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = test_invitation_filtering()
    exit(0 if success else 1)
