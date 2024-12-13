from pymongo import MongoClient
from sbd_rohanbatrain.database.db import restaurant_collection

def insert_restaurant(restaurant_collection, name, location, 
                      contact_number=None, start_time="09:00 AM", end_time="09:00 PM"):
    """
    Inserts a new restaurant into the restaurants collection.
    
    Args:
        restaurant_collection: MongoDB collection instance for restaurants.
        restaurant_id (str): Unique ID for the restaurant. (Required)
        name (str): Name of the restaurant. (Required)
        location (str): Address of the restaurant. (Required)
        contact_number (str): Contact number of the restaurant. (Optional, Default: None)
        start_time (str): Opening time. (Optional, Default: "09:00 AM")
        end_time (str): Closing time. (Optional, Default: "09:00 PM")
    """
    restaurant_data = {
        "name": name,
        "contactNumber": contact_number,
        "orderTimings": {
            "start": start_time,
            "end": end_time
        },
        "location": location
    }
    result = restaurant_collection.insert_one(restaurant_data)
    print(f"Restaurant inserted with ID: {result.inserted_id}")
