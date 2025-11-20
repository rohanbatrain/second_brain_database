#!/usr/bin/env python3
"""
Test script for Family Received Invitations API endpoint.

Usage:
    python test_received_invitations.py <token> [status]

Examples:
    python test_received_invitations.py eyJhbGc...
    python test_received_invitations.py eyJhbGc... pending
"""

import sys
import json
import requests
from typing import Optional, List, Dict, Any


BASE_URL = "http://localhost:8000"  # Change to your API URL


def test_get_received_invitations(token: str, status: Optional[str] = None) -> None:
    """Test the GET /family/my-invitations endpoint."""

    url = f"{BASE_URL}/family/my-invitations"
    params = {"status": status} if status else {}
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "TestScript/1.0"
    }

    print(f"\n{'='*60}")
    print(f"Testing: GET /family/my-invitations")
    if status:
        print(f"Filter: status={status}")
    print(f"{'='*60}\n")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {response.elapsed.total_seconds():.3f}s")
        print(f"\nResponse Headers:")
        for key, value in response.headers.items():
            if key.lower() in ['content-type', 'x-ratelimit-limit', 'x-ratelimit-remaining']:
                print(f"  {key}: {value}")

        print(f"\nResponse Body:")

        if response.status_code == 200:
            invitations = response.json()
            print(f"✅ Success! Retrieved {len(invitations)} invitation(s)\n")

            if not invitations:
                print("  No invitations found.")
            else:
                for i, inv in enumerate(invitations, 1):
                    print(f"  [{i}] Invitation from {inv['inviter_username']}")
                    print(f"      Family: {inv['family_name']}")
                    print(f"      Role: {inv['relationship_type']}")
                    print(f"      Status: {inv['status']}")
                    print(f"      Expires: {inv['expires_at']}")
                    print(f"      ID: {inv['invitation_id']}")
                    print()

            # Pretty print full JSON
            print("\nFull JSON Response:")
            print(json.dumps(invitations, indent=2))

        elif response.status_code == 400:
            error = response.json()
            print(f"❌ Bad Request:")
            print(f"   Error: {error.get('error', 'Unknown')}")
            print(f"   Message: {error.get('message', 'No message')}")

        elif response.status_code == 401:
            print(f"❌ Unauthorized:")
            print(f"   Your token is invalid or expired.")
            print(f"   Please login again to get a fresh token.")

        elif response.status_code == 403:
            print(f"❌ Forbidden:")
            print(f"   {response.json().get('detail', 'Access denied')}")

        elif response.status_code == 429:
            print(f"❌ Rate Limit Exceeded:")
            print(f"   You've made too many requests. Wait before retrying.")

        elif response.status_code == 500:
            error = response.json()
            print(f"❌ Server Error:")
            print(f"   Error: {error.get('error', 'Unknown')}")
            print(f"   Message: {error.get('message', 'Internal server error')}")

        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error:")
        print(f"   Cannot connect to {BASE_URL}")
        print(f"   Make sure the API server is running.")

    except requests.exceptions.Timeout:
        print(f"❌ Timeout Error:")
        print(f"   Request took longer than 10 seconds.")

    except requests.exceptions.RequestException as e:
        print(f"❌ Request Error: {e}")

    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response")
        print(f"   Raw response: {response.text[:200]}")

    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

    print(f"\n{'='*60}\n")


def test_status_filters(token: str) -> None:
    """Test all status filter values."""
    statuses = [None, "pending", "accepted", "declined", "expired"]

    print(f"\n{'='*60}")
    print("Testing all status filters")
    print(f"{'='*60}\n")

    for status in statuses:
        filter_name = status if status else "all"
        print(f"Testing filter: {filter_name}")
        test_get_received_invitations(token, status)


def test_invalid_status(token: str) -> None:
    """Test with invalid status value."""
    print(f"\n{'='*60}")
    print("Testing invalid status filter (should return 400)")
    print(f"{'='*60}\n")

    test_get_received_invitations(token, "invalid_status")


def run_all_tests(token: str) -> None:
    """Run comprehensive test suite."""
    print("\n" + "="*60)
    print(" FAMILY RECEIVED INVITATIONS API - TEST SUITE")
    print("="*60)

    # Test 1: Get all invitations
    print("\n[Test 1] Get all invitations (no filter)")
    test_get_received_invitations(token)

    # Test 2: Get only pending
    print("\n[Test 2] Get pending invitations only")
    test_get_received_invitations(token, "pending")

    # Test 3: Invalid status
    print("\n[Test 3] Test invalid status filter")
    test_invalid_status(token)

    print("\n" + "="*60)
    print(" TEST SUITE COMPLETE")
    print("="*60 + "\n")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test_received_invitations.py <token> [status]")
        print("\nExamples:")
        print("  python test_received_invitations.py eyJhbGc...")
        print("  python test_received_invitations.py eyJhbGc... pending")
        print("  python test_received_invitations.py eyJhbGc... --all-tests")
        sys.exit(1)

    token = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[2] == "--all-tests":
        run_all_tests(token)
    elif len(sys.argv) > 2:
        status = sys.argv[2]
        test_get_received_invitations(token, status)
    else:
        test_get_received_invitations(token)


if __name__ == "__main__":
    main()
