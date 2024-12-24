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
quotes_collection = db["quotes"]
inventory_collection = db["inventory"]
restaurant_collection = db["restaurant"]
goals_collection = db["goals"]
playlist_collection = db["playlist"]
songs_collection = db["songs"]
habits_collection  = db["habits"]
history_collection = db["history"]
water_intake_collection = db["water_intake"]
time_tracker_collection = db["time_tracker"]
body_weight_collection = db["body_weight"]
recipe_collection = db["recipe_collection"]
routine_collection = db["routines"]