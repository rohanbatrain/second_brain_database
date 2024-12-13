from datetime import datetime
from sbd_rohanbatrain.database.db import sleep_collection

collection = sleep_collection

def update_bedtime(id, bedtime=None):
    check_entry()  # Ensure the entry exists or create it (using the same check_entry logic)
    collection.update_one({"_id": id}, {"$set": {"bedtime": bedtime}})
    print("Bedtime updated.")


def update_wake_up_time(id, wake_up_time=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"wake_up_time": wake_up_time}})
    print("Wake-up time updated.")


def update_total_sleep_time(id, total_sleep_time=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"total_sleep_time": f"{total_sleep_time:.2f} hours"}})
    print("Total sleep time updated.")


def update_sleep_cycles(id, sleep_cycles=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"sleep_cycles": sleep_cycles}})
    print("Sleep cycles updated.")


# Quality Field Updates
def update_sleep_rating(id, sleep_rating=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"sleep_rating": sleep_rating}})
    print("Sleep rating updated.")


def update_dreams(id, dreams=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"dreams": dreams}})
    print("Dreams updated.")





def update_general_quality(id, general_quality=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"general_quality": general_quality}})
    print("General sleep quality updated.")


# Environment Field Updates
def update_room_temperature(id, room_temperature=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"room_temperature": room_temperature}})
    print("Room temperature updated.")


def update_noise_level(id, noise_level=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"noise_level": noise_level}})
    print("Noise level updated.")


def update_light_exposure(id, light_exposure=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"light_exposure": light_exposure}})
    print("Light exposure updated.")


def update_sleep_position(id, sleep_position=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"sleep_position": sleep_position}})
    print("Sleep position updated.")


def update_bedding_comfort(id, bedding_comfort=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"bedding_comfort": bedding_comfort}})
    print("Bedding comfort updated.")


def update_pillow_type(id, pillow_type=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"pillow_type": pillow_type}})
    print("Pillow type updated.")


def update_mattress_type(id, mattress_type=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"mattress_type": mattress_type}})
    print("Mattress type updated.")


def update_sleeping_clothing(id, sleeping_clothing=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"sleeping_clothing": sleeping_clothing}})
    print("Sleeping clothing updated.")


def update_sleep_aid_used(id, sleep_aid_used=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"sleep_aid_used": sleep_aid_used}})
    print("Sleep aid used updated.")


def update_sleep_temperature_preference(id, sleep_temperature_preference=None):
    check_entry()
    collection.update_one({"_id": id}, {"$set": {"sleep_temperature_preference": sleep_temperature_preference}})
    print("Sleep temperature preference updated.")

def add_awakening(id, time=None, disruption_cause=None):
    check_entry()
    awakening = {"time": time, "disruption_cause": disruption_cause}
    collection.update_one({"_id": id}, {"$push": {"awakenings": awakening}})
    print("Awakening added.")