def delete_note(note_id):
    # Delete the note from MongoDB
    result = notes_collection.delete_one({"_id": note_id})
    
    if result.deleted_count > 0:
        print(f"Note {note_id} deleted.")
    else:
        print("Note not found.")
