import pymongo
import datetime
from sbd_rohanbatrain.database.db import flashcards_collection
from sbd_rohanbatrain.features.flashcards.flashcards_update.flashcards_update_by_id import update_flashcard


# Function to create a new flashcard and insert it into the MongoDB database
def create_flashcard(front, back, deck, latex=False):
    """
    Create a new flashcard and insert it into the MongoDB database.
    
    Parameters:
    front (str): The front of the flashcard (e.g., the question or term).
    back (str): The back of the flashcard (e.g., the answer or definition).
    deck (str): The deck to which the flashcard belongs.
    latex (bool): Whether the flashcard uses LaTeX for math formatting (default is False).
    
    Returns:
    ObjectId: The unique ID of the newly created flashcard.
    """
    now = datetime.datetime.now()  # Get the current local time
    timestamp = now.strftime('%Y-%m-%d %H:%M:%S')  # Format timestamp as 'YYYY-MM-DD HH:MM:SS'
    
    flashcard = {
        'front': front,
        'back': back,
        'latex': latex,
        'deck': deck,
        'created_at': timestamp,  # Store the creation timestamp in local time
        'updated_at': timestamp,  # Store the update timestamp in local time
        'interval': 1,  # Initial review interval (1 day)
        'ease_factor': 2.5,  # Initial ease factor (default for a new card)
        'repetitions': 0,  # Start with 0 repetitions (the card hasn't been reviewed yet)
        'next_review_date': now + datetime.timedelta(days=1),  # Set next review in 1 day
    }
    
    # Insert the new flashcard into the database
    result = flashcards_collection.insert_one(flashcard)
    
    return result.inserted_id  # Return the unique ObjectId of the inserted flashcard


# # Example usage: Simulate creating and updating flashcards based on user reviews
# if __name__ == "__main__":
#     # Example of creating a new flashcard
#     # flashcard_id = create_flashcard("What is Python?", "A programming language.", "Programming")

#     # Simulate a user grading the flashcard after reviewing it (e.g., grade = 4)
#     grade = 5 # Let's assume the user finds the card easy to recall.
#     updated_flashcard = update_flashcard("675ea7986d01761981bac5b8", grade)
#     print(f"Updated flashcard: {updated_flashcard}")