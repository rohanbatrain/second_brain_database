"""
config.py

Configuration management for Second Brain Database. Handles environment detection
(Docker vs. localhost), loads configuration from a user config file,
environment variables, or defaults,and exposes configuration values
for use throughout the application.

Dependencies:
    - os
    - json
    - pathlib

Author: Rohan Batra
Date: 2025-06-11
"""
import os
import json
from pathlib import Path

def is_docker():
    """
    Detect if the application is running inside a Docker container.

    Returns:
        bool: True if running in Docker, False otherwise.
    """
    print("Checking if running inside Docker container (is_docker)")
    if os.environ.get('IN_DOCKER') == '1':
        print("Detected Docker environment via IN_DOCKER env variable.")
        return True
    if Path('/.dockerenv').exists():
        print("Detected Docker environment via /.dockerenv file.")
        return True
    print("Not running inside Docker.")
    return False

# Cache the Docker environment check to avoid repeated prints and checks
IS_DOCKER = is_docker()

# Set defaults based on environment
print("Setting configuration defaults based on environment (Docker or localhost)")
if IS_DOCKER:
    defaults = {
        'MONGO_URL': 'mongodb://mongo:27017',
        'MONGO_DB_NAME': 'your_application_db_name',
        'SECRET_KEY': 'your_super_long_and_random_secret_key_here',
        'JWT_EXPIRY': '1h',
        'JWT_REFRESH_EXPIRY': '7d',
        'MT_API': 'your_third_party_api_key_here',
        'REDIS_HOST': 'redis',
        'REDIS_PORT': '6379',
        'REDIS_DB': '0',
        'REDIS_STORAGE_URI': 'redis://redis:6379/0',
        'MAIL_DEFAULT_SENDER': 'noreply@rohanbatra.in',
        'MAIL_SENDER_NAME': 'Rohan Batra',
    }
    print("Docker environment detected. Using Docker defaults.")
else:
    defaults = {
        'MONGO_URL': 'mongodb://127.0.0.1:27017',
        'MONGO_DB_NAME': 'your_application_db_name',
        'SECRET_KEY': 'your_super_long_and_random_secret_key_here_at_least_32_characters',
        'JWT_EXPIRY': '15m',
        'JWT_REFRESH_EXPIRY': '7d',
        'MT_API': 'your_third_party_api_key_here',
        'REDIS_HOST': '127.0.0.1',
        'REDIS_PORT': '6379',
        'REDIS_DB': '0',
        'REDIS_STORAGE_URI': 'redis://127.0.0.1:6379/0',
        'MAIL_DEFAULT_SENDER': 'noreply@rohanbatra.in',
        'MAIL_SENDER_NAME': 'Rohan Batra',
    }
    print("Localhost environment detected. Using localhost defaults.")

def ensure_default_config(config_file, default_values):
    """
    Ensure the default config file exists, creating it with defaults if not.

    Args:
        config_file (Path): Path to the config file.
        default_values (dict): Default configuration values.
    """
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        # Store all keys as upper case in JSON
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump({k.upper(): v for k, v in default_values.items()}, f, indent=2)
        print(f"Created default config file at {config_file}")

def load_sbd_config():
    """
    Load the Second Brain Database configuration from file, or use defaults.

    Returns:
        dict: Configuration values loaded from file or defaults.
    """
    config = {}
    config_file = None
    if IS_DOCKER:
        config_file = Path('/sbd_user/.config/Second-Brain-Database/.sbd_config.json')
    else:
        home = os.environ.get('HOME')
        if home:
            config_file = Path(home) / '.config' / 'Second-Brain-Database' / '.sbd_config.json'
    if config_file:
        if config_file.exists():
            print(f"[CONFIG] Loaded config file: {config_file}")
        else:
            print(f"[CONFIG] Config file not found, using defaults: {config_file}")
        ensure_default_config(config_file, defaults)
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # Ensure all keys are upper case
            config = {k.upper(): v for k, v in config.items()}
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[CONFIG] Error loading config file: {e}")
    return config

sbd_config = load_sbd_config()

# Helper to get config value: prefer .sbd_config, else env, else default

def get_conf(key, default=None):
    """
    Retrieve a configuration value, preferring .sbd_config, then environment, then defaults.

    Args:
        key (str): Configuration key.
        default (Any, optional): Fallback value if not found. Defaults to None.

    Returns:
        Any: The configuration value.
    """
    key = key.upper()
    value = sbd_config.get(key) or os.environ.get(key)
    if value is not None:
        return value
    return defaults.get(key, default)

MONGO_URL = get_conf("MONGO_URL")
MONGO_DB_NAME = get_conf("MONGO_DB_NAME")
SECRET_KEY = get_conf("SECRET_KEY")
JWT_EXPIRY = get_conf("JWT_EXPIRY")
JWT_REFRESH_EXPIRY = get_conf("JWT_REFRESH_EXPIRY")
MAIL_DEFAULT_SENDER = get_conf("MAIL_DEFAULT_SENDER")
MAIL_SENDER_NAME= get_conf("MAIL_SENDER_NAME", "Rohan Batra")
MT_API = get_conf("MT_API")
REDIS_HOST = get_conf("REDIS_HOST", "localhost")
REDIS_PORT = int(get_conf("REDIS_PORT", 6379))
REDIS_DB = int(get_conf("REDIS_DB", 0))
REDIS_STORAGE_URI = get_conf("REDIS_STORAGE_URI", f"redis://{REDIS_HOST}:{REDIS_PORT}")

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
