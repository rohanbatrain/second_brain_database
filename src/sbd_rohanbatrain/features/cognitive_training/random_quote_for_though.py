import random

def get_random_quote_for_thought():
    """Fetch a random quote that has no thoughts yet and return it."""
    quotes = list(collection.find({"thoughts": {"$size": 0}}, {"_id": 1, "quote": 1, "author": 1}))
    
    if not quotes:
        return {"status": "error", "message": "No quotes available for reflection, or all quotes already have your thoughts!"}

    # Select a random quote
    selected_quote = random.choice(quotes)
    return {
        "status": "success",
        "quote": selected_quote['quote'],
        "author": selected_quote['author'],
        "quote_id": selected_quote["_id"]
    }

def add_thought_to_quote(quote_id, thought):
    """Add a thought to the specified quote in MongoDB."""
    if not thought:
        return {"status": "error", "message": "Thought cannot be empty."}
    
    result = collection.update_one({"_id": quote_id}, {"$push": {"thoughts": thought}})
    
    if result.matched_count == 0:
        return {"status": "error", "message": "Quote not found."}
    
    return {"status": "success", "message": "Your thought has been saved."}
