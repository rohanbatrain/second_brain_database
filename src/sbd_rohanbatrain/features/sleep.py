from datetime import datetime
from sbd_rohanbatrain.database.db import sleep_collection

collection = sleep_collection

def check_entry(date=None):
    """
    Checks if a sleep log entry exists for the given date.

    If no entry exists, a new entry is created.

    Args:
        date (str, optional): The date to check in "YYYY-MM-DD" format. Defaults to today's date.

    Returns:
        int: Returns 0 if a new entry is created, 1 if an entry already exists.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    if not collection.find_one({"date": date}):
        create_entry(date)
        return 0
    else:
        return 1


def create_entry(date=None):
    """
    Creates a new sleep log entry for the specified date.

    Args:
        date (str, optional): The date for the new entry in "YYYY-MM-DD" format. Defaults to None.

    Returns:
        dict: The created entry.
    """
    entry = {
        "date": date,
        "duration": {},
        "quality": {},
        "environment": {}
    }
    collection.insert_one(entry)
    return entry


# Duration Field Updates
def update_bedtime(date, bedtime):
    """
    Updates the bedtime for the given date.

    Args:
        date (str): The date of the entry.
        bedtime (str): The bedtime in "HH:MM" format.
    """
    collection.update_one({"date": date}, {"$set": {"duration.bedtime": bedtime}})
    print("Bedtime updated.")


def update_wake_up_time(date, wake_up_time):
    """
    Updates the wake-up time for the given date.

    Args:
        date (str): The date of the entry.
        wake_up_time (str): The wake-up time in "HH:MM" format.
    """
    collection.update_one({"date": date}, {"$set": {"duration.wake_up_time": wake_up_time}})
    print("Wake-up time updated.")


def update_total_sleep_time(date, total_sleep_time):
    """
    Updates the total sleep time for the given date.

    Args:
        date (str): The date of the entry.
        total_sleep_time (float): The total sleep time in hours.
    """
    collection.update_one({"date": date}, {"$set": {"duration.total_sleep_time": f"{total_sleep_time:.2f} hours"}})
    print("Total sleep time updated.")


def update_sleep_cycles(date, sleep_cycles):
    """
    Updates the sleep cycles for the given date.

    Args:
        date (str): The date of the entry.
        sleep_cycles (int): The number of sleep cycles.
    """
    collection.update_one({"date": date}, {"$set": {"duration.sleep_cycles": sleep_cycles}})
    print("Sleep cycles updated.")


# Quality Field Updates
def update_sleep_rating(date, sleep_rating):
    """
    Updates the sleep rating for the given date.

    Args:
        date (str): The date of the entry.
        sleep_rating (int): The sleep rating (e.g., on a scale of 1 to 10).
    """
    collection.update_one({"date": date}, {"$set": {"quality.sleep_rating": sleep_rating}})
    print("Sleep rating updated.")


def update_dreams(date, dreams):
    """
    Updates the dreams description for the given date.

    Args:
        date (str): The date of the entry.
        dreams (str): Description of the dreams.
    """
    collection.update_one({"date": date}, {"$set": {"quality.dreams": dreams}})
    print("Dreams updated.")


def add_awakening(date, time, disruption_cause):
    """
    Adds an awakening record for the given date.

    Args:
        date (str): The date of the entry.
        time (str): The time of awakening in "HH:MM" format.
        disruption_cause (str): The cause of the awakening.
    """
    awakening = {"time": time, "disruption_cause": disruption_cause}
    collection.update_one({"date": date}, {"$push": {"quality.awakenings": awakening}})
    print("Awakening added.")


def update_general_quality(date, general_quality):
    """
    Updates the general sleep quality description for the given date.

    Args:
        date (str): The date of the entry.
        general_quality (str): A general description of sleep quality.
    """
    collection.update_one({"date": date}, {"$set": {"quality.general_quality": general_quality}})
    print("General sleep quality updated.")


# Environment Field Updates
def update_room_temperature(date, room_temperature):
    """
    Updates the room temperature for the given date.

    Args:
        date (str): The date of the entry.
        room_temperature (float): The room temperature in degrees.
    """
    collection.update_one({"date": date}, {"$set": {"environment.room_temperature": room_temperature}})
    print("Room temperature updated.")


def update_noise_level(date, noise_level):
    """
    Updates the noise level for the given date.

    Args:
        date (str): The date of the entry.
        noise_level (str): The noise level description (e.g., "quiet", "noisy").
    """
    collection.update_one({"date": date}, {"$set": {"environment.noise_level": noise_level}})
    print("Noise level updated.")


def update_light_exposure(date, light_exposure):
    """
    Updates the light exposure for the given date.

    Args:
        date (str): The date of the entry.
        light_exposure (str): The light exposure description (e.g., "dark", "dim", "bright").
    """
    collection.update_one({"date": date}, {"$set": {"environment.light_exposure": light_exposure}})
    print("Light exposure updated.")


def update_sleep_position(date, sleep_position):
    """
    Updates the sleep position for the given date.

    Args:
        date (str): The date of the entry.
        sleep_position (str): The sleep position description (e.g., "back", "side").
    """
    collection.update_one({"date": date}, {"$set": {"environment.sleep_position": sleep_position}})
    print("Sleep position updated.")


def update_bedding_comfort(date, bedding_comfort):
    """
    Updates the bedding comfort for the given date.

    Args:
        date (str): The date of the entry.
        bedding_comfort (str): Description of the bedding comfort.
    """
    collection.update_one({"date": date}, {"$set": {"environment.bedding_comfort": bedding_comfort}})
    print("Bedding comfort updated.")


def update_pillow_type(date, pillow_type):
    """
    Updates the pillow type for the given date.

    Args:
        date (str): The date of the entry.
        pillow_type (str): The type of pillow used.
    """
    collection.update_one({"date": date}, {"$set": {"environment.pillow_type": pillow_type}})
    print("Pillow type updated.")


def update_mattress_type(date, mattress_type):
    """
    Updates the mattress type for the given date.

    Args:
        date (str): The date of the entry.
        mattress_type (str): The type of mattress used.
    """
    collection.update_one({"date": date}, {"$set": {"environment.mattress_type": mattress_type}})
    print("Mattress type updated.")


def update_sleeping_clothing(date, sleeping_clothing):
    """
    Updates the sleeping clothing for the given date.

    Args:
        date (str): The date of the entry.
        sleeping_clothing (str): Description of the sleeping clothing.
    """
    collection.update_one({"date": date}, {"$set": {"environment.sleeping_clothing": sleeping_clothing}})
    print("Sleeping clothing updated.")


def update_sleep_aid_used(date, sleep_aid_used):
    """
    Updates the sleep aid used for the given date.

    Args:
        date (str): The date of the entry.
        sleep_aid_used (str): Description of the sleep aid used.
    """
    collection.update_one({"date": date}, {"$set": {"environment.sleep_aid_used": sleep_aid_used}})
    print("Sleep aid used updated.")


def update_sleep_temperature_preference(date, sleep_temperature_preference):
    """
    Updates the sleep temperature preference for the given date.

    Args:
        date (str): The date of the entry.
        sleep_temperature_preference (str): Description of the preferred sleep temperature.
    """
    collection.update_one({"date": date}, {"$set": {"environment.sleep_temperature_preference": sleep_temperature_preference}})
    print("Sleep temperature preference updated.")


# Calling check_entry 
# if check_entry() == 0:
#     print(f"Entry created for {date}.")
# elif check_entry() == 1:
#     print("Entry for this date already exists.")
# else:
#     print("unknown error")
# Calling update bedtime

