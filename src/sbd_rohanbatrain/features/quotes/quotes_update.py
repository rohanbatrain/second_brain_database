import pymongo
from pymongo import MongoClient
from sbd_rohanbatrain.database.db import quotes_collection

def update_quote(quote_id, new_quote=None, new_author=None):
    """Update an existing quote in the MongoDB collection."""
    try:
        # Create the update fields dictionary
        update_fields = {}
        
        if new_quote:
            update_fields["quote"] = new_quote
        if new_author:
            update_fields["author"] = new_author

        # If no fields to update, return None
        if not update_fields:
            return None

        # Update the quote
        result = quotes_collection.update_one(
            {"_id": pymongo.ObjectId(quote_id)}, 
            {"$set": update_fields}
        )

        if result.matched_count > 0:
            # Return the updated quote ID if the update was successful
            return quote_id
        else:
            # If no document was matched, return None
            return None
        
    except pymongo.errors.PyMongoError as e:
        # Handle any MongoDB-related exceptions
        return None
