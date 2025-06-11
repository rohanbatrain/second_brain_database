"""
routes.py

Flask routes for admin plan management (CRUD) for privileged users.

Dependencies:
    - Flask
    - Second_Brain_Database.admin.v1.plans.model
    - Second_Brain_Database.utils.decorators.privileged

Author: Rohan Batra
Date: 2025-06-11
"""

from flask import Blueprint, request, jsonify
from second_brain_database.admin.v1.plans.model import (
    define_new_plan,
    delete_plan,
    read_all_plans,
    read_plan,
    update_plan,
)
from second_brain_database.utils.decorators.privileged import admin_only

# Initialize the blueprint for plans
plans_bp = Blueprint("plans", __name__)


# Define the protected route for creating a new plan
@plans_bp.route("/create_plan", methods=["POST"])
@admin_only  # Apply the admin_only decorator
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
        name, team_limit, project_limit, task_limit_per_project, description
    )

    # Return the response based on the result
    return jsonify(result)


# Define the protected route for updating an existing plan
@plans_bp.route("/update_plan", methods=["POST"])
@admin_only  # Apply the admin_only decorator
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
        name, team_limit, project_limit, task_limit_per_project, description
    )

    # Return the response based on the result
    return jsonify(result)


# Define the protected route for reading all plans
@plans_bp.route("/read_all_plans", methods=["GET"])
@admin_only  # Apply the admin_only decorator
def read_all_plans_route(user):
    # Call the function to read all plans
    result = read_all_plans()

    # Return the response based on the result
    return jsonify(result)


# Define the protected route for reading an existing plan
@plans_bp.route("/read_plan/<plan_id>", methods=["GET"])
@admin_only  # Apply the admin_only decorator
def read_plan_route(user, plan_id):
    # Call the function to read the plan
    result = read_plan(plan_id)

    # Return the response based on the result
    return jsonify(result)


# Define the protected route for deleting an existing plan
@plans_bp.route("/delete_plan/<plan_id>", methods=["DELETE"])
@admin_only  # Apply the admin_only decorator
def delete_plan_route(user, plan_id):
    # Call the function to delete the plan
    result = delete_plan(plan_id)

    # Return the response based on the result
    return jsonify(result)
