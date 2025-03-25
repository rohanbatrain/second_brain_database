from flask import Blueprint, request, jsonify
from Second_Brain_Database.auth.services import (
    create_user,
    authenticate_user,
    generate_jwt_token,
)
from Second_Brain_Database.auth.model import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.get_json()

    # Required fields
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    # Optional fields with defaults
    plan = data.get("plan", "free")
    team = data.get("team", [])

    # Ensure all required fields are provided
    if not username or not email or not password:
        return jsonify(
            {"status": "error",
             "message": "Missing required fields"}), 400

    # Check if the email already exists
    if User.find_by_email(email):
        return (
            jsonify({
                "status": "error",
                "message": "Email is already registered"
                }),
            400,
        )

    # Check if the username already exists
    if User.find_by_username(username):
        return jsonify(
            {
                "status": "error",
                "message": "Username is already taken"
            }), 400

    # Create and save the user
    create_user(username, email, password, plan, team)
    return jsonify({"status": "success",
                    "message": "User created successfully"}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login a user and return a token."""
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    # client = data.get("client")

    if not email or not password:
        return jsonify({"status": "error",
                        "message": "Missing required fields"}), 400

    # Authenticate user by email and password
    user = authenticate_user(email, password)
    if not user:
        return jsonify({"status": "error",
                        "message": "Invalid email or password"}), 401

    # Generate a JWT token
    token = generate_jwt_token(user)

    return (
        jsonify(
            {
                "status": "success",
                "message": "Login successful",
                "token": token,
                "role": "default",
            }
        ),
        200,
    )
