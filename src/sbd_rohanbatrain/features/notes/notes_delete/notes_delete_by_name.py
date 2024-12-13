def delete_note_by_name(note_name):
    # Delete the note from MongoDB using the title (name)
    result = notes_collection.delete_one({"title": note_name})
    
    if result.deleted_count > 0:
        print(f"Note '{note_name}' deleted.")
    else:
        print(f"Note '{note_name}' not found.")
