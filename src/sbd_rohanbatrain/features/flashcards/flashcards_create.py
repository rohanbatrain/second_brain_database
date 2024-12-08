import pymongo
import datetime
from sbd_rohanbatrain.database.db import flashcards_collection


def create_flashcard(front, back, latex=False):
    now = datetime.datetime.utcnow()
    flashcard = {
        'front': front,
        'back': back,
        'latex': latex,
        'created_at': now,
        'creation_date': now.date().isoformat(),  # Only the date
        'creation_time': now.time().isoformat(),  # Only the time
        'modified': now,  # Full timestamp for modifications
        'modified_date': now.date().isoformat(),  # Only the date of modification
        'modified_time': now.time().isoformat(),  # Only the time of modification
    }
    # Insert the flashcard into the collection
    flashcards_collection.insert_one(flashcard)
    return flashcard  # Return the created flashcard


# Example usage
print(create_flashcard("hi", "hello"))
