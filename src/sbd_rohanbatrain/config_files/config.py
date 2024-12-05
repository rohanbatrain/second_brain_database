# Import the JSON module to work with JSON files
import json
from sbd_rohanbatrain.utilities.config_related import config_location

# Variable Declaration
config_file_path =  config_location

# Open the configuration file named "config.json" in read mode
with open(config_file_path, "r") as config_file:
    # Load the contents of the JSON file into a Python dictionary
    config = json.load(config_file)

# Retrieve the API key value from the loaded configuration
API_KEY = config["API_KEY"]
MONGO_URL = config["MONGO_URL"]
MONGO_DB_NAME  = config["MONGO_DB_NAME"]