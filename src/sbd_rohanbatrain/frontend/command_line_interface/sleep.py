import typer
from datetime import datetime
from sbd_rohanbatrain.database.db import sleep_collection
from sbd_rohanbatrain.features.sleep.sleep import check_entry

# Import update functions for date
from sbd_rohanbatrain.features.sleep.sleep_update.sleep_update_by_date import (
    update_bedtime as update_bedtime_by_date,
    update_wake_up_time as update_wake_up_time_by_date,
    update_total_sleep_time as update_total_sleep_time_by_date,
    update_sleep_cycles as update_sleep_cycles_by_date,
    update_sleep_rating as update_sleep_rating_by_date,
    update_dreams as update_dreams_by_date,
    add_awakening as add_awakening_by_date,
    update_general_quality as update_general_quality_by_date,
    update_room_temperature as update_room_temperature_by_date,
    update_noise_level as update_noise_level_by_date,
    update_light_exposure as update_light_exposure_by_date,
    update_sleep_position as update_sleep_position_by_date,
    update_bedding_comfort as update_bedding_comfort_by_date,
    update_pillow_type as update_pillow_type_by_date,
    update_mattress_type as update_mattress_type_by_date,
    update_sleeping_clothing as update_sleeping_clothing_by_date,
    update_sleep_aid_used as update_sleep_aid_used_by_date,
    update_sleep_temperature_preference as update_sleep_temperature_preference_by_date,
)

# Initialize the main Typer app
sleep_app = typer.Typer(help="Manage sleep logs.")

# Reference to the database collection
collection = sleep_collection

# Utility to get today's date if no date is provided
def get_date_or_default(date: str = None) -> str:
    return date or datetime.now().strftime("%Y-%m-%d")

# Command to create a new sleep log entry
@sleep_app.command("create", help="Create a new sleep log entry for a specific date.")
def add_a_new_record(date: str = None):
    try:
        result = check_entry(date)
        if result == 0:
            print(f"New sleep log entry created for date: {date or datetime.now().strftime('%Y-%m-%d')}.")
        else:
            print(f"Sleep log entry already exists for date: {date or datetime.now().strftime('%Y-%m-%d')}.")
    except Exception as e:
        print(f"An error occurred: {e}")

# Command to update sleep logs by date
@sleep_app.command("update", help="Update specific fields in sleep logs by date.")
def update_sleep_log_by_date(date: str = None, 
                             bedtime: str = None, 
                             wake_up_time: str = None, 
                             total_sleep_time: float = None, 
                             sleep_cycles: int = None, 
                             sleep_rating: int = None, 
                             dreams: str = None):
    date = get_date_or_default(date)  # Get today's date if no date is provided
    
    if bedtime:
        update_bedtime_by_date(date, bedtime)
    if wake_up_time:
        update_wake_up_time_by_date(date, wake_up_time)
    if total_sleep_time:
        update_total_sleep_time_by_date(date, total_sleep_time)
    if sleep_cycles:
        update_sleep_cycles_by_date(date, sleep_cycles)
    if sleep_rating:
        update_sleep_rating_by_date(date, sleep_rating)
    if dreams:
        update_dreams_by_date(date, dreams)

# Run the Typer app if executed as a script
if __name__ == "__main__":
    sleep_app()
