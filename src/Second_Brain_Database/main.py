from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from Second_Brain_Database.auth.routes import auth_bp
from Second_Brain_Database.admin.v1.plans.routes import plans_bp
from Second_Brain_Database.user.v1.emotion_tracker.routes import emotion_bp

# Create Flask app
app = Flask(__name__)
CORS(app)

# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],  # Global rate limits
)

# Register the authentication blueprint
app.register_blueprint(auth_bp, url_prefix="/auth")

# /admin routes
# v1
# plans
app.register_blueprint(plans_bp, url_prefix="/admin/v1/plans")

# /user routes
# v1
# emotion tracker
app.register_blueprint(emotion_bp, url_prefix="/user/v1/emotion_tracker/")

# Run the application
if __name__ == "__main__":
    app.run(host="0.0.0.0")
