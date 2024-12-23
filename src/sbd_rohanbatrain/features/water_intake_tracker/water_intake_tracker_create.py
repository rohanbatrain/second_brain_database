from datetime import datetime
from sbd_rohanbatrain.database.db import water_intake_collection, goals_collection
from sbd_rohanbatrain.utilities.date_time import get_time_details
from sbd_rohanbatrain.features.goals.goals_create import create_goal

# Function to log water intake and update goal progress
def log_water_intake(amount):
    # Get the current time details
    time_details = get_time_details()

    # Create a log entry for the water intake
    log_entry = {
        "amount": amount,  # Amount of water intake
        "timestamp": datetime.now(),  # Current timestamp
        "day_of_week": time_details["Day"],
        "week_of_year": time_details["Week"],
        "month_of_year": time_details["Month"],
        "quarter_of_year": time_details["Quarter"],
        "year": time_details["Year"]
    }

    print("Log entry created:", log_entry)  # Debugging: check the log entry

    # Retrieve all hydration goals (for all frequencies)
    goals_cursor = goals_collection.find({"goal_type": "hydration"})

    # Convert the cursor to a list of documents (iterate through it)
    goals = list(goals_cursor)  # This turns the cursor into a list

    print("Found goals:", goals)  # Debugging: check the goals returned

    for goal in goals:
        goal_value = goal["goal_value"]
        description = goal["description"]
        
        # Logic for handling time-based resets and progress updates
        goal_updated = False  # Flag to track if the goal was updated

        # Daily goal logic
        if goal["frequency"] == "daily":
            if time_details["Day"] != goal.get("day_of_week", time_details["Day"]):  # New day starts
                goal["progress"] = 0  # Reset progress if a new day starts
                goals_collection.update_one({"_id": goal["_id"]}, {"$set": {"progress": 0}})
                print(f"Progress reset for daily goal {goal['_id']}")  # Debugging: check progress reset
            goal["progress"] += amount  # Increment progress for daily goal
            goal_updated = True

        # Weekly goal logic
        elif goal["frequency"] == "weekly":
            if time_details["Week"] != goal.get("week_of_year", time_details["Week"]):  # New week starts
                goal["progress"] = 0  # Reset progress if a new week starts
                goals_collection.update_one({"_id": goal["_id"]}, {"$set": {"progress": 0}})
                print(f"Progress reset for weekly goal {goal['_id']}")  # Debugging: check progress reset
            goal["progress"] += amount  # Increment progress for weekly goal
            goal_updated = True

        # Monthly goal logic
        elif goal["frequency"] == "monthly":
            if time_details["Month"] != goal.get("month_of_year", time_details["Month"]):  # New month starts
                goal["progress"] = 0  # Reset progress if a new month starts
                goals_collection.update_one({"_id": goal["_id"]}, {"$set": {"progress": 0}})
                print(f"Progress reset for monthly goal {goal['_id']}")  # Debugging: check progress reset
            goal["progress"] += amount  # Increment progress for monthly goal
            goal_updated = True

        # Quarterly goal logic
        elif goal["frequency"] == "quarterly":
            if time_details["Quarter"] != goal.get("quarter_of_year", time_details["Quarter"]):  # New quarter starts
                goal["progress"] = 0  # Reset progress if a new quarter starts
                goals_collection.update_one({"_id": goal["_id"]}, {"$set": {"progress": 0}})
                print(f"Progress reset for quarterly goal {goal['_id']}")  # Debugging: check progress reset
            goal["progress"] += amount  # Increment progress for quarterly goal
            goal_updated = True

        # Yearly goal logic
        elif goal["frequency"] == "yearly":
            if time_details["Year"] != goal.get("year", time_details["Year"]):  # New year starts
                goal["progress"] = 0  # Reset progress if a new year starts
                goals_collection.update_one({"_id": goal["_id"]}, {"$set": {"progress": 0}})
                print(f"Progress reset for yearly goal {goal['_id']}")  # Debugging: check progress reset
            goal["progress"] += amount  # Increment progress for yearly goal
            goal_updated = True

        # If any goal was updated, update the goal's progress in the database
        if goal_updated:
            result = goals_collection.update_one({"_id": goal["_id"]}, {"$set": {"progress": goal["progress"]}})
            print("Goal updated:", result.modified_count)  # Debugging: check if goal update succeeded

    # After processing all goals, log the water intake entry
    water_intake_result = water_intake_collection.insert_one(log_entry)
    print("Water intake logged:", water_intake_result.inserted_id)  # Debugging: check if log entry inserted

    return "Water intake logged and goal progress updated successfully"


log_water_intake(250)



# # Example function calls to test it
# # Test Water Intake Logging with automatic goal tracking
# print(log_water_intake(amount=500))  # Log water intake without specifying goal frequency
# print(log_water_intake(amount=1000))  # Log water intake without specifying goal frequency


# # 1. Test Daily Goal
# def test_daily_goal():
#     # Create a daily hydration goal
#     goal_id = create_goal(
#         goal_type="hydration",
#         goal_value=2000,  # Set a goal of 2000 ml per day
#         description="Drink 2000 ml of water per day",
#         unit="ml",
#         frequency="daily"
#     )
#     print(f"Daily goal created with ID: {goal_id}")

# # 2. Test Weekly Goal
# def test_weekly_goal():
#     # Create a weekly hydration goal
#     goal_id = create_goal(
#         goal_type="hydration",
#         goal_value=14000,  # Set a goal of 14000 ml per week
#         description="Drink 14000 ml of water per week",
#         unit="ml",
#         frequency="weekly"
#     )
#     print(f"Weekly goal created with ID: {goal_id}")

# # 3. Test Monthly Goal
# def test_monthly_goal():
#     # Create a monthly hydration goal
#     goal_id = create_goal(
#         goal_type="hydration",
#         goal_value=60000,  # Set a goal of 60000 ml per month
#         description="Drink 60000 ml of water per month",
#         unit="ml",
#         frequency="monthly"
#     )
#     print(f"Monthly goal created with ID: {goal_id}")

# # 4. Test Quarterly Goal
# def test_quarterly_goal():
#     # Create a quarterly hydration goal
#     goal_id = create_goal(
#         goal_type="hydration",
#         goal_value=180000,  # Set a goal of 180000 ml per quarter
#         description="Drink 180000 ml of water per quarter",
#         unit="ml",
#         frequency="quarterly"
#     )
#     print(f"Quarterly goal created with ID: {goal_id}")

# # 5. Test Yearly Goal
# def test_yearly_goal():
#     # Create a yearly hydration goal
#     goal_id = create_goal(
#         goal_type="hydration",
#         goal_value=730000,  # Set a goal of 730000 ml per year
#         description="Drink 730000 ml of water per year",
#         unit="ml",
#         frequency="yearly"
#     )
#     print(f"Yearly goal created with ID: {goal_id}")

# # Call the test functions
# test_daily_goal()
# test_weekly_goal()
# test_monthly_goal()
# test_quarterly_goal()
# test_yearly_goal()