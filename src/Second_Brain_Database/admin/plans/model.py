from pymongo import MongoClient
from Second_Brain_Database.database import db

# Initialize the plans collection
plans_collection = db["plans"]

def define_new_plan(name, team_limit, project_limit, task_limit_per_project, description=None):
    """
    Define a new plan and add it to the 'plans' collection in MongoDB.

    Parameters:
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
        return {"status": "error", "message": "Plan name must be a non-empty string."}
    if not isinstance(team_limit, (int, str)) or (isinstance(team_limit, int) and team_limit < 0):
        return {"status": "error", "message": "Team limit must be a positive integer or 'Unlimited'."}
    if not isinstance(project_limit, (int, str)) or (isinstance(project_limit, int) and project_limit < 0):
        return {"status": "error", "message": "Project limit must be a positive integer or 'Unlimited'."}
    if not isinstance(task_limit_per_project, (int, str)) or (isinstance(task_limit_per_project, int) and task_limit_per_project < 0):
        return {"status": "error", "message": "Task limit per project must be a positive integer or 'Unlimited'."}

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
        "description": description or f"{name} Plan"
    }

    # Insert the new plan into the collection
    result = plans_collection.insert_one(new_plan)
    if result.inserted_id:
        return {"status": "success", "message": f"Plan '{name}' added successfully.", "plan_id": str(result.inserted_id)}
    else:
        return {"status": "error", "message": "Failed to add the plan."}


# # Example call to define_new_plan function
# name = "Pro"
# team_limit = 100  # Limit of 100 team members
# project_limit = 50  # Limit of 50 projects
# task_limit_per_project = 500  # Limit of 500 tasks per project
# description = "Pro Plan for enterprise-level teams."

# # Call the function to define the new plan
# result = define_new_plan(name, team_limit, project_limit, task_limit_per_project, description)

# # Print the result
# print(result)
