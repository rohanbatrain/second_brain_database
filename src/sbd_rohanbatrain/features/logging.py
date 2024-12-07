import logging
from logging.handlers import RotatingFileHandler
from pymongo import MongoClient
from datetime import datetime
from sbd_rohanbatrain.database.db import logging_collection

# Function to create a MongoDB log handler
def mongo_log_handler(db_uri, db_name, collection_name, formatter=None):
    """
    Function to create a MongoDB logging handler.
    """
    collection = logging_collection
    
    def emit(record):
        """
        Emit a log message to MongoDB.
        """
        log_entry = formatter.format(record) if formatter else record.getMessage()
        log_data = {
            "message": log_entry,
            "level": record.levelname,
            "timestamp": datetime.utcnow()
        }
        collection.insert_one(log_data)
    
    return emit

# Setup logger function
def setup_logger(log_file="sbd.log", level=logging.INFO, max_size=5 * 1024 * 1024, backup_count=3, db_uri="mongodb://localhost:27017/", db_name="logs_db", collection_name="logs"):
    """
    Set up a logger that writes to a file, console, and MongoDB collection.
    """
    logger = logging.getLogger("AppLogger")
    
    # Check if the logger already has handlers to avoid duplicate ones
    if logger.hasHandlers():
        return logger
    
    logger.setLevel(level)

    # File handler with rotation
    file_handler = RotatingFileHandler(log_file, maxBytes=max_size, backupCount=backup_count)
    file_handler.setLevel(level)

    # Define the log format
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # MongoDB handler (no need to subclass, using function)
    mongo_handler = mongo_log_handler(db_uri, db_name, collection_name, formatter)
    logger.addHandler(logging.Handler())
    logger.handlers[-1].emit = mongo_handler

    return logger

# # Example usage
# if __name__ == "__main__":
#     logger = setup_logger()

#     # Log various messages
#     logger.info("This is an info message.")
#     logger.error("This is an error message.")
#     logger.warning("This is a warning message.")
#     logger.debug("This is a debug message.")
