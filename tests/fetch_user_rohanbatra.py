import asyncio
from second_brain_database.database import db_manager

async def fetch_user_all():
    await db_manager.connect()
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": "rohanbatra"})
    print("User document for 'rohanbatra':")
    print(user)
    await db_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(fetch_user_all())
