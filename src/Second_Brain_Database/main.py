from flask import Flask, request, abort
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis
import time
import os
from Second_Brain_Database.auth.routes import auth_bp
from Second_Brain_Database.admin.v1.plans.routes import plans_bp
from Second_Brain_Database.user.v1.emotion_tracker.routes import emotion_bp
from Second_Brain_Database.user.v1.notes.routes import notes_bp
from Second_Brain_Database.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_STORAGE_URI

# Create Flask app
app = Flask(__name__)
CORS(app)

# Initialize Redis for tracking abusive IPs
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

# Initialize Flask-Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=REDIS_STORAGE_URI,  # Use configurable Redis URI
    swallow_errors=True  # Prevent Flask from logging too many limit errors
)

# Middleware to block abusive IPs
@app.before_request
def block_abusive_ips():
    ip = request.remote_addr
    blocked = r.get(f"blocked:{ip}")
    if blocked:
        abort(403, description="You are temporarily blocked.")

# Middleware to track failed attempts and block IPs
@app.after_request
def track_failed_attempts(response):
    if response.status_code == 429:  # Too Many Requests
        ip = request.remote_addr
        r.incr(f"failed:{ip}")  # Increment failure count
        attempts = int(r.get(f"failed:{ip}") or 0)
        if attempts > 10:  # Block IP after 10 failures
            r.setex(f"blocked:{ip}", 3600, 1)  # Block for 1 hour
    return response

# Middleware for tar-pitting abusive IPs
@app.before_request
def slow_down_attackers():
    ip = request.remote_addr
    failed_attempts = int(r.get(f"failed:{ip}") or 0)
    if failed_attempts > 5:  # Delay only if user has failed 5+ times
        time.sleep(2)  # 2-second delay before processing request

@app.route("/")
def landing_page():
    """
    Landing page for the application.
    """
    return """<html>
    <head>
        <title>Welcome to Second Brain Database</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                background-color: #f4f4f9;
                color: #333;
                margin: 0;
                padding: 0;
            }
            header {
                background-color: #6200ea;
                color: white;
                padding: 20px 0;
            }
            h1 {
                margin: 0;
            }
            p {
                font-size: 18px;
            }
            footer {
                margin-top: 20px;
                font-size: 14px;
                color: #777;
            }
        </style>
    </head>
    <body>
        <header>
            <h1>Welcome to Second Brain Database</h1>
        </header>
        <main>
            <p>Your one-stop solution for managing notes, emotions, and plans.</p>
            <p>Navigate to the login or register page to get started!</p>
        </main>
        <footer>
            <p>&copy; 2023 Second Brain Database. All rights reserved.</p>
        </footer>
    </body>
    </html>"""

@app.route("/login")
def login_page():
    """
    Serve the login page.
    """
    return """<html><head><title>Login</title></head><body><h1>Login Page</h1></body></html>"""

@app.route("/register")
def register_page():
    """
    Serve the register page.
    """
    return """<html><head><title>Register</title></head><body><h1>Register Page</h1></body></html>"""

# Custom error handlers
@app.errorhandler(404)
def not_found_error(error):
    return """<html><head><title>404 Not Found</title></head><body><h1>404 - Page Not Found</h1></body></html>""", 404

@app.errorhandler(401)
def unauthorized_error(error):
    return """<html><head><title>401 Unauthorized</title></head><body><h1>401 - Unauthorized</h1></body></html>""", 401

@app.errorhandler(403)
def forbidden_error(error):
    return """<html><head><title>403 Forbidden</title></head><body><h1>403 - Forbidden</h1></body></html>""", 403

@app.errorhandler(500)
def internal_server_error(error):
    return """<html><head><title>500 Internal Server Error</title></head><body><h1>500 - Internal Server Error</h1></body></html>""", 500

# Register the authentication blueprint
app.register_blueprint(auth_bp, url_prefix="/auth")
limiter.limit("10 per minute")(auth_bp)

# /admin routes
# v1
# plans
app.register_blueprint(plans_bp, url_prefix="/admin/v1/plans")
limiter.limit("5 per minute")(plans_bp)

# /user routes
# v1
# emotion tracker
app.register_blueprint(emotion_bp, url_prefix="/user/v1/emotion_tracker/")
limiter.limit("20 per minute")(emotion_bp)
# notes
app.register_blueprint(notes_bp, url_prefix="/user/v1/notes/")
limiter.limit("15 per minute")(notes_bp)

# Expose the Flask app as `application` for Gunicorn
application = app


# Run the application
if __name__ == "__main__":
    application.run(host="0.0.0.0")
