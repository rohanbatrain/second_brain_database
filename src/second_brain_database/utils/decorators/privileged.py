"""
privileged.py

This module provides Flask route decorators for enforcing user authentication and authorization (admin-only and user-only access).

Dependencies:
    - Flask (request, jsonify)
    - functools.wraps
    - Second_Brain_Database.auth.services.decode_jwt_token
    - Second_Brain_Database.auth.model.User

Author: Rohan Batra
Date: 2025-06-11
"""
from flask import request, jsonify
from functools import wraps
from second_brain_database.auth.services import decode_jwt_token
from second_brain_database.auth.model import User


def admin_only(f):
    """
    Decorator to restrict access to admin users only.

    Args:
        f (function): The Flask route function to decorate.

    Returns:
        function: The decorated function that enforces admin-only access.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return (
                jsonify({"status": "unauthorized",
                         "message": "No token provided."}),
                401,
            )

        # Remove "Bearer " prefix from the token if it exists
        if token.startswith("Bearer "):
            token = token[7:]

        # Decode the token
        payload = decode_jwt_token(token)
        if not payload:
            return (
                jsonify(
                    {
                        "status": "unauthorized",
                        "message": "Invalid or expired token."
                    }
                ),
                401,
            )

        # Get user from email in the payload
        user = User.find_by_email(payload["email"])
        if not user or not user.is_admin:
            return (
                jsonify(
                    {
                        "status": "forbidden",
                        "message": "You do not have the required privileges.",
                    }
                ),
                403,
            )

        # Pass user data to the route
        return f(user, *args, **kwargs)

    return decorated_function


def user_only(f):
    """
    Decorator to restrict access to authenticated users only.

    Args:
        f (function): The Flask route function to decorate.

    Returns:
        function: The decorated function that enforces user authentication.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return (
                jsonify({
                    "status": "unauthorized",
                    "message": "No token provided."
                    }),
                401,
            )

        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        # Decode the token
        payload = decode_jwt_token(token)
        if not payload:
            return (
                jsonify(
                    {
                        "status": "unauthorized",
                        "message": "Invalid or expired token."
                    }
                ),
                401,
            )

        # Get user from email in the payload
        user = User.find_by_email(payload["email"])
        if not user:
            return (
                jsonify({
                    "status": "unauthorized",
                    "message": "User not found."}),
                401,
            )

        # Pass user data to the route
        return f(user, *args, **kwargs)

    return decorated_function
