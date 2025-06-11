"""
main.py

Flask application entry point for Second Brain Database. Sets up routes, middleware, rate
limiting, and error handling.

Dependencies:
    - Flask
    - flask_cors
    - flask_limiter
    - redis
    - logging
    - Second_Brain_Database.*

Author: Rohan Batra
Date: 2025-06-11
"""
import logging
import time
from flask import Flask, request, abort
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis
from second_brain_database.auth.routes import auth_bp
from second_brain_database.admin.v1.plans.routes import plans_bp
from second_brain_database.user.v1.emotion_tracker.routes import emotion_bp
from second_brain_database.user.v1.notes.routes import notes_bp
from second_brain_database.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_STORAGE_URI

logger = logging.getLogger(__name__)

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

@app.before_request
def block_abusive_ips():
    """
    Block requests from IPs that are currently blocked in Redis.
    Raises:
        403: If the IP is blocked.
    """
    ip = request.remote_addr
    blocked = r.get(f"blocked:{ip}")
    if blocked:
        print(f"Blocked request from IP: {ip}")
        abort(403, description="You are temporarily blocked.")

@app.after_request
def track_failed_attempts(response):
    """
    Track failed requests and block IPs after too many failures.
    Args:
        response (flask.Response): The response object.
    Returns:
        flask.Response: The response object.
    """
    if response.status_code == 429:  # Too Many Requests
        ip = request.remote_addr
        r.incr(f"failed:{ip}")  # Increment failure count
        attempts = int(r.get(f"failed:{ip}") or 0)
        if attempts > 10:  # Block IP after 10 failures
            r.setex(f"blocked:{ip}", 3600, 1)  # Block for 1 hour
            print(f"IP {ip} blocked for 1 hour after {attempts} failures.")
    return response

@app.before_request
def slow_down_attackers():
    """
    Introduce a delay for IPs with multiple failed attempts (tar-pitting).
    """
    ip = request.remote_addr
    failed_attempts = int(r.get(f"failed:{ip}") or 0)
    if failed_attempts > 5:  # Delay only if user has failed 5+ times
        print(f"Delaying request from IP {ip} due to {failed_attempts} failed attempts.")
        time.sleep(2)  # 2-second delay before processing request

@app.route("/")
def landing_page():
    """
    Landing page for the application.
    Returns:
        str: HTML content for the landing page.
    """
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Welcome to Second Brain Database</title>

  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">

  <style>
    body {
      font-family: 'Inter', sans-serif;
      margin: 0;
      padding: 0;
      overflow: hidden;
      background: #0a0a0a;
    }

    .glass-bg {
      position: fixed;
      inset: 0;
      background: rgba(255, 255, 255, 0.05);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.08);
      animation: subtleGlow 6s ease-in-out infinite;
    }

    .glass-bg::before {
      content: "";
      position: absolute;
      inset: -5px;
      background: linear-gradient(135deg, rgba(255,255,255,0.2), rgba(255,255,255,0.05));
      z-index: -1;
      filter: blur(30px);
      border-radius: inherit;
      animation: subtleGlow 8s ease-in-out infinite;
    }

    @keyframes subtleGlow {
      0%, 100% { opacity: 0.4; }
      50% { opacity: 0.9; }
    }
  </style>
</head>
<body class="flex items-center justify-center min-h-screen text-white">

  <!-- Fullscreen Glass Background -->
  <div class="glass-bg z-0"></div>

  <!-- Centered Content -->
  <div class="relative z-10 text-center px-6">
    <h1 class="text-4xl md:text-6xl font-extrabold tracking-tight">
      Welcome to<br>Second Brain Database API
    </h1>
    <p class="mt-6 text-lg text-white/70">
      A centralized, elegant engine for personal knowledge management.
    </p>
  </div>

</body>
</html>

"""

@app.route("/login")
def login_page():
    """
    Serve the login page.
    Returns:
        str: HTML content for the login page.
    """
    return """<html><head><title>Login</title></head><body><h1>Login Page</h1></body></html>"""

@app.route("/register")
def register_page():
    """
    Serve the register page.
    Returns:
        str: HTML content for the register page.
    """
    return """<html><head><title>Register</title></head>
    <body><h1>Register Page</h1></body></html>"""

@app.errorhandler(404)
def not_found_error(error):  # pylint: disable=unused-argument
    """
    Handle 404 Not Found errors.
    Args:
        error (Exception): The error object.
    Returns:
        tuple: HTML content and status code.
    """
    return (
        """<html><head><title>404 Not Found</title></head><body><h1>404 - Page Not Found</h1>"
        "</body></html>""",
        404,
    )

@app.errorhandler(401)
def unauthorized_error(error):  # pylint: disable=unused-argument
    """
    Handle 401 Unauthorized errors.
    Args:
        error (Exception): The error object.
    Returns:
        tuple: HTML content and status code.
    """
    return (
        """<html><head><title>401 Unauthorized</title></head><body><h1>401 - Unauthorized</h1>"
        "</body></html>""",
        401,
    )

@app.errorhandler(403)
def forbidden_error(error):  # pylint: disable=unused-argument
    """
    Handle 403 Forbidden errors.
    Args:
        error (Exception): The error object.
    Returns:
        tuple: HTML content and status code.
    """
    return (
        """<html><head><title>403 Forbidden</title></head><body><h1>403 - Forbidden</h1>"
        "</body></html>""",
        403,
    )

@app.errorhandler(500)
def internal_server_error(error):  # pylint: disable=unused-argument
    """
    Handle 500 Internal Server Error errors.
    Args:
        error (Exception): The error object.
    Returns:
        tuple: HTML content and status code.
    """
    return (
        """<html><head><title>500 Internal Server Error</title>
        </head><body><h1>500 - Internal Server Error</h1>"
        "</body></html>""",
        500,
    )

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
app.register_blueprint(
    notes_bp,
    url_prefix="/user/v1/notes/"
)
limiter.limit("15 per minute")(notes_bp)

# Expose the Flask app as `application` for Gunicorn
application = app

# Run the application
if __name__ == "__main__":
    application.run(host="0.0.0.0")
