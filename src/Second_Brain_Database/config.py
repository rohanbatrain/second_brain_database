import os
import sys
import configparser
from pathlib import Path

def ensure_default_config(config_file, defaults):
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        parser = configparser.ConfigParser()
        parser['DEFAULT'] = defaults
        with open(config_file, 'w') as f:
            parser.write(f)

def load_sbd_config():
    config = {}
    config_file = None
    # Always use ~/.config/Second-Brain-Database/.sbd_config
    home = os.environ.get('HOME')
    if home:
        config_file = Path(home) / '.config' / 'Second-Brain-Database' / '.sbd_config'
    defaults = {
        'MONGO_URL': 'mongodb://mongo:27017',
        'MONGO_DB_NAME': 'your_application_db_name',
        'SECRET_KEY': 'your_super_long_and_random_secret_key_here_at_least_32_characters_or_more_for_security',
        'JWT_EXPIRY': '15m',
        'JWT_REFRESH_EXPIRY': '7d',
        'MT_API': 'your_third_party_api_key_here',
        'REDIS_HOST': 'redis',
        'REDIS_PORT': '6379',
        'REDIS_DB': '0',
        'REDIS_STORAGE_URI': 'redis://redis:6379/0',
        'MAIL_DEFAULT_SENDER': 'noreply@rohanbatra.in',
    }
    if config_file:
        ensure_default_config(config_file, defaults)
        parser = configparser.ConfigParser()
        parser.read(config_file)
        if 'DEFAULT' in parser:
            config = dict(parser['DEFAULT'])
    return config

sbd_config = load_sbd_config()

# Helper to get config value: prefer .sbd_config, else env, else default

def get_conf(key, default=None):
    value = sbd_config.get(key) or os.environ.get(key)
    if value is not None:
        return value
    # Provide hardcoded defaults if nothing is found
    defaults = {
        'MONGO_URL': 'mongodb://mongo:27017',
        'MONGO_DB_NAME': 'your_application_db_name',
        'SECRET_KEY': 'your_super_long_and_random_secret_key_here_at_least_32_characters_or_more_for_security',
        'JWT_EXPIRY': '15m',
        'JWT_REFRESH_EXPIRY': '7d',
        'MT_API': 'your_third_party_api_key_here',
        'REDIS_HOST': 'redis',
        'REDIS_PORT': '6379',
        'REDIS_DB': '0',
        'REDIS_STORAGE_URI': 'redis://redis:6379/0',
        'MAIL_DEFAULT_SENDER': 'noreply@rohanbatra.in',
        'DEBUG': 'false'
    }
    return defaults.get(key, default)

MONGO_URL = get_conf("MONGO_URL")
MONGO_DB_NAME = get_conf("MONGO_DB_NAME")
SECRET_KEY = get_conf("SECRET_KEY")
JWT_EXPIRY = get_conf("JWT_EXPIRY")
JWT_REFRESH_EXPIRY = get_conf("JWT_REFRESH_EXPIRY")
MAIL_DEFAULT_SENDER = get_conf("MAIL_DEFAULT_SENDER")
MT_API = get_conf("MT_API")
REDIS_HOST = get_conf("REDIS_HOST", "localhost")
REDIS_PORT = int(get_conf("REDIS_PORT", 6379))
REDIS_DB = int(get_conf("REDIS_DB", 0))
REDIS_STORAGE_URI = get_conf("REDIS_STORAGE_URI", f"redis://{REDIS_HOST}:{REDIS_PORT}")
DEBUG = get_conf("DEBUG", "false").lower() == "true"