from flask import Blueprint, request, jsonify
from functools import wraps
from Second_Brain_Database.auth.services import decode_jwt_token
from Second_Brain_Database.auth.model import User

# Helper function to check if the user is privileged
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"status": "unauthorized", "message": "No token provided."}), 401
        
        # Remove "Bearer " prefix from the token if it exists
        if token.startswith("Bearer "):
            token = token[7:]
        
        # Decode the token
        payload = decode_jwt_token(token)
        if not payload:
            return jsonify({"status": "unauthorized", "message": "Invalid or expired token."}), 401
        
        # Get user from email in the payload
        user = User.find_by_email(payload['email'])
        if not user or not user.is_admin:
            return jsonify({"status": "forbidden", "message": "You do not have the required privileges."}), 403
        
        # Pass user data to the route
        return f(user, *args, **kwargs)
    return decorated_function

def user_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"status": "unauthorized", "message": "No token provided."}), 401
        
        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        
        # Decode the token
        payload = decode_jwt_token(token)
        if not payload:
            return jsonify({"status": "unauthorized", "message": "Invalid or expired token."}), 401
        
        # Get user from email in the payload
        user = User.find_by_email(payload['email'])
        if not user:
            return jsonify({"status": "unauthorized", "message": "User not found."}), 401

        # Pass user data to the route
        return f(user, *args, **kwargs)
    return decorated_function