"""
database.py

Initializes the MongoDB client and database connection for Second Brain Database.

Dependencies:
    - pymongo
    - Second_Brain_Database.config

Author: Rohan Batra
Date: 2025-06-11
"""

import pymongo
from second_brain_database.config import MONGO_DB_NAME, MONGO_URL

client = pymongo.MongoClient(MONGO_URL)
db = client[str(MONGO_DB_NAME)]
