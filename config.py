import os

# Ensure sbd_config and defaults are defined
sbd_config = {}
defaults = {
    'MONGO_URL': None,
    'MONGO_DB_NAME': None,
    'SECRET_KEY': None,
    'JWT_EXPIRY': None,
    'JWT_REFRESH_EXPIRY': None,
    'MAIL_DEFAULT_SENDER': None,
    'MAIL_SENDER_NAME': None,
    'MT_API': None,
    'REDIS_HOST': None,
    'REDIS_PORT': None,
    'REDIS_DB': None,
    'REDIS_STORAGE_URI': None
}

def printenv_config():
    """
    Print the effective configuration values from config, environment, and defaults.
    """
    print("\n[ENV/CONFIG] Effective configuration values:")
    for key in [
        'MONGO_URL', 'MONGO_DB_NAME', 'SECRET_KEY', 'JWT_EXPIRY', 'JWT_REFRESH_EXPIRY',
        'MAIL_DEFAULT_SENDER', 'MAIL_SENDER_NAME', 'MT_API',
        'REDIS_HOST', 'REDIS_PORT', 'REDIS_DB', 'REDIS_STORAGE_URI']:
        value = sbd_config.get(key) or os.getenv(key) or defaults.get(key)
        source = (
            "(from config)" if key in sbd_config else
            "(from env)" if os.getenv(key) else
            "(from default)"
        )
        print(f"{key} = {value}   {source}")
    print()