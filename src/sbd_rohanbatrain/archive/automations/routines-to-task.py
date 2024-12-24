from datetime import datetime, timedelta
import calendar
from bson.objectid import ObjectId

# Helper function to check if a year is a leap year
def is_leap_year(year):
    """
    Returns True if the given year is a leap year.
    """
    return (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))

# Helper function to get the last day of a given month
def get_last_day_of_month(year, month):
    """
    Returns the last day of the month.
    """
    next_month = month % 12 + 1
    next_month_year = year if next_month > 1 else year + 1
    last_day = datetime(next_month_year, next_month, 1) - timedelta(days=1)
    return last_day.day

# Helper function to adjust the date for leap years and end-of-month cases
def adjust_due_date(due_date, frequency):
    """
    Adjust the due date when there are edge cases like leap year or end-of-month issues.
    """
    if frequency == "monthly":
        # Handle the case where the day does not exist in the next month
        try:
            # Try to set the same day in the next month
            next_due_date = due_date.replace(year=due_date.year + 1 if due_date.month == 12 else due_date.year, 
                                              month=due_date.month + 1 if due_date.month < 12 else 1)
        except ValueError:
            # If that day doesn't exist, set to the last valid day of the next month
            last_day_of_next_month = get_last_day_of_month(due_date.year, due_date.month + 1 if due_date.month < 12 else 1)
            next_due_date = due_date.replace(day=last_day_of_next_month, 
                                              month=due_date.month + 1 if due_date.month < 12 else 1, 
                                              year=due_date.year + 1 if due_date.month == 12 else due_date.year)
        return next_due_date

    if frequency == "yearly":
        # Handle leap year cases for February 29th
        if due_date.month == 2 and due_date.day == 29:
            # If the next year is not a leap year, move it to February 28th
            if not is_leap_year(due_date.year + 1):
                return due_date.replace(year=due_date.year + 1, day=28)
            else:
                return due_date.replace(year=due_date.year + 1)
    
        return due_date.replace(year=due_date.year + 1)
    
    if frequency == "daily":
        return due_date + timedelta(days=1)

    if frequency == "weekly":
        return due_date + timedelta(weeks=1)

    return due_date


# Function to handle task creation based on frequency and update routine
def create_recurring_task_and_update_routine(task, frequency, routine_id):
    """
    Creates a recurring task based on the given frequency (daily, weekly, monthly, yearly),
    adjusts the due date based on edge cases, and appends the task to the routine document.
    It also updates the `latest_task_id` field in the routine.
    """
    due_date = task['due_date']
    
    # Adjust due date based on frequency (daily, weekly, monthly, yearly)
    new_due_date = adjust_due_date(due_date, frequency)

    # Create the new task
    new_task = {
        "title": task["title"],
        "description": task["description"],
        "due_date": new_due_date,
        "priority": task["priority"],
        "is_completed": False,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "task_reference_id": task["task_reference_id"],  # This could include "habit", "routine", etc.
        "frequency": frequency
    }

    # Insert the new task into the task collection (replace with your actual insert code)
    # result = tasks_collection.insert_one(new_task)
    new_task_id = str(ObjectId())  # Mock ObjectId, replace with actual insert result

    # Update the routine document
    routine_collection.update_one(
        {"_id": ObjectId(routine_id)},  # Use the routine_id to fetch the specific routine
        {
            "$push": {"task_ids": new_task_id},  # Append the new task ID to the task_ids array
            "$set": {"latest_task_id": new_task_id}  # Set the latest_task_id field to the new task ID
        }
    )

    print(f"New task created with ID: {new_task_id} and added to routine {routine_id}")

    return new_task, new_task_id


# Sample usage
# task_example = {
#     "title": "Pay bills",
#     "description": "Pay all outstanding utility bills",
#     "due_date": datetime(2024, 2, 29),  # A task due on February 29, 2024 (leap year)
#     "priority": 2,
#     "task_reference_id": "some_reference_id"
# }

# routine_id_example = "5f50c31a50f5a8b8b8f1b2e8"  # Replace with an actual routine ID from your database

# # Handle monthly task creation and leap year adjustment, while updating the routine
# new_task, new_task_id = create_recurring_task_and_update_routine(task_example, "monthly", routine_id_example)