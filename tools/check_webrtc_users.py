#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from second_brain_database.managers.mongodb_manager import mongodb_manager

async def check_and_verify_users():
    print("🔍 Checking WebRTC Test Users Status")
    print("====================================")

    try:
        await mongodb_manager.connect()
        db = mongodb_manager.get_database('second_brain_database')
        users_collection = db.users

        # Find our test users
        user1 = await users_collection.find_one({'username': 'webrtc_user1'})
        user2 = await users_collection.find_one({'username': 'webrtc_user2'})

        print('👤 USER 1 (webrtc_user1):')
        if user1:
            print(f'   ID: {user1.get("_id")}')
            print(f'   Email: {user1.get("email")}')
            print(f'   Verified: {user1.get("is_verified", False)}')
            verification_token = user1.get("verification_token")
            if verification_token:
                print(f'   Verification Token: {verification_token}')
                print(f'   🔗 Verification URL: http://localhost:8000/auth/verify-email?token={verification_token}')
            else:
                print('   Verification Token: None')
        else:
            print('   Not found')

        print()
        print('👤 USER 2 (webrtc_user2):')
        if user2:
            print(f'   ID: {user2.get("_id")}')
            print(f'   Email: {user2.get("email")}')
            print(f'   Verified: {user2.get("is_verified", False)}')
            verification_token = user2.get("verification_token")
            if verification_token:
                print(f'   Verification Token: {verification_token}')
                print(f'   🔗 Verification URL: http://localhost:8000/auth/verify-email?token={verification_token}')
            else:
                print('   Verification Token: None')
        else:
            print('   Not found')

        print()
        print("🔧 Manual Verification Options:")
        print("================================")

        if user1 and not user1.get("is_verified", False) and user1.get("verification_token"):
            print("1. Click this link to verify User 1:")
            print(f"   http://localhost:8000/auth/verify-email?token={user1['verification_token']}")

        if user2 and not user2.get("is_verified", False) and user2.get("verification_token"):
            print("2. Click this link to verify User 2:")
            print(f"   http://localhost:8000/auth/verify-email?token={user2['verification_token']}")

        print()
        print("3. Or use curl commands:")
        if user1 and user1.get("verification_token"):
            print(f"   curl -X POST http://localhost:8000/auth/verify-email -H 'Content-Type: application/json' -d '{{\"token\": \"{user1['verification_token']}\"}}'")
        if user2 and user2.get("verification_token"):
            print(f"   curl -X POST http://localhost:8000/auth/verify-email -H 'Content-Type: application/json' -d '{{\"token\": \"{user2['verification_token']}\"}}'")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await mongodb_manager.close()

if __name__ == "__main__":
    asyncio.run(check_and_verify_users())