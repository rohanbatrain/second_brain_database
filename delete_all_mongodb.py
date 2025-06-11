"""
delete_all_mongodb.py

Utility script to delete all documents from every collection in the configured MongoDB database.

Dependencies:
    - pymongo
    - Second_Brain_Database.config
    - logging

Author: Rohan (refactored by GitHub Copilot)
Date: 2025-06-11
"""
import logging
from pymongo import MongoClient
from Second_Brain_Database.config import MONGO_URL, MONGO_DB_NAME

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def delete_all_collections():
    """
    Delete all documents from every collection in the configured MongoDB database.

    Returns:
        None
    """
    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB_NAME]
    collections = db.list_collection_names()
    if not collections:
        logger.info(f"No collections found in database '{MONGO_DB_NAME}'. Nothing to delete.")
        return
    for coll_name in collections:
        result = db[coll_name].delete_many({})
        logger.info(f"Deleted {result.deleted_count} documents from collection '{coll_name}' in database '{MONGO_DB_NAME}'.")
    logger.info(f"All collections in database '{MONGO_DB_NAME}' have been cleared.")

if __name__ == "__main__":
    logger.warning("This operation will irreversibly delete ALL data in the database. Proceeding...")
    delete_all_collections()
