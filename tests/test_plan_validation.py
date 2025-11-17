#!/usr/bin/env python3
"""
Test script to verify plan validation works correctly in user registration.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from second_brain_database.routes.auth.models import UserIn
from pydantic import ValidationError


def test_plan_validation():
    """Test plan validation in UserIn model."""
    print("🧪 Testing Plan Validation in User Registration")
    print("=" * 50)
    
    # Test 1: Default free plan (should work)
    print("\n1️⃣ Testing default free plan...")
    try:
        user = UserIn(
            username="testuser",
            email="test@example.com",
            password="TestPass123!"
        )
        print(f"✅ Default plan: {user.plan}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Explicit free plan (should work)
    print("\n2️⃣ Testing explicit free plan...")
    try:
        user = UserIn(
            username="testuser2",
            email="test2@example.com", 
            password="TestPass123!",
            plan="free"
        )
        print(f"✅ Explicit free plan: {user.plan}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Premium plan attempt (should fail)
    print("\n3️⃣ Testing premium plan (should be blocked)...")
    try:
        user = UserIn(
            username="hacker",
            email="hacker@example.com",
            password="TestPass123!",
            plan="premium"
        )
        print(f"❌ SECURITY ISSUE: Premium plan allowed: {user.plan}")
    except ValidationError as e:
        print(f"✅ Premium plan correctly blocked: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")
    
    # Test 4: Enterprise plan attempt (should fail)
    print("\n4️⃣ Testing enterprise plan (should be blocked)...")
    try:
        user = UserIn(
            username="enterpriseuser",
            email="enterprise@example.com",
            password="TestPass123!",
            plan="enterprise"
        )
        print(f"❌ SECURITY ISSUE: Enterprise plan allowed: {user.plan}")
    except ValidationError as e:
        print(f"✅ Enterprise plan correctly blocked: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")
    
    # Test 5: Random plan attempt (should fail)
    print("\n5️⃣ Testing random plan name (should be blocked)...")
    try:
        user = UserIn(
            username="randomuser",
            email="random@example.com",
            password="TestPass123!",
            plan="super_premium_unlimited"
        )
        print(f"❌ SECURITY ISSUE: Random plan allowed: {user.plan}")
    except ValidationError as e:
        print(f"✅ Random plan correctly blocked: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")
    
    # Test 6: Case sensitivity (should normalize to free)
    print("\n6️⃣ Testing case sensitivity...")
    try:
        user = UserIn(
            username="casetest",
            email="case@example.com",
            password="TestPass123!",
            plan="FREE"
        )
        print(f"✅ Case handled correctly: {user.plan}")
    except ValidationError as e:
        print(f"✅ Case correctly blocked: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")
    
    print("\n" + "=" * 50)
    print("🔒 Plan validation test complete!")
    print("✅ Only 'free' plans should be allowed for new registrations")


if __name__ == "__main__":
    test_plan_validation()