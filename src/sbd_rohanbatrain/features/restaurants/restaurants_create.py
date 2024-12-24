from pymongo import MongoClient
from sbd_rohanbatrain.database.db import restaurant_collection

# Insert a new restaurant with a menu_ids array
def insert_restaurant(name, address, contact_number=None, start_time="09:00 AM", end_time="09:00 PM", lat=None, long=None, menu_ids=None):
    """
    Inserts a new restaurant into the restaurants collection with an array of menu_ids.
    
    Args:
        name (str): Name of the restaurant. (Required)
        address (str): Address of the restaurant. (Required)
        contact_number (str): Contact number of the restaurant. (Optional, Default: None)
        start_time (str): Opening time of the restaurant. (Optional, Default: "09:00 AM")
        end_time (str): Closing time of the restaurant. (Optional, Default: "09:00 PM")
        lat (float): Latitude of the restaurant's location. (Optional, Default: None)
        long (float): Longitude of the restaurant's location. (Optional, Default: None)
        menu_ids (list): List of menu unique IDs. (Optional, Default: None)
        
    Returns:
        None: This function does not return any value, it only inserts the data into the database.
    """
    location_data = {
        "address": address,
        "lat": lat,
        "long": long
    }

    restaurant_data = {
        "name": name,
        "contactNumber": contact_number,
        "orderTimings": {
            "start": start_time,
            "end": end_time
        },
        "location": location_data
    }

    if menu_ids:
        restaurant_data["menu_ids"] = menu_ids

    result = restaurant_collection.insert_one(restaurant_data)
    print(f"Restaurant inserted with ID: {result.inserted_id}")