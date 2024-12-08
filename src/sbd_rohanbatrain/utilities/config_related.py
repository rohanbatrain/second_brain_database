import os

def find_sbd_config(start_path=None):
    """
    Searches for the 'sbd_config.json' file by moving upwards from the specified directory.
    
    Parameters:
    start_path (str): The directory where the search begins. Default is the current working directory.
    
    Returns:
    str: The full path to the 'sbd_config.json' file, or a message indicating the file was not found.
    """
    # Default to the current working directory if no start_path is provided
    if start_path is None:
        start_path = os.getcwd()

    # Loop to traverse upwards through parent directories
    while True:
        # Check if the 'sbd_config.json' file exists in the current directory
        file_path = os.path.join(start_path, 'sbd_config.json')
        if os.path.isfile(file_path):
            return file_path  # Return the full path including filename

        # Move one directory up
        parent_dir = os.path.dirname(start_path)

        # If we've reached the root, break out of the loop
        if parent_dir == start_path:
            break

        start_path = parent_dir

    return "'sbd_config.json' not found."

# Example Usage

config_location = find_sbd_config() 
print(config_location)
