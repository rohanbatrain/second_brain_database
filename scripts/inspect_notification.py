"""Inspect a family_notifications document by request_id and print it as JSON.

Usage: python3 scripts/inspect_notification.py [request_id]
If no request_id is provided, defaults to 'req_9f063d76360d4eb7'.
"""
import sys
import os
import json
from pymongo import MongoClient

REQUEST_ID = sys.argv[1] if len(sys.argv) > 1 else "req_9f063d76360d4eb7"
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DATABASE", "SecondBrainDatabase")

try:
    client = MongoClient(MONGODB_URL)
    db = client[MONGODB_DB]
    coll = db.get_collection("family_notifications")

    doc = coll.find_one({"data.request_id": REQUEST_ID})
    if not doc:
        print(f"No notification found with data.request_id = {REQUEST_ID}")
        sys.exit(0)

    # Convert ObjectId and datetimes to strings for JSON serialization
    def convert(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if hasattr(obj, '__str__'):
            return str(obj)
        return obj

    print(json.dumps(doc, default=convert, indent=2))

except Exception as e:
    print(f"Error querying MongoDB: {e}")
    sys.exit(2)
