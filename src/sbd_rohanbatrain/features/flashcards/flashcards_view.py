import pymongo
from bson.objectid import ObjectId
from sbd_rohanbatrain.database.db import flashcards_collection

# Fetch all flashcards from the collection
def get_all_flashcards():
    flashcards = flashcards_collection.find()
    return list(flashcards)  # Convert the cursor to a list and return

# Fetch a specific flashcard by ID
def get_flashcard_by_id(flashcard_id):
    flashcard = flashcards_collection.find_one({"_id": ObjectId(flashcard_id)})
    return flashcard  # Returns the flashcard or None if not found

# Example usage to get all flashcards
def print_all_flashcards():
    flashcards = get_all_flashcards()
    for flashcard in flashcards:
        print(flashcard)

# Example usage to get a flashcard by ID
def print_flashcard_by_id(flashcard_id):
    flashcard = get_flashcard_by_id(flashcard_id)
    if flashcard:
        print(flashcard)
    else:
        print(f"Flashcard with ID {flashcard_id} not found.")
