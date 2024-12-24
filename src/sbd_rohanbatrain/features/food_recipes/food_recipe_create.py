from datetime import datetime
from pymongo import MongoClient
from sbd_rohanbatrain.database.db import recipe_collection,  inventory_collection


def add_recipe(name, ingredients, instructions, tags, prep_time, cook_time):
    """Add a new recipe to the Recipes collection."""
    recipe = {
        "name": name,
        "ingredients": ingredients,
        "instructions": instructions,
        "tags": tags,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "total_time": prep_time + cook_time,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    result = recipes_collection.insert_one(recipe)
    return result.inserted_id

def get_recipe(recipe_id):
    """Retrieve a recipe by its ID."""
    recipe = recipes_collection.find_one({"_id": recipe_id})
    return recipe

def update_recipe(recipe_id, update_data):
    """Update a recipe by its ID."""
    update_data["updated_at"] = datetime.now()
    result = recipes_collection.update_one({"_id": recipe_id}, {"$set": update_data})
    return result.modified_count

def delete_recipe(recipe_id):
    """Delete a recipe by its ID."""
    result = recipes_collection.delete_one({"_id": recipe_id})
    return result.deleted_count


