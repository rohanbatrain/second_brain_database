from bson.objectid import ObjectId

def delete_flashcard_by_id(mongo, flashcard_id):
    mongo.db.flashcards.delete_one({"_id": ObjectId(flashcard_id)})
