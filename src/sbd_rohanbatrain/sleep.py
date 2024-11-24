from datetime import datetime
from db import sleep

collection = sleep


def check_entry(date=None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    if not collection.find_one({"date": date}):
        create_entry(date)
        # print(f"Entry created for {date}.")
        return 0
    else:
        # print("Entry for this date already exists.")
        return 1
    

def create_entry(date=None):
    """Initializes a new sleep log entry for a given date."""
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
    collection.update_one({"date": date}, {"$set": {"duration.bedtime": bedtime}})
    print("Bedtime updated.")

def update_wake_up_time(date, wake_up_time):
    collection.update_one({"date": date}, {"$set": {"duration.wake_up_time": wake_up_time}})
    print("Wake-up time updated.")

def update_total_sleep_time(date, total_sleep_time):
    collection.update_one({"date": date}, {"$set": {"duration.total_sleep_time": f"{total_sleep_time:.2f} hours"}})
    print("Total sleep time updated.")

def update_sleep_cycles(date, sleep_cycles):
    collection.update_one({"date": date}, {"$set": {"duration.sleep_cycles": sleep_cycles}})
    print("Sleep cycles updated.")

# Quality Field Updates
def update_sleep_rating(date, sleep_rating):
    collection.update_one({"date": date}, {"$set": {"quality.sleep_rating": sleep_rating}})
    print("Sleep rating updated.")

def update_dreams(date, dreams):
    collection.update_one({"date": date}, {"$set": {"quality.dreams": dreams}})
    print("Dreams updated.")

def add_awakening(date, time, disruption_cause):
    awakening = {"time": time, "disruption_cause": disruption_cause}
    collection.update_one({"date": date}, {"$push": {"quality.awakenings": awakening}})
    print("Awakening added.")

def update_general_quality(date, general_quality):
    collection.update_one({"date": date}, {"$set": {"quality.general_quality": general_quality}})
    print("General sleep quality updated.")

# Environment Field Updates
def update_room_temperature(date, room_temperature):
    collection.update_one({"date": date}, {"$set": {"environment.room_temperature": room_temperature}})
    print("Room temperature updated.")

def update_noise_level(date, noise_level):
    collection.update_one({"date": date}, {"$set": {"environment.noise_level": noise_level}})
    print("Noise level updated.")

def update_light_exposure(date, light_exposure):
    collection.update_one({"date": date}, {"$set": {"environment.light_exposure": light_exposure}})
    print("Light exposure updated.")

def update_sleep_position(date, sleep_position):
    collection.update_one({"date": date}, {"$set": {"environment.sleep_position": sleep_position}})
    print("Sleep position updated.")

def update_bedding_comfort(date, bedding_comfort):
    collection.update_one({"date": date}, {"$set": {"environment.bedding_comfort": bedding_comfort}})
    print("Bedding comfort updated.")

def update_pillow_type(date, pillow_type):
    collection.update_one({"date": date}, {"$set": {"environment.pillow_type": pillow_type}})
    print("Pillow type updated.")

def update_mattress_type(date, mattress_type):
    collection.update_one({"date": date}, {"$set": {"environment.mattress_type": mattress_type}})
    print("Mattress type updated.")

def update_sleeping_clothing(date, sleeping_clothing):
    collection.update_one({"date": date}, {"$set": {"environment.sleeping_clothing": sleeping_clothing}})
    print("Sleeping clothing updated.")

def update_sleep_aid_used(date, sleep_aid_used):
    collection.update_one({"date": date}, {"$set": {"environment.sleep_aid_used": sleep_aid_used}})
    print("Sleep aid used updated.")

def update_sleep_temperature_preference(date, sleep_temperature_preference):
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
