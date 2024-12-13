def update_note_by_name(note_name, new_content):
    # Fetch the existing note by its title
    note = notes_collection.find_one({"title": note_name})
    
    if note:
        # Get the current timestamp
        updated_at = datetime.datetime.now().isoformat()

        # Prepare the version history and increment version
        version = note["version"] + 1
        version_history = note.get("version_history", [])

        # Add the old content to the version history
        version_history.append({
            "version": note["version"],
            "content": note["content"],
            "updated_at": note["updated_at"]
        })

        # Update the note in MongoDB with the new content and incremented version
        notes_collection.update_one(
            {"title": note_name},
            {"$set": {
                "content": new_content,
                "updated_at": updated_at,
                "version": version
            },
            "$push": {"version_history": {
                "version": note["version"],
                "content": note["content"],
                "updated_at": note["updated_at"]
            }}}
        )

        print(f"Note '{note_name}' updated to version {version}.")
    else:
        print(f"Note '{note_name}' not found.")
