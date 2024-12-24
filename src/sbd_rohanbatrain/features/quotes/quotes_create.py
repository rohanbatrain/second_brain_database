import pymongo
from pymongo import MongoClient
from sbd_rohanbatrain.database.db import quotes_collection



def add_quote(quote, author):
    """Add a new quote with author to the MongoDB collection."""
    existing_quote = quotes_collection.find_one({"quote": quote, "author": author})
    if existing_quote:
        return existing_quote["_id"]
    else:
        result = quotes_collection.insert_one({"quote": quote, "author": author, "thoughts": []})
        return result.inserted_id

