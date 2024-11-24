import os
import glob

def find_sbd_config(start_path="."):
    # Search for 'sbd_config.json' starting from the provided path (default is current directory).
    # The '**' allows searching in subdirectories recursively.
    search_pattern = os.path.join(start_path, '**', 'sbd_config.json')
    
    # Use glob.glob to find all matching files, with recursive search enabled.
    config_files = glob.glob(search_pattern, recursive=True)
    
    # If any config file is found, return the path of the first one.
    if config_files:
        return config_files[0]
    else:
        # If no config file is found, return a message indicating this.
        return "sbd_config.json not found."

# Using the function to search for 'sbd_config.json' and storing the result in a variable.
# This variable can be imported into other files in the package if needed.
config_file_path = find_sbd_config()