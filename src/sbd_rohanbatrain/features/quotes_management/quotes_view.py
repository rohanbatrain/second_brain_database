import pymongo
from pymongo import MongoClient
from sbd_rohanbatrain.database.db import quotes_collection

def get_quote_by_id(quote_id):
    """Retrieve a quote by its ID."""
    return quotes_collection.find_one({"_id": quote_id})
