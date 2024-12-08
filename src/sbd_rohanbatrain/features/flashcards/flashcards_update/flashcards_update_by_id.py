from bson.objectid import ObjectId
from sbd_rohanbatrain.database.db import flashcards_collection

def update_flashcard_by_name(front, new_front=None, new_back=None, new_latex=None):
    # Create the update dictionary based on provided values
    update_fields = {}
    
    if new_front:
        update_fields['front'] = new_front
    if new_back:
        update_fields['back'] = new_back
    if new_latex is not None:
        update_fields['latex'] = new_latex

    if not update_fields:
        return "No update data provided."

    # Update the flashcard with the specified 'front' value (name)
    result = flashcards_collection.update_one(
        {"front": front},  # Search for flashcard by front (name)
        {"$set": update_fields}  # Set new fields
    )

    if result.matched_count == 0:
        return f"Flashcard with front '{front}' not found."
    
    # Return updated flashcard
    updated_flashcard = flashcards_collection.find_one({"front": front})
    return updated_flashcard

