from datetime import datetime
from sbd_rohanbatrain.database.db import sleep_collection
from sbd_rohanbatrain.features.sleep.sleep import check_entry

collection = sleep_collection


# Duration Field Updates
def update_bedtime(date=None, bedtime=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)  # Ensure the entry exists or create it
    collection.update_one({"date": date}, {"$set": {"bedtime": bedtime}})
    print("Bedtime updated.")
    

def update_wake_up_time(date=None, wake_up_time=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"wake_up_time": wake_up_time}})
    print("Wake-up time updated.")


def update_total_sleep_time(date=None, total_sleep_time=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"total_sleep_time": f"{total_sleep_time:.2f} hours"}})
    print("Total sleep time updated.")


def update_sleep_cycles(date=None, sleep_cycles=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"sleep_cycles": sleep_cycles}})
    print("Sleep cycles updated.")


# Quality Field Updates
def update_sleep_rating(date=None, sleep_rating=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"sleep_rating": sleep_rating}})
    print("Sleep rating updated.")


def update_dreams(date=None, dreams=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"dreams": dreams}})
    print("Dreams updated.")



def update_general_quality(date=None, general_quality=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"general_quality": general_quality}})
    print("General sleep quality updated.")


# Environment Field Updates
def update_room_temperature(date=None, room_temperature=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"room_temperature": room_temperature}})
    print("Room temperature updated.")


def update_noise_level(date=None, noise_level=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"noise_level": noise_level}})
    print("Noise level updated.")


def update_light_exposure(date=None, light_exposure=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"light_exposure": light_exposure}})
    print("Light exposure updated.")


def update_sleep_position(date=None, sleep_position=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"sleep_position": sleep_position}})
    print("Sleep position updated.")


def update_bedding_comfort(date=None, bedding_comfort=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"bedding_comfort": bedding_comfort}})
    print("Bedding comfort updated.")


def update_pillow_type(date=None, pillow_type=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"pillow_type": pillow_type}})
    print("Pillow type updated.")


def update_mattress_type(date=None, mattress_type=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"mattress_type": mattress_type}})
    print("Mattress type updated.")


def update_sleeping_clothing(date=None, sleeping_clothing=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"sleeping_clothing": sleeping_clothing}})
    print("Sleeping clothing updated.")


def update_sleep_aid_used(date=None, sleep_aid_used=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"sleep_aid_used": sleep_aid_used}})
    print("Sleep aid used updated.")


def update_sleep_temperature_preference(date=None, sleep_temperature_preference=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    collection.update_one({"date": date}, {"$set": {"sleep_temperature_preference": sleep_temperature_preference}})
    print("Sleep temperature preference updated.")

def add_awakening(date=None, time=None, disruption_cause=None):
    date = date or datetime.now().strftime("%Y-%m-%d")  # Use today's date if None
    check_entry(date)
    awakening = {"time": time, "disruption_cause": disruption_cause}
    collection.update_one({"date": date}, {"$push": {"awakenings": awakening}})
    print("Awakening added.")