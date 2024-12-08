from sbd_rohanbatrain.database.db import flashcards_collection

def delete_flashcard_by_name(front):
    # Delete the flashcard with the specified 'front' (name)
    result = flashcards_collection.delete_one({"front": front})

    if result.deleted_count == 0:
        return f"Flashcard with front '{front}' not found."
    
    return f"Flashcard with front '{front}' has been deleted."
