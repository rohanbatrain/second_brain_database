from flask import Flask
from flask_cors import CORS
from Second_Brain_Database.auth.routes import auth_bp 
from Second_Brain_Database.admin.plans.routes import plans_bp

# Create Flask app
app = Flask(__name__)
CORS(app)

# Register the authentication blueprint
app.register_blueprint(auth_bp, url_prefix='/auth')


# /admin routes
## /plan routes  
app.register_blueprint(plans_bp, url_prefix='/admin/plan')

# Run the application
if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
