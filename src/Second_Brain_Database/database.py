from Second_Brain_Database.config import MONGO_DB_NAME, MONGO_URL
from pymongo import MongoClient

client = MongoClient(MONGO_URL)  # Replace with your MongoDB URI
db = client[str(MONGO_DB_NAME)]  # Replace with your actual database name