"""
database.py

Initializes the MongoDB client and database connection for Second Brain Database.

Dependencies:
    - pymongo
    - Second_Brain_Database.config

Author: Rohan (refactored by GitHub Copilot)
Date: 2025-06-11
"""

import pymongo
from Second_Brain_Database.config import MONGO_DB_NAME, MONGO_URL

client = pymongo.MongoClient(MONGO_URL)
db = client[str(MONGO_DB_NAME)]
