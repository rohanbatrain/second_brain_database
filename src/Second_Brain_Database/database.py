from Second_Brain_Database.config import MONGO_DB_NAME, MONGO_URL
from pymongo import MongoClient

client = MongoClient(MONGO_URL)   
db = client[str(MONGO_DB_NAME)]   