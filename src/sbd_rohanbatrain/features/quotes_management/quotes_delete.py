import pymongo
from pymongo import MongoClient
from sbd_rohanbatrain.database.db import quotes_collection

def delete_quote_by_id(quote_id):
    """Delete a quote by its ID."""
    return quotes_collection.delete_one({"_id": quote_id})
