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


MT_API = os.environ.get("MT_API")



REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
REDIS_STORAGE_URI = os.environ.get("REDIS_STORAGE_URI", f"redis://{REDIS_HOST}:{REDIS_PORT}")