

# Example usage of CRUD functions
if __name__ == "__main__":
    # Create a new time entry
    new_entry_id = start_time_logging(
        entry="Writing a report",
        project_id="project1",
        task_id="task1",
        label_ids=["label1", "label2"],
        description="Writing the final draft of the report"
    )
    print(f"Time Entry Created: {new_entry_id}")

    # Get the time entry by ID
    time_entry = get_time_entry(new_entry_id)
    print(f"Retrieved Time Entry: {time_entry}")
    
    # Update the time entry
    updated_entry_id = update_time_entry(new_entry_id, description="Finalizing the report draft")
    print(f"Updated Time Entry ID: {updated_entry_id}")

    # Stop the time entry
    stop_result = stop_time_logging(new_entry_id)
    print(f"Stopped Time Entry: {stop_result}")
    
    # List all time entries
    all_entries = list_time_entries()
    print(f"All Time Entries: {all_entries}")
    
    # Delete the time entry
    delete_result = delete_time_entry(new_entry_id)
    print(f"Deleted Time Entry: {delete_result}")