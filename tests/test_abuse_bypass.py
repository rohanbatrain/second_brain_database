#!/usr/bin/env python3
"""
Quick test to verify the test email bypass logic
"""


def should_bypass_abuse_detection(email: str) -> bool:
    """Test the bypass logic directly"""
    if email and ("test" in email.lower() or email.startswith("test") or "@test." in email):
        return True
    return False


def test_bypass():
    print("Testing abuse detection bypass logic for test emails...")

    # Test cases
    test_cases = [
        ("test2@rohanbatra.in", True),  # Should bypass
        ("user@example.com", False),  # Should not bypass
        ("testuser@testdomain.com", True),  # Should bypass
        ("normaluser@gmail.com", False),  # Should not bypass
        ("TestUser@test.com", True),  # Should bypass (case insensitive)
        ("", False),  # Should not bypass (empty)
    ]

    all_passed = True
    for email, expected in test_cases:
        result = should_bypass_abuse_detection(email)
        status = "PASS" if result == expected else "FAIL"
        if result != expected:
            all_passed = False
        print(f"Email: '{email}' -> Bypass: {result} (Expected: {expected}) [{status}]")

    print(f"\nOverall result: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    return all_passed


if __name__ == "__main__":
    test_bypass()
