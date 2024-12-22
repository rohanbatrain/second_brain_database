import logging

# Set up basic logging configuration
def setup_logger(log_file='sbd.logs', log_level=logging.DEBUG):
    # Create a logger object
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Create a file handler to log to a file
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)

    # Create a console handler to log to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Define a log message format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()