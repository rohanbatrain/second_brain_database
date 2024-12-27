from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
from Second_Brain_Database.config import SECRET_KEY
from Second_Brain_Database.auth.model import User
from Second_Brain_Database.auth.services import decode_jwt_token
from Second_Brain_Database.utils.decorators.priviedged import privileged_only

# Initialize routes blueprint
privilege_bp = Blueprint("privilege", __name__)

# Define a protected route
@privilege_bp.route("/hi", methods=["GET"])
@privileged_only
def protected_resource(user):
    return jsonify({
        "status": "success",
        "message": "Welcome to the privilege only endpoint!",
        "user": {"email": user.email, "username": user.username}
    })
