import os
import glob
import logging

# Setup logger with basic configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_sbd_config(start_path="."):
    """
    Searches for the 'sbd_config.json' file starting from the specified directory, recursively.
    
    This function uses the `glob` module to search for the file in the given directory and all of its subdirectories.
    
    Parameters:
    start_path (str): The directory where the search begins. Default is the current directory (".").
    
    Returns:
    str: The path to the first found 'sbd_config.json' file, or a message indicating the file was not found.
    """
    
    # Validate if the given start_path is a valid directory
    if not os.path.isdir(start_path):
        logger.error(f"The path {start_path} is not a valid directory.")
        return f"The path {start_path} is not a valid directory."

    # Construct the search pattern
    search_pattern = os.path.join(start_path, '**', 'sbd_config.json')
    logger.info(f"Searching for 'sbd_config.json' in: {start_path}")

    # Use glob to find all matching files recursively
    config_files = glob.glob(search_pattern, recursive=True)

    if config_files:
        # Log the first found file path and return it
        logger.info(f"Found 'sbd_config.json' at: {config_files[0]}")
        return config_files[0]
    else:
        # Log if the file was not found
        logger.warning("'sbd_config.json' not found in the specified path.")
        return "'sbd_config.json' not found."

# config_location = find_sbd_config()