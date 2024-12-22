from datetime import datetime, timedelta
from bson.objectid import ObjectId
from sbd_rohanbatrain.database.db import history_collection, habits_collection
from sbd_rohanbatrain.features.tasks.tasks import create_task  # Reuse task creation logic


def create_habit(name, description, goal, frequency, goal_reference_id):
    """
    Creates a new habit and links it to a goal.

    Args:
        name (str): The name of the habit (e.g., "Daily Pushups").
        description (str): A short description of the habit.
        goal (str): A specific goal or objective associated with the habit (e.g., "Do 10 pushups daily").
        frequency (str): The recurrence frequency of the habit (e.g., "daily", "weekly").
        goal_reference_id (str): The ID of the goal document this habit is linked to.

    Returns:
        str: The ID of the newly created habit document in the database.

    Raises:
        Exception: If an error occurs during habit creation, an exception is raised.
    """
    try:
        habit = {
            "name": name,
            "description": description,
            "goal": goal,
            "frequency": frequency,
            "goal_reference_id": goal_reference_id,  # Reference to the associated goal
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        result = habits_collection.insert_one(habit)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error creating habit: {e}")
        return None

def track_habit(habit_id, is_completed):
    """
    Tracks the completion of a habit and updates the associated goal's progress.

    Args:
        habit_id (str): The ID of the habit being tracked.
        is_completed (bool): Whether the habit was completed today.

    Returns:
        str: The ID of the history entry created to track the habit's completion.
    """
    try:
        habit = get_habit_by_id(habit_id)
        if not habit:
            print(f"Habit with ID {habit_id} not found")
            return None
        
        # Create a task representing the completion of the habit
        task_id = create_task(
            title=f"Complete {habit['name']}",
            description=f"Complete the habit: {habit['name']}",
            due_date=datetime.now(),
            priority=3,
            task_reference_id=habit_id  # Reference to the habit
        )

        # If the habit has an associated goal, update the goal's progress
        if 'goal_reference_id' in habit:
            goal_id = habit['goal_reference_id']
            goal = get_goal_by_id(goal_id)  # Retrieve the goal associated with the habit
            
            if goal:
                # For example, let's assume goal_value is the target to track
                goal_progress = 1 if is_completed else 0  # Increment progress if completed
                # Update the goal document with the new progress value
                goals_collection.update_one(
                    {"_id": goal_id},
                    {"$inc": {"progress": goal_progress}}  # Increment progress based on completion
                )

        # Record the completion history in the 'history' collection
        history_entry = {
            "task_reference_id": ObjectId(habit_id),
            "task_id": task_id,
            "is_completed": is_completed,
            "date": datetime.now(),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        result = history_collection.insert_one(history_entry)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error tracking habit: {e}")
        return None



# Schedule habit tasks based on frequency (daily, weekly, etc.)
def schedule_habit_task(habit_id):
    """
    Schedules the next task for a habit based on its frequency.

    This function calculates the next due date for a habit, considering its defined frequency
    (e.g., daily, weekly, etc.), and creates a task to track the habit's future completion. 
    The task will be automatically scheduled based on the habit's recurrence pattern.

    Args:
        habit_id (str): The ID of the habit for which the next task is being scheduled.

    Raises:
        Exception: If the habit is not found or an error occurs while scheduling the task, an exception is raised.
    """
    try:
        habit = get_habit_by_id(habit_id)
        if not habit:
            print(f"Habit with ID {habit_id} not found")
            return

        today = datetime.now()
        if habit["frequency"] == "daily":
            next_due = today + timedelta(days=1)
        elif habit["frequency"] == "weekly":
            next_due = today + timedelta(weeks=1)
        elif habit["frequency"] == "monthly":
            next_due = today + timedelta(days=30)
        elif habit["frequency"] == "quarterly":
            next_due = today + timedelta(days=90)
        elif habit["frequency"] == "yearly":
            next_due = today + timedelta(days=365)
        else:
            print(f"Invalid frequency: {habit['frequency']}")
            return
        
        # Create a new task for the next scheduled time
        create_task(
            title=f"Complete {habit['name']}",
            description=f"Complete the habit: {habit['name']}",
            due_date=next_due,
            priority=3,
            task_reference_id=habit_id  # Reference to the habit (generic reference)
        )
    except Exception as e:
        print(f"Error scheduling habit task: {e}")
