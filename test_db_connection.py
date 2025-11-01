#!/usr/bin/env python3
"""
Quick test to check database connection for AI orchestration
"""

import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

async def test_database_connection():
    """Test database connection for AI orchestration."""
    
    print("🔍 TESTING DATABASE CONNECTION")
    print("=" * 50)
    
    try:
        # Test 1: Check configuration
        print("\n1️⃣ Checking Configuration...")
        from second_brain_database.config import settings
        
        print(f"   MongoDB URL: {settings.MONGODB_URL}")
        print(f"   MongoDB Database: {settings.MONGODB_DATABASE}")
        print(f"   Redis URL: {settings.REDIS_URL}")
        
        # Test 2: Test database manager
        print("\n2️⃣ Testing Database Manager...")
        from second_brain_database.database import db_manager
        
        if db_manager:
            print("   ✅ Database manager exists")
            
            # Try to get database
            try:
                database = db_manager.database
                if database:
                    print("   ✅ Database object available")
                    
                    # Test connection
                    server_info = await database.command("ping")
                    if server_info:
                        print("   ✅ Database ping successful")
                        
                        # Test collection access
                        users_collection = db_manager.get_collection("users")
                        if users_collection:
                            print("   ✅ Users collection accessible")
                        else:
                            print("   ❌ Users collection not accessible")
                    else:
                        print("   ❌ Database ping failed")
                else:
                    print("   ❌ Database object not available")
            except Exception as db_error:
                print(f"   ❌ Database connection error: {db_error}")
        else:
            print("   ❌ Database manager not available")
        
        # Test 3: Test Redis connection
        print("\n3️⃣ Testing Redis Connection...")
        from second_brain_database.managers.redis_manager import redis_manager
        
        try:
            redis = await redis_manager.get_redis()
            if redis:
                print("   ✅ Redis connection successful")
                
                # Test Redis operation
                await redis.set("test_key", "test_value")
                value = await redis.get("test_key")
                if value == "test_value":
                    print("   ✅ Redis operations working")
                    await redis.delete("test_key")
                else:
                    print("   ❌ Redis operations failed")
            else:
                print("   ❌ Redis connection failed")
        except Exception as redis_error:
            print(f"   ❌ Redis error: {redis_error}")
        
        # Test 4: Initialize database manager properly
        print("\n4️⃣ Initializing Database Manager...")
        try:
            # Try to initialize database manager
            await db_manager.initialize()
            print("   ✅ Database manager initialized")
            
            # Test collection access after initialization
            users_collection = db_manager.get_collection("users")
            if users_collection:
                print("   ✅ Collections accessible after initialization")
                
                # Test a simple query
                user_count = await users_collection.count_documents({})
                print(f"   ✅ User count: {user_count}")
            else:
                print("   ❌ Collections still not accessible")
                
        except Exception as init_error:
            print(f"   ❌ Database initialization error: {init_error}")
        
        return True
        
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_database_connection())
        if success:
            print("\n✅ Database connection test completed")
        else:
            print("\n❌ Database connection test failed")
    except Exception as e:
        print(f"\n💥 Test failed: {e}")