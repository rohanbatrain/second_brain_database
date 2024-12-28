from flask import Blueprint, request, jsonify
from Second_Brain_Database.admin.plans.model import define_new_plan, update_plan
from Second_Brain_Database.utils.decorators.privileged import privileged_only  # Import the decorator

# Initialize the blueprint for plans
plans_bp = Blueprint("plans", __name__)

# Define the protected route for creating a new plan
@plans_bp.route("/create_plan", methods=["POST"])
@privileged_only  # Apply the privileged_only decorator
def create_plan(user):
    data = request.get_json()

    # Ensure the necessary fields are in the request body
    name = data.get("name")
    team_limit = data.get("team_limit")
    project_limit = data.get("project_limit")
    task_limit_per_project = data.get("task_limit_per_project")
    description = data.get("description", None)

    # Call the function to define and add the new plan
    result = define_new_plan(
        name, 
        team_limit, 
        project_limit, 
        task_limit_per_project, 
        description
    )

    # Return the response based on the result
    return jsonify(result)

# Define the protected route for updating an existing plan
@plans_bp.route("/update_plan", methods=["POST"])
@privileged_only  # Apply the privileged_only decorator
def update_plan_route(user):
    data = request.get_json()

    # Ensure the necessary fields are in the request body
    name = data.get("name")
    team_limit = data.get("team_limit", None)
    project_limit = data.get("project_limit", None)
    task_limit_per_project = data.get("task_limit_per_project", None)
    description = data.get("description", None)

    # Call the function to update the plan
    result = update_plan(
        name, 
        team_limit, 
        project_limit, 
        task_limit_per_project, 
        description
    )

    # Return the response based on the result
    return jsonify(result)
