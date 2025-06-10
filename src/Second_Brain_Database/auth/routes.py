from flask import Blueprint, jsonify, current_app, url_for, request
from Second_Brain_Database.auth.services import (
    create_user,
    authenticate_user,
    generate_jwt_token,
)
from Second_Brain_Database.auth.model import User
from itsdangerous import URLSafeTimedSerializer
from Second_Brain_Database.config import SECRET_KEY, MT_API
import mailtrap as mt  # Import Mailtrap library

auth_bp = Blueprint("auth", __name__)

serializer = URLSafeTimedSerializer(SECRET_KEY)


def send_verification_email(email):
    """Helper function to send a verification email with HTML content."""
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
                <a href="{verification_url}" style="display: inline-block; padding: 12px 24px; margin-top: 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px;">
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
            sender=mt.Address(email="noreply@rohanbatra.in", name="Rohan Batra"),
            to=[mt.Address(email=email)],
            subject="Verify Your Email",
            html=html_content,
            reply_to=mt.Address(email="noreply@rohanbatra.in")
        )

        client = mt.MailtrapClient(token=MT_API)  # Replace with your Mailtrap API key
        client.send(mail)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send verification email: {e}")
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
    user = create_user(username, email, password, plan, team)

    # Send verification email using Mailtrap
    if not send_verification_email(email):
        return jsonify({"status": "error", "message": "Failed to send verification email"}), 500

    return jsonify({"status": "success", "message": "User created successfully. Please verify your email."}), 201


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
            return jsonify({"status": "success", "message": "Email verified successfully"}), 200
        else:
            return jsonify({"status": "error", "message": "User not found"}), 404
    except SignatureExpired:
        return jsonify({"status": "error", "message": "Token expired"}), 400
    except BadSignature:
        return jsonify({"status": "error", "message": "Invalid token"}), 400


@auth_bp.route("/resend", methods=["POST"])
def resend_verification():
    """Resend the verification email."""
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"status": "error", "message": "Missing email"}), 400

    user = User.find_by_email(email)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    if user.is_verified:
        return jsonify({"status": "error", "message": "Email already verified"}), 400

    # Send verification email using Mailtrap
    if not send_verification_email(email):
        return jsonify({"status": "error", "message": "Failed to resend email"}), 500

    return jsonify({"status": "success", "message": "Verification email resent"}), 200


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

    # Check if the user's email is verified
    if not user.is_verified:
        return jsonify({"status": "error", "message": "Please verify your email"}), 403

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
