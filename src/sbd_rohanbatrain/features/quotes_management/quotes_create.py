import pymongo
from pymongo import MongoClient
from sbd_rohanbatrain.database.db import quotes_collection



# Connect to MongoDB

collection = quotes_collection

def add_quote(quote, author):
    """Add a new quote with author to the MongoDB collection."""
    if collection.find_one({"quote": quote, "author": author}):
        return {"status": "error", "message": "This quote by this author is already saved."}
    else:
        collection.insert_one({"quote": quote, "author": author, "thoughts": []})
        return {"status": "success", "message": "Quote saved successfully!"}

def view_quotes():
    """Retrieve and return all quotes with authors and thoughts."""
    quotes = list(collection.find({}, {"_id": 0, "quote": 1, "author": 1, "thoughts": 1}))
    if not quotes:
        return {"status": "error", "message": "No quotes saved yet!"}
    
    quote_list = []
    for quote in quotes:
        quote_data = {
            "quote": quote['quote'],
            "author": quote['author'],
            "thoughts": quote['thoughts'] if quote['thoughts'] else "No thoughts yet"
        }
        quote_list.append(quote_data)
    return {"status": "success", "quotes": quote_list}
