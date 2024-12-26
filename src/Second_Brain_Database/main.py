from flask import Flask
from Second_Brain_Database.auth.routes import auth_bp  # Import your auth blueprint


# Create Flask app
app = Flask(__name__)

# Register the authentication blueprint
app.register_blueprint(auth_bp, url_prefix='/auth')

# Run the application
if __name__ == '__main__':
    app.run(debug=True)
