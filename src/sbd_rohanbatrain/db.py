from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from config import MONGO_URL, MONGO_DB_NAME

# Establish the connection
client = MongoClient(MONGO_URL)

# Access the database
db = client[MONGO_DB_NAME]
sleep = db["sleep"]