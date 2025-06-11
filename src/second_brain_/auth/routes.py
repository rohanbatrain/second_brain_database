"""
routes.py

Flask routes for authentication, registration, and email verification.

Dependencies:
    - Flask
    - itsdangerous
    - mailtrap
    - Second_Brain_Database.auth.services
    - Second_Brain_Database.auth.model
    - Second_Brain_Database.config

Author: Rohan Batra
Date: 2025-06-11
"""

from flask import Blueprint, jsonify, url_for, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import mailtrap as mt
from second_brain_database.auth.services import (
    create_user,
    authenticate_user,
    generate_jwt_token,
)
from second_brain_database.auth.model import User
from second_brain_database.config import SECRET_KEY, MT_API, MAIL_DEFAULT_SENDER, MAIL_SENDER_NAME

auth_bp = Blueprint("auth", __name__)

serializer = URLSafeTimedSerializer(SECRET_KEY)


def send_verification_email(email):
    """
    Helper function to send a verification email with HTML content.

    Args:
        email (str): The email address to send the verification to.

    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    try:
        token = serializer.dumps(email, salt="email-verification")
        verification_url = url_for("auth.verify_email", token=token, _external=True)

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #4CAF50; margin: 0;">Second Brain Database</h1>
                    <p style="color: #888; font-size: 14px;">Centralize your thoughts. Organize your world.</p>
                </div>
                <h2 style="color: #333;">Verify Your Email</h2>
                <p style="color: #555;">
                    Hi there,<br><br>
                    Thank you for signing up! Please verify your email address by clicking the button below:
                </p>
                <a href="{verification_url}"
                   style="display: inline-block; padding: 12px 24px; margin-top: 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px;">
                    Verify Email
                </a>
                <p style="color: #999; margin-top: 30px; font-size: 12px;">
                    If you did not sign up for this account, you can ignore this email.
                </p>
            </div>
        </body>
        </html>
        """

        mail = mt.Mail(
            sender=mt.Address(email=MAIL_DEFAULT_SENDER, name=MAIL_SENDER_NAME),
            to=[mt.Address(email=email)],
            subject="Verify Your Email",
            html=html_content
        )

        client = mt.MailtrapClient(token=MT_API)  # Replace with your Mailtrap API key
        client.send(mail)
        return True
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Failed to send verification email: {e} - {MT_API}")
        return False


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
    user = create_user(username, email, password, plan, team) # pylint: disable=unused-variable

    # Send verification email using Mailtrap
    if not send_verification_email(email):
        return jsonify({"status": "error", "message": "Failed to send verification email"}), 500

    return jsonify({"status": "success",
                    "message": "User created successfully. Please verify your email."
                    }), 201


@auth_bp.route("/verify-email", methods=["GET"])
def verify_email():
    """Verify a user's email."""
    token = request.args.get("token")
    if not token:
        return jsonify({"status": "error", "message": "Missing token"}), 400

    try:
        email = serializer.loads(token, salt="email-verification", max_age=3600)
        user = User.find_by_email(email)
        if user:
            user.update(is_verified=True)
            print("Email verified successfully")
            return jsonify({"status": "success", "message": "Email verified successfully"}), 200
        print("User not found")
        return jsonify({"status": "error", "message": "User not found"}), 404
    except SignatureExpired:
        print("Token expired")
        return jsonify({"status": "error", "message": "Token expired"}), 400
    except BadSignature:
        print("Invalid token")
        return jsonify({"status": "error", "message": "Invalid token"}), 400


@auth_bp.route("/resend", methods=["POST"])
def resend_verification():
    """Resend the verification email."""
    data = request.get_json()
    email = data.get("email")

    if not email:
        print("Missing email")
        return jsonify({"status": "error", "message": "Missing email"}), 400

    user = User.find_by_email(email)
    if not user:
        print("User not found")
        return jsonify({"status": "error", "message": "User not found"}), 404

    if user.is_verified:
        print("Email already verified")
        return jsonify({"status": "error", "message": "Email already verified"}), 400

    # Send verification email using Mailtrap
    if not send_verification_email(email):
        print("Failed to resend email")
        return jsonify({"status": "error", "message": "Failed to resend email"}), 500

    print("Verification email resent")
    return jsonify({"status": "success", "message": "Verification email resent"}), 200


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login a user and return a token."""
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    # client = data.get("client")

    if not email or not password:
        print("Missing required fields")
        return jsonify({"status": "error",
                        "message": "Missing required fields"}), 400

    # Authenticate user by email and password
    user = authenticate_user(email, password)
    if not user:
        print("Invalid email or password")
        return jsonify({"status": "error",
                        "message": "Invalid email or password"}), 401

    # Check if the user's email is verified
    if not user.is_verified:
        print("Please verify your email")
        return jsonify({"status": "error", "message": "Please verify your email"}), 403

    # Generate a JWT token
    token = generate_jwt_token(user)

    print("Login successful")
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
