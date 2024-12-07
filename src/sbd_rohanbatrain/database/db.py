from pymongo import MongoClient
from sbd_rohanbatrain.config_files.config import MONGO_URL, MONGO_DB_NAME 

# Establish the connection
client = MongoClient(MONGO_URL)

# Access the database
db = client[MONGO_DB_NAME]

# Collections
sleep_collection = db["sleep"]
tasks_collection = db["tasks"]
projects_collection = db["projects"]
labels_collection = db["labels"]
network_collection = db["network"]
expense_collection = db["expense"]
logging_collection = db["logging"]
