import os

MONGO_URL = os.environ.get("MONGO_URL")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME")
SECRET_KEY = os.environ.get("SECRET_KEY")
JWT_EXPIRY = os.environ.get("JWT_EXPIRY")
JWT_REFRESH_EXPIRY = os.environ.get("JWT_REFRESH_EXPIRY")
MAIL_SERVER = os.environ.get("MAIL_SERVER")
MAIL_PORT = os.environ.get("MAIL_PORT")
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS")
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")


# print(JWT_EXPIRY)

# # Print each value to test
# print("MONGO_URL:", MONGO_URL)
# print("MONGO_DB_NAME:", MONGO_DB_NAME)
# print("SECRET_KEY:", SECRET_KEY)
# print("JWT_EXPIRY:", JWT_EXPIRY)
# print("JWT_REFRESH_EXPIRY:", JWT_REFRESH_EXPIRY)
# print("MAIL_SERVER:", MAIL_SERVER)
# print("MAIL_PORT:", MAIL_PORT)
# print("MAIL_USE_TLS:", MAIL_USE_TLS)
# print("MAIL_USERNAME:", MAIL_USERNAME)
# print("MAIL_PASSWORD:", MAIL_PASSWORD)
# print("MAIL_DEFAULT_SENDER:", MAIL_DEFAULT_SENDER)