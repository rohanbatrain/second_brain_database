"""
model.py

Data access and business logic for admin plan management in Second Brain Database.

Dependencies:
    - Second_Brain_Database.database

Author: Rohan Batra
Date: 2025-06-11
"""
from second_brain_database.database import db

# Initialize the plans collection
plans_collection = db["plans"]


def validate_limit(limit, limit_name):
    """
    Validate the limit value.

    Args:
        limit (int or str): The limit value to validate.
        limit_name (str): The name of the limit for error messages.

    Returns:
        dict: A response indicating the result of the validation.
    """
    if not isinstance(limit, (int, str)
                      ) or (isinstance(limit, int) and limit < 0):
        return {
            "status": "error",
            "message": f"{limit_name} must be a positive int or 'Unlimited'.",
        }
    return {"status": "success"}


def define_new_plan(
    name, team_limit, project_limit, task_limit_per_project, description=None
):
    """
    Define a new plan and add it to the 'plans' collection in MongoDB.

    Args:
        name (str): The name of the plan (e.g., "Free", "Basic").
        team_limit (int or str): The maximum number of team members allowed (use "Unlimited" for no limit).
        project_limit (int or str): The maximum number of projects allowed (use "Unlimited" for no limit).
        task_limit_per_project (int or str): The maximum number of tasks allowed per project (use "Unlimited" for no limit).
        description (str, optional): A short description of the plan.

    Returns:
        dict: A response indicating the result of the operation.
    """
    # Validate inputs
    if not isinstance(name, str) or not name.strip():
        return {"status": "error",
                "message": "Plan name must be a non-empty string."}

    for limit, limit_name in [
        (team_limit, "Team limit"),
        (project_limit, "Project limit"),
        (task_limit_per_project, "Task limit per project"),
    ]:
        validation_result = validate_limit(limit, limit_name)
        if validation_result["status"] == "error":
            return validation_result

    # Check if a plan with the same name already exists
    existing_plan = plans_collection.find_one({"name": name})
    if existing_plan:
        return {"status": "error", "message": f"Plan '{name}' already exists."}

    # Define the new plan
    new_plan = {
        "name": name,
        "team_limit": team_limit,
        "project_limit": project_limit,
        "task_limit_per_project": task_limit_per_project,
        "description": description or f"{name} Plan",
    }

    # Insert the new plan into the collection
    result = plans_collection.insert_one(new_plan)
    if result.inserted_id:
        return {
            "status": "success",
            "message": f"Plan '{name}' added successfully.",
            "plan_id": str(result.inserted_id),
        }
    else:
        return {"status": "error", "message": "Failed to add the plan."}


def update_plan(
    name,
    team_limit=None,
    project_limit=None,
    task_limit_per_project=None,
    description=None,
):
    """
    Update an existing plan in the 'plans' collection in MongoDB.

    Args:
        name (str): The name of the plan to update.
        team_limit (int or str, optional): The maximum number of team members allowed (use "Unlimited" for no limit).
        project_limit (int or str, optional): The maximum number of projects allowed (use "Unlimited" for no limit).
        task_limit_per_project (int or str, optional): The maximum number of tasks allowed per project (use "Unlimited" for no limit).
        description (str, optional): A short description of the plan.

    Returns:
        dict: A response indicating the result of the operation.
    """
    # Validate inputs
    if not isinstance(name, str) or not name.strip():
        return {"status": "error",
                "message": "Plan name must be a non-empty string."}

    updates = {}
    if team_limit is not None:
        validation_result = validate_limit(team_limit, "Team limit")
        if validation_result["status"] == "error":
            return validation_result
        updates["team_limit"] = team_limit

    if project_limit is not None:
        validation_result = validate_limit(project_limit, "Project limit")
        if validation_result["status"] == "error":
            return validation_result
        updates["project_limit"] = project_limit

    if task_limit_per_project is not None:
        validation_result = validate_limit(
            task_limit_per_project, "Task limit per project"
        )
        if validation_result["status"] == "error":
            return validation_result
        updates["task_limit_per_project"] = task_limit_per_project

    if description is not None:
        if not isinstance(description, str):
            return {"status": "error",
                    "message": "Description must be a string."}
        updates["description"] = description

    if not updates:
        return {"status": "error", "message": "No valid updates provided."}

    # Update the plan
    result = plans_collection.update_one({"name": name}, {"$set": updates})
    if result.matched_count:
        return {"status": "success",
                "message": f"Plan '{name}' updated successfully."}
    else:
        return {"status": "error", "message": f"Plan '{name}' not found."}


def delete_plan(name):
    """
    Delete an existing plan from the 'plans' collection in MongoDB.

    Args:
        name (str): The name of the plan to delete.

    Returns:
        dict: A response indicating the result of the operation.
    """
    # Validate inputs
    if not isinstance(name, str) or not name.strip():
        return {
            "status": "error",
            "message": "Plan name must be a non-empty string."
            }

    # Delete the plan
    result = plans_collection.delete_one({"name": name})
    if result.deleted_count:
        return {
            "status": "success",
            "message": f"Plan '{name}' deleted successfully."
            }
    else:
        return {"status": "error", "message": f"Plan '{name}' not found."}


def read_plan(name):
    """
    Read an existing plan from the 'plans' collection in MongoDB.

    Args:
        name (str): The name of the plan to read.

    Returns:
        dict: A response indicating the result of the operation.
    """
    # Validate inputs
    if not isinstance(name, str) or not name.strip():
        return {
            "status": "error",
            "message": "Plan name must be a non-empty string."
            }

    # Read the plan
    plan = plans_collection.find_one({"name": name})
    if plan:
        return {"status": "success", "plan": plan}
    else:
        return {"status": "error", "message": f"Plan '{name}' not found."}


def read_all_plans():
    """
    Read all plans from the 'plans' collection in MongoDB.

    Returns:
        dict: A response indicating the result of the operation.
    """
    # Read all plans
    all_plans = list(plans_collection.find())
    return {"status": "success", "plans": all_plans}
