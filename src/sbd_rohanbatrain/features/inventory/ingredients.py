

def add_ingredient(name, category, quantity_available, unit, nutritional_info=None):
    """Add a new ingredient to the Inventory collection."""
    ingredient = {
        "name": name,
        "category": category,
        "quantity_available": quantity_available,
        "unit": unit,
        "nutritional_info": nutritional_info,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    result = inventory_collection.insert_one(ingredient)
    return result.inserted_id

def get_ingredient(ingredient_id):
    """Retrieve an ingredient by its ID."""
    ingredient = inventory_collection.find_one({"_id": ingredient_id})
    return ingredient

def update_ingredient(ingredient_id, update_data):
    """Update an ingredient by its ID."""
    update_data["updated_at"] = datetime.now()
    result = inventory_collection.update_one({"_id": ingredient_id}, {"$set": update_data})
    return result.modified_count

def delete_ingredient(ingredient_id):
    """Delete an ingredient by its ID."""
    result = inventory_collection.delete_one({"_id": ingredient_id})
    return result.deleted_count

# def decrement_ingredient_quantity(ingredient_id, quantity_used):
#     """Decrement the quantity of an ingredient when used in a recipe."""
#     ingredient = inventory_collection.find_one({"_id": ingredient_id})
#     if not ingredient:
#         raise ValueError("Ingredient not found")
#     if ingredient["quantity_available"] < quantity_used:
#         raise ValueError("Insufficient quantity available")
#     updated_quantity = ingredient["quantity_available"] - quantity_used
#     inventory_collection.update_one({"_id": ingredient_id}, {"$set": {"quantity_available": updated_quantity}})
