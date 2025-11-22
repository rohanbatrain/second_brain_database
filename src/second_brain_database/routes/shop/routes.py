from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from second_brain_database.database import db_manager
from second_brain_database.docs.models import (
    StandardErrorResponse,
    StandardSuccessResponse,
    ValidationErrorResponse,
    create_error_responses,
    create_standard_responses,
)
from second_brain_database.managers.family_manager import family_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.utils.logging_utils import (
    ip_address_context,
    log_database_operation,
    log_error_with_context,
    log_performance,
    request_id_context,
    user_id_context,
)

logger = get_logger(prefix="[SHOP]")

router = APIRouter()

SHOP_COLLECTION = "shop"


# Payment method models
class PaymentMethod(BaseModel):
    """Payment method selection for shop purchases."""

    type: str = Field(..., description="Payment type: 'personal' or 'family'")
    family_id: Optional[str] = Field(None, description="Family ID if using family tokens")


class PurchaseRequest(BaseModel):
    """Base purchase request with payment method."""

    payment_method: PaymentMethod = Field(..., description="Payment method selection")


class ThemePurchaseRequest(PurchaseRequest):
    """Theme purchase request with payment method."""

    theme_id: str = Field(..., description="Theme ID to purchase")


class AvatarPurchaseRequest(PurchaseRequest):
    """Avatar purchase request with payment method."""

    avatar_id: str = Field(..., description="Avatar ID to purchase")


class BannerPurchaseRequest(PurchaseRequest):
    """Banner purchase request with payment method."""

    banner_id: str = Field(..., description="Banner ID to purchase")


class BundlePurchaseRequest(PurchaseRequest):
    """Bundle purchase request with payment method."""

    bundle_id: str = Field(..., description="Bundle ID to purchase")


class CartCheckoutRequest(BaseModel):
    """Cart checkout request with payment method."""

    payment_method: PaymentMethod = Field(..., description="Payment method selection")


class ShopItemResponse(BaseModel):
    item_id: str
    name: str
    description: Optional[str]
    price: int
    item_type: str  # "theme", "avatar", "banner", "bundle"
    category: Optional[str]
    featured: bool = False
    new_arrival: bool = False
    image_url: Optional[str]
    bundle_contents: Optional[dict] = None
    available: bool = True


class ShopCategoryResponse(BaseModel):
    category_id: str
    name: str
    description: Optional[str]
    item_type: str


class CategoryCreateRequest(BaseModel):
    """Request model for creating a new category."""
    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, max_length=500, description="Category description")
    icon: Optional[str] = Field(None, description="Category icon/emoji")
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$", description="Category color (hex)")
    item_type: str = Field(..., description="Type of items in this category")


class CategoryUpdateRequest(BaseModel):
    """Request model for updating a category."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, max_length=500, description="Category description")
    icon: Optional[str] = Field(None, description="Category icon/emoji")
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$", description="Category color (hex)")


class CategoryDetailResponse(BaseModel):
    """Detailed category response with stats."""
    category_id: str
    name: str
    description: Optional[str]
    icon: Optional[str]
    color: Optional[str]
    item_type: str
    item_count: int = 0
    created_at: str
    updated_at: Optional[str]


class CartItemRequest(BaseModel):
    item_id: str
    item_type: str
    quantity: int = 1


class CartItemResponse(BaseModel):
    item_id: str
    item_type: str
    name: str
    price: int
    quantity: int
    subtotal: int


class CartResponse(BaseModel):
    items: List[CartItemResponse]
    total_items: int
    total_price: int


class CheckoutResponse(BaseModel):
    transaction_id: str
    items_purchased: List[str]
    total_amount: int
    payment_method: str
    status: str


class OwnedItemResponse(BaseModel):
    item_id: str
    item_type: str
    name: str
    acquired_at: datetime
    source: str  # "purchase", "gift", "bundle"
    permanent: bool
    rental_expires: Optional[datetime]


class InventoryResponse(BaseModel):
    themes: List[OwnedItemResponse]
    avatars: List[OwnedItemResponse]
    banners: List[OwnedItemResponse]
    bundles: List[str]
    total_items: int


class BalanceResponse(BaseModel):
    sbd_tokens: int
    username: str


# Helper functions for family token integration
async def get_user_payment_options(user_id: str, username: str) -> Dict[str, Any]:
    """
    Get available payment options for a user including personal and family tokens.

    Args:
        user_id: User ID
        username: Username

    Returns:
        Dict containing personal and family token balances
    """
    users_collection = db_manager.get_collection("users")

    # Get personal token balance
    user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
    personal_balance = user.get("sbd_tokens", 0) if user else 0

    # Get family token balances
    family_balances = []
    try:
        user_families = await family_manager.get_user_families(user_id)
        for family in user_families:
            family_id = family["family_id"]
            try:
                # Get family SBD account details
                sbd_account = await family_manager.get_family_sbd_account(family_id, user_id)

                # Check if user has spending permissions
                user_permissions = sbd_account["spending_permissions"].get(user_id, {})
                can_spend = user_permissions.get("can_spend", False) and not sbd_account["is_frozen"]

                if can_spend:
                    family_balances.append(
                        {
                            "family_id": family_id,
                            "family_name": family["name"],
                            "balance": sbd_account["balance"],
                            "spending_limit": user_permissions.get("spending_limit", 0),
                            "is_frozen": sbd_account["is_frozen"],
                        }
                    )
            except Exception as e:
                logger.warning("Failed to get family SBD account for family %s: %s", family_id, e)
                continue
    except Exception as e:
        logger.warning("Failed to get user families for payment options: %s", e)

    return {"personal": {"balance": personal_balance, "available": True}, "family": family_balances}


async def validate_payment_method(
    payment_method: PaymentMethod, user_id: str, username: str, amount: int
) -> Dict[str, Any]:
    """
    Validate payment method and check if user can make the purchase.

    Args:
        payment_method: Payment method selection
        user_id: User ID
        username: Username
        amount: Purchase amount

    Returns:
        Dict containing validation result and payment details

    Raises:
        HTTPException: If payment method is invalid or insufficient funds
    """
    if payment_method.type == "personal":
        # Validate personal token balance
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        balance = user.get("sbd_tokens", 0)
        if balance < amount:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INSUFFICIENT_PERSONAL_TOKENS",
                    "message": f"Insufficient personal tokens. Required: {amount}, Available: {balance}",
                },
            )

        return {"valid": True, "payment_type": "personal", "account_username": username, "balance": balance}

    elif payment_method.type == "family":
        if not payment_method.family_id:
            raise HTTPException(
                status_code=400,
                detail={"error": "MISSING_FAMILY_ID", "message": "Family ID is required for family token payments"},
            )

        try:
            # Get family data and validate spending permission
            family_data = await family_manager.get_family_by_id(payment_method.family_id)
            family_username = family_data["sbd_account"]["account_username"]

            # Validate family spending permission
            can_spend = await family_manager.validate_family_spending(family_username, user_id, amount)

            if not can_spend:
                # Get detailed error information
                permissions = family_data["sbd_account"]["spending_permissions"].get(user_id, {})

                if family_data["sbd_account"]["is_frozen"]:
                    error_detail = "Family account is currently frozen and cannot be used for spending"
                elif not permissions.get("can_spend", False):
                    error_detail = "You don't have permission to spend from this family account"
                elif permissions.get("spending_limit", 0) != -1 and amount > permissions.get("spending_limit", 0):
                    error_detail = (
                        f"Amount exceeds your spending limit of {permissions.get('spending_limit', 0)} tokens"
                    )
                else:
                    error_detail = "Family spending validation failed"

                raise HTTPException(
                    status_code=403, detail={"error": "FAMILY_SPENDING_DENIED", "message": error_detail}
                )

            # Get family account balance
            balance = await family_manager.get_family_sbd_balance(family_username)

            return {
                "valid": True,
                "payment_type": "family",
                "account_username": family_username,
                "family_id": payment_method.family_id,
                "family_name": family_data["name"],
                "balance": balance,
                "user_permissions": permissions,
            }

        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error("Failed to validate family payment method: %s", e)
            raise HTTPException(
                status_code=500,
                detail={"error": "FAMILY_VALIDATION_FAILED", "message": "Failed to validate family payment method"},
            )

    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_PAYMENT_TYPE",
                "message": f"Invalid payment type: {payment_method.type}. Must be 'personal' or 'family'",
            },
        )


async def process_payment(
    payment_details: Dict[str, Any],
    amount: int,
    item_details: Dict[str, Any],
    current_user: Dict[str, Any],
    transaction_id: str,
) -> Dict[str, Any]:
    """
    Process payment using the validated payment method.

    Args:
        payment_details: Validated payment details
        amount: Purchase amount
        item_details: Item being purchased
        current_user: Current user information
        transaction_id: Transaction ID

    Returns:
        Dict containing transaction details
    """
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])
    now_iso = datetime.now(timezone.utc).isoformat()

    # Prepare transaction notes
    item_type = item_details.get("type", "item")
    item_id = item_details.get(f"{item_type}_id", "unknown")
    base_note = f"Bought {item_type} {item_id} from shop"

    if payment_details["payment_type"] == "personal":
        # Process personal token payment
        send_txn = {
            "type": "send",
            "to": "emotion_tracker_shop",
            "amount": amount,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": base_note,
        }

        receive_txn = {
            "type": "receive",
            "from": username,
            "amount": amount,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"User bought {item_type} {item_id}",
        }

        # Deduct from personal account
        result = await users_collection.update_one(
            {"username": username, "sbd_tokens": {"$gte": amount}},
            {
                "$inc": {"sbd_tokens": -amount},
                "$push": {"sbd_tokens_transactions": send_txn},
            },
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Insufficient SBD tokens or race condition")

        # Add to shop account
        await users_collection.update_one(
            {"username": "emotion_tracker_shop"},
            {
                "$setOnInsert": {"email": "emotion_tracker_shop@rohanbatra.in"},
                "$push": {"sbd_tokens_transactions": receive_txn},
            },
            upsert=True,
        )

        return {
            "payment_type": "personal",
            "from_account": username,
            "amount": amount,
            "transaction_id": transaction_id,
        }

    elif payment_details["payment_type"] == "family":
        # Process family token payment
        family_username = payment_details["account_username"]
        family_id = payment_details["family_id"]
        family_name = payment_details["family_name"]

        # Enhanced transaction notes with family member attribution
        family_note = f"Spent by family member @{username} from {family_name}"
        send_txn = {
            "type": "send",
            "to": "emotion_tracker_shop",
            "amount": amount,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"{base_note} ({family_note})",
            "family_member_id": user_id,
            "family_member_username": username,
            "shop_item_type": item_type,
            "shop_item_id": item_id,
        }

        receive_txn = {
            "type": "receive",
            "from": family_username,
            "amount": amount,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"Family member @{username} bought {item_type} {item_id}",
            "family_member_id": user_id,
            "family_member_username": username,
            "shop_item_type": item_type,
            "shop_item_id": item_id,
        }

        # Deduct from family account
        result = await users_collection.update_one(
            {"username": family_username, "sbd_tokens": {"$gte": amount}},
            {
                "$inc": {"sbd_tokens": -amount},
                "$push": {"sbd_tokens_transactions": send_txn},
            },
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Insufficient family tokens or race condition")

        # Add to shop account
        await users_collection.update_one(
            {"username": "emotion_tracker_shop"},
            {
                "$setOnInsert": {"email": "emotion_tracker_shop@rohanbatra.in"},
                "$push": {"sbd_tokens_transactions": receive_txn},
            },
            upsert=True,
        )

        # Send family notification about the purchase
        try:
            await family_manager.send_family_notification(
                family_id,
                "sbd_spend",
                {
                    "transaction_id": transaction_id,
                    "amount": amount,
                    "spender_username": username,
                    "spender_id": user_id,
                    "shop_item_type": item_type,
                    "shop_item_id": item_id,
                    "shop_item_name": item_details.get("name", "Unknown Item"),
                    "to_account": "emotion_tracker_shop",
                },
            )
        except Exception as e:
            logger.warning("Failed to send family notification for shop purchase: %s", e)

        return {
            "payment_type": "family",
            "from_account": family_username,
            "family_id": family_id,
            "family_name": family_name,
            "amount": amount,
            "transaction_id": transaction_id,
            "family_member": username,
        }

    else:
        raise HTTPException(status_code=400, detail="Invalid payment type")


# Server-side registry for shop items to ensure prices are not client-controlled.
# In a real-world application, this would be a separate collection in the database.
async def get_item_details(item_id: str, item_type: str):
    # This is a mock implementation. Replace with a real database lookup.
    # NOTE: This function supports both legacy hardcoded items and dynamic parsing.
    # It returns both 'type' (legacy) and 'item_type' (new REST API) keys for compatibility.
    
    if item_type == "theme":
        if item_id.startswith("emotion_tracker-"):
            return {
                "theme_id": item_id, 
                "name": "Emotion Tracker Theme", 
                "price": 250, 
                "item_type": "theme",
                "type": "theme"  # Legacy compatibility
            }
    elif item_type == "avatar":
        # Premium animated avatars
        if item_id == "emotion_tracker-animated-avatar-playful_eye":
            return {
                "avatar_id": item_id, 
                "name": "Playful Eye", 
                "price": 2500, 
                "item_type": "avatar",
                "type": "avatar"  # Legacy compatibility
            }
        if item_id == "emotion_tracker-animated-avatar-floating_brain":
            return {
                "avatar_id": item_id, 
                "name": "Floating Brain", 
                "price": 5000, 
                "item_type": "avatar",
                "type": "avatar"  # Legacy compatibility
            }

        # In a real app, you'd look up the avatar's price
        name = "User Avatar"  # Default name
        try:
            # Attempt to create a more descriptive name from the ID
            # e.g., "emotion_tracker-static-avatar-cat-1" -> "Cat 1"
            name_part = item_id.split("avatar-")[1]
            name = name_part.replace("-", " ").title()
        except IndexError:
            # If the ID format is not as expected, fall back to the default name
            pass
        return {
            "avatar_id": item_id, 
            "name": name, 
            "price": 100, 
            "item_type": "avatar",
            "type": "avatar"  # Legacy compatibility
        }
    elif item_type == "bundle":
        bundles = {
            "emotion_tracker-avatars-cat-bundle": {"name": "Cat Lovers Pack", "price": 2000},
            "emotion_tracker-avatars-dog-bundle": {"name": "Dog Lovers Pack", "price": 2000},
            "emotion_tracker-avatars-panda-bundle": {"name": "Panda Lovers Pack", "price": 1500},
            "emotion_tracker-avatars-people-bundle": {"name": "People Pack", "price": 2000},
            "emotion_tracker-themes-dark": {"name": "Dark Theme Pack", "price": 2500},
            "emotion_tracker-themes-light": {"name": "Light Theme Pack", "price": 2500},
        }
        if item_id in bundles:
            bundle_info = bundles[item_id]
            return {
                "bundle_id": item_id, 
                "name": bundle_info["name"], 
                "price": bundle_info["price"], 
                "item_type": "bundle",
                "type": "bundle"  # Legacy compatibility
            }
    elif item_type == "banner":
        if item_id == "emotion_tracker-static-banner-earth-1":
            return {
                "banner_id": item_id, 
                "name": "Earth Banner", 
                "price": 100, 
                "item_type": "banner",
                "type": "banner"  # Legacy compatibility
            }
        # Fallback for other banners
        return {
            "banner_id": item_id, 
            "name": "User Banner", 
            "price": 100, 
            "item_type": "banner",
            "type": "banner"  # Legacy compatibility
        }
    return None


# Utility to get or create a user's shop doc
async def get_or_create_shop_doc(username):
    shop_collection = db_manager.get_tenant_collection(SHOP_COLLECTION)
    doc = await shop_collection.find_one({"username": username})
    if not doc:
        doc = {"username": username, "carts": {}}
        await shop_collection.insert_one(doc)
    return doc


@router.get("/shop/payment-options", tags=["Shop"], summary="Get available payment options")
async def get_payment_options(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Get available payment options for the current user including personal and family token balances.

    Returns comprehensive information about all available payment methods,
    including personal token balance and family accounts the user can spend from.

    **Returns:**
    - Personal token balance
    - List of family accounts with spending permissions
    - Spending limits and restrictions for each account
    """
    user_id = str(current_user["_id"])
    username = current_user["username"]

    try:
        payment_options = await get_user_payment_options(user_id, username)

        logger.debug("Retrieved payment options for user %s", username)

        return {
            "status": "success",
            "data": {"user_id": user_id, "username": username, "payment_options": payment_options},
        }

    except Exception as e:
        logger.error("Failed to get payment options for user %s: %s", username, e)
        return JSONResponse({"status": "error", "detail": "Failed to retrieve payment options"}, status_code=500)


BUNDLE_CONTENTS = {
    "emotion_tracker-avatars-cat-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-cat-1",
            "emotion_tracker-static-avatar-cat-2",
            "emotion_tracker-static-avatar-cat-3",
            "emotion_tracker-static-avatar-cat-4",
            "emotion_tracker-static-avatar-cat-5",
            "emotion_tracker-static-avatar-cat-6",
            "emotion_tracker-static-avatar-cat-7",
            "emotion_tracker-static-avatar-cat-8",
            "emotion_tracker-static-avatar-cat-9",
            "emotion_tracker-static-avatar-cat-10",
            "emotion_tracker-static-avatar-cat-11",
            "emotion_tracker-static-avatar-cat-12",
            "emotion_tracker-static-avatar-cat-13",
            "emotion_tracker-static-avatar-cat-14",
            "emotion_tracker-static-avatar-cat-15",
            "emotion_tracker-static-avatar-cat-16",
            "emotion_tracker-static-avatar-cat-17",
            "emotion_tracker-static-avatar-cat-18",
            "emotion_tracker-static-avatar-cat-19",
            "emotion_tracker-static-avatar-cat-20",
        ]
    },
    "emotion_tracker-avatars-dog-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-dog-1",
            "emotion_tracker-static-avatar-dog-2",
            "emotion_tracker-static-avatar-dog-3",
            "emotion_tracker-static-avatar-dog-4",
            "emotion_tracker-static-avatar-dog-5",
            "emotion_tracker-static-avatar-dog-6",
            "emotion_tracker-static-avatar-dog-7",
            "emotion_tracker-static-avatar-dog-8",
            "emotion_tracker-static-avatar-dog-9",
            "emotion_tracker-static-avatar-dog-10",
            "emotion_tracker-static-avatar-dog-11",
            "emotion_tracker-static-avatar-dog-12",
            "emotion_tracker-static-avatar-dog-13",
            "emotion_tracker-static-avatar-dog-14",
            "emotion_tracker-static-avatar-dog-15",
            "emotion_tracker-static-avatar-dog-16",
            "emotion_tracker-static-avatar-dog-17",
        ]
    },
    "emotion_tracker-avatars-panda-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-panda-1",
            "emotion_tracker-static-avatar-panda-2",
            "emotion_tracker-static-avatar-panda-3",
            "emotion_tracker-static-avatar-panda-4",
            "emotion_tracker-static-avatar-panda-5",
            "emotion_tracker-static-avatar-panda-6",
            "emotion_tracker-static-avatar-panda-7",
            "emotion_tracker-static-avatar-panda-8",
            "emotion_tracker-static-avatar-panda-9",
            "emotion_tracker-static-avatar-panda-10",
            "emotion_tracker-static-avatar-panda-11",
            "emotion_tracker-static-avatar-panda-12",
        ]
    },
    "emotion_tracker-avatars-people-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-person-1",
            "emotion_tracker-static-avatar-person-2",
            "emotion_tracker-static-avatar-person-3",
            "emotion_tracker-static-avatar-person-4",
            "emotion_tracker-static-avatar-person-5",
            "emotion_tracker-static-avatar-person-6",
            "emotion_tracker-static-avatar-person-7",
            "emotion_tracker-static-avatar-person-8",
            "emotion_tracker-static-avatar-person-9",
            "emotion_tracker-static-avatar-person-10",
            "emotion_tracker-static-avatar-person-11",
            "emotion_tracker-static-avatar-person-12",
            "emotion_tracker-static-avatar-person-13",
            "emotion_tracker-static-avatar-person-14",
            "emotion_tracker-static-avatar-person-15",
            "emotion_tracker-static-avatar-person-16",
        ]
    },
    "emotion_tracker-themes-dark": {
        "themes": [
            "emotion_tracker-serenityGreenDark",
            "emotion_tracker-pacificBlueDark",
            "emotion_tracker-blushRoseDark",
            "emotion_tracker-cloudGrayDark",
            "emotion_tracker-sunsetPeachDark",
            "emotion_tracker-goldenYellowDark",
            "emotion_tracker-forestGreenDark",
            "emotion_tracker-midnightLavender",
            "emotion_tracker-crimsonRedDark",
            "emotion_tracker-deepPurpleDark",
            "emotion_tracker-royalOrangeDark",
        ]
    },
    "emotion_tracker-themes-light": {
        "themes": [
            "emotion_tracker-serenityGreen",
            "emotion_tracker-pacificBlue",
            "emotion_tracker-blushRose",
            "emotion_tracker-cloudGray",
            "emotion_tracker-sunsetPeach",
            "emotion_tracker-goldenYellow",
            "emotion_tracker-forestGreen",
            "emotion_tracker-midnightLavenderLight",
            "emotion_tracker-royalOrange",
            "emotion_tracker-crimsonRed",
            "emotion_tracker-deepPurple",
        ]
    },
}


SHOP_CATEGORIES = {
    "theme": [
        {"id": "light", "name": "Light Themes", "description": "Bright and airy themes"},
        {"id": "dark", "name": "Dark Themes", "description": "Dark mode themes"},
        {"id": "colorful", "name": "Colorful Themes", "description": "Vibrant color schemes"},
    ],
    "avatar": [
        {"id": "animated", "name": "Animated Avatars", "description": "Premium animated avatars"},
        {"id": "cats", "name": "Cat Avatars", "description": "Cute cat-themed avatars"},
        {"id": "dogs", "name": "Dog Avatars", "description": "Friendly dog avatars"},
        {"id": "pandas", "name": "Panda Avatars", "description": "Adorable panda avatars"},
        {"id": "people", "name": "People Avatars", "description": "Human character avatars"},
    ],
    "banner": [
        {"id": "nature", "name": "Nature Banners", "description": "Natural landscape banners"},
        {"id": "abstract", "name": "Abstract Banners", "description": "Artistic abstract designs"},
        {"id": "space", "name": "Space Banners", "description": "Cosmic and space themes"},
    ],
    "bundle": [
        {"id": "avatars", "name": "Avatar Bundles", "description": "Collections of themed avatars"},
        {"id": "themes", "name": "Theme Bundles", "description": "Curated theme collections"},
        {"id": "complete", "name": "Complete Packs", "description": "Full customization packages"},
    ],
}


async def get_all_shop_items() -> List[Dict[str, Any]]:
    """Get all available shop items from the registry."""
    shop_items = []

    # Themes
    shop_items.extend([
        {
            "item_id": "emotion_tracker-serenityGreen",
            "name": "Serenity Green Theme",
            "price": 250,
            "item_type": "theme",
            "category": "light",
            "featured": True,
            "description": "A calming green theme for peaceful productivity",
        },
        {
            "item_id": "emotion_tracker-pacificBlue",
            "name": "Pacific Blue Theme",
            "price": 250,
            "item_type": "theme",
            "category": "light",
            "description": "Ocean-inspired blue theme for clarity and focus",
        },
        {
            "item_id": "emotion_tracker-midnightLavender",
            "name": "Midnight Lavender Theme",
            "price": 250,
            "item_type": "theme",
            "category": "dark",
            "featured": True,
            "description": "Elegant dark theme with lavender accents",
        },
        {
            "item_id": "emotion_tracker-crimsonRedDark",
            "name": "Crimson Red Dark Theme",
            "price": 250,
            "item_type": "theme",
            "category": "dark",
            "description": "Bold dark theme with crimson highlights",
        },
    ])

    # Avatars
    shop_items.extend([
        {
            "item_id": "emotion_tracker-animated-avatar-playful_eye",
            "name": "Playful Eye Avatar",
            "price": 2500,
            "item_type": "avatar",
            "category": "animated",
            "featured": True,
            "new_arrival": True,
            "description": "Animated avatar with playful eye expressions",
        },
        {
            "item_id": "emotion_tracker-animated-avatar-floating_brain",
            "name": "Floating Brain Avatar",
            "price": 5000,
            "item_type": "avatar",
            "category": "animated",
            "featured": True,
            "description": "Premium animated floating brain avatar",
        },
        {
            "item_id": "emotion_tracker-static-avatar-cat-1",
            "name": "Cat Avatar 1",
            "price": 100,
            "item_type": "avatar",
            "category": "cats",
            "description": "Cute static cat avatar",
        },
        {
            "item_id": "emotion_tracker-static-avatar-dog-1",
            "name": "Dog Avatar 1",
            "price": 100,
            "item_type": "avatar",
            "category": "dogs",
            "description": "Friendly static dog avatar",
        },
    ])

    # Banners
    shop_items.extend([
        {
            "item_id": "emotion_tracker-static-banner-earth-1",
            "name": "Earth Banner",
            "price": 100,
            "item_type": "banner",
            "category": "nature",
            "description": "Beautiful Earth landscape banner",
        }
    ])

    # Bundles
    shop_items.extend([
        {
            "item_id": "emotion_tracker-avatars-cat-bundle",
            "name": "Cat Lovers Pack",
            "price": 2000,
            "item_type": "bundle",
            "category": "avatars",
            "featured": True,
            "description": "Complete collection of cat avatars",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-avatars-cat-bundle", {}),
        },
        {
            "item_id": "emotion_tracker-themes-dark",
            "name": "Dark Theme Pack",
            "price": 2500,
            "item_type": "bundle",
            "category": "themes",
            "featured": True,
            "description": "Collection of premium dark themes",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-themes-dark", {}),
        },
    ])

    return shop_items


@router.get("/shop/items", response_model=List[ShopItemResponse])
async def get_shop_items(
    item_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    featured_only: bool = Query(False),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """Get available shop items with optional filtering."""
    all_items = await get_all_shop_items()
    
    # Apply filters
    filtered_items = all_items
    
    if item_type:
        filtered_items = [item for item in filtered_items if item.get("item_type") == item_type]
        
    if category:
        filtered_items = [item for item in filtered_items if item.get("category") == category]
        
    if featured_only:
        filtered_items = [item for item in filtered_items if item.get("featured", False)]
        
    # Pagination
    paginated_items = filtered_items[offset : offset + limit]
    
    return paginated_items


@router.get("/shop/items/{item_id}", response_model=ShopItemResponse)
async def get_shop_item(item_id: str, item_type: str = Query(...)):
    """Get detailed information about a specific shop item."""
    item = await get_item_details(item_id, item_type)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/shop/categories", response_model=List[ShopCategoryResponse])
async def get_shop_categories_endpoint():
    """Get all available shop categories organized by item type."""
    categories = []
    for item_type, cats in SHOP_CATEGORIES.items():
        for cat in cats:
            categories.append({
                "category_id": cat["id"],
                "name": cat["name"],
                "description": cat["description"],
                "item_type": item_type,
                "item_count": 0  # TODO: Calculate item count
            })
    return categories


@router.post("/shop/categories", response_model=CategoryDetailResponse, status_code=201)
async def create_category(
    category: CategoryCreateRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Create a new shop category."""
    # Check if user has admin permissions (you may want to add a specific permission check)
    shop_collection = db_manager.get_tenant_collection("shop_categories")
    
    # Check if category with same name already exists
    existing = await shop_collection.find_one({
        "name": category.name,
        "item_type": category.item_type
    })
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Category '{category.name}' already exists for {category.item_type}"
        )
    
    # Create category document
    category_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    
    category_doc = {
        "category_id": category_id,
        "name": category.name,
        "description": category.description,
        "icon": category.icon,
        "color": category.color,
        "item_type": category.item_type,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user["username"]
    }
    
    await shop_collection.insert_one(category_doc)
    
    return {
        **category_doc,
        "item_count": 0
    }


@router.put("/shop/categories/{category_id}", response_model=CategoryDetailResponse)
async def update_category(
    category_id: str,
    category: CategoryUpdateRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Update an existing shop category."""
    shop_collection = db_manager.get_tenant_collection("shop_categories")
    
    # Find existing category
    existing = await shop_collection.find_one({"category_id": category_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Build update document
    update_data = {}
    if category.name is not None:
        update_data["name"] = category.name
    if category.description is not None:
        update_data["description"] = category.description
    if category.icon is not None:
        update_data["icon"] = category.icon
    if category.color is not None:
        update_data["color"] = category.color
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user["username"]
    
    # Update category
    await shop_collection.update_one(
        {"category_id": category_id},
        {"$set": update_data}
    )
    
    # Get updated category
    updated = await shop_collection.find_one({"category_id": category_id})
    
    # Count items in this category
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    item_count = await shop_items_collection.count_documents({"category": updated["name"]})
    
    return {
        **updated,
        "item_count": item_count
    }


@router.delete("/shop/categories/{category_id}")
async def delete_category(
    category_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Delete a shop category."""
    shop_collection = db_manager.get_tenant_collection("shop_categories")
    
    # Find existing category
    existing = await shop_collection.find_one({"category_id": category_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check if category has items
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    item_count = await shop_items_collection.count_documents({"category": existing["name"]})
    
    if item_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete category with {item_count} items. Please reassign or delete items first."
        )
    
    # Delete category
    await shop_collection.delete_one({"category_id": category_id})
    
    return {"status": "success", "message": f"Category '{existing['name']}' deleted"}


@router.get("/shop/categories/{category_id}", response_model=CategoryDetailResponse)
async def get_category_detail(category_id: str):
    """Get detailed information about a specific category."""
    shop_collection = db_manager.get_tenant_collection("shop_categories")
    
    category = await shop_collection.find_one({"category_id": category_id})
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Count items in this category
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    item_count = await shop_items_collection.count_documents({"category": category["name"]})
    
    return {
        **category,
        "item_count": item_count
    }


@router.get("/shop/categories/{category_id}/items", response_model=List[ShopItemResponse])
async def get_category_items(category_id: str):
    """Get all items in a specific category."""
    shop_collection = db_manager.get_tenant_collection("shop_categories")
    
    category = await shop_collection.find_one({"category_id": category_id})
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Get items in this category
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    items_cursor = shop_items_collection.find({"category": category["name"]})
    items = await items_cursor.to_list(length=None)
    
    return items


# ============================================================================
# ITEM MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/shop/items", response_model=ShopItemResponse, status_code=201)
async def create_shop_item(
    item: dict,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Create a new shop item."""
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    
    item_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    
    item_doc = {
        "item_id": item_id,
        "name": item["name"],
        "description": item.get("description"),
        "price": item["price"],
        "item_type": item["item_type"],
        "category": item.get("category"),
        "featured": item.get("featured", False),
        "new_arrival": item.get("new_arrival", False),
        "image_url": item.get("image_url"),
        "bundle_contents": item.get("bundle_contents"),
        "available": item.get("available", True),
        "stock": item.get("stock", 999),
        "created_at": now,
        "updated_at": now,
        "created_by": current_user["username"]
    }
    
    await shop_items_collection.insert_one(item_doc)
    return item_doc


@router.put("/shop/items/{item_id}", response_model=ShopItemResponse)
async def update_shop_item(
    item_id: str,
    item: dict,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Update an existing shop item."""
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    
    existing = await shop_items_collection.find_one({"item_id": item_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Item not found")
    
    update_data = {}
    for key in ["name", "description", "price", "category", "featured", "new_arrival", "image_url", "bundle_contents", "available", "stock"]:
        if key in item:
            update_data[key] = item[key]
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user["username"]
    
    await shop_items_collection.update_one(
        {"item_id": item_id},
        {"$set": update_data}
    )
    
    updated = await shop_items_collection.find_one({"item_id": item_id})
    return updated


@router.delete("/shop/items/{item_id}")
async def delete_shop_item(
    item_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Delete a shop item."""
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    
    existing = await shop_items_collection.find_one({"item_id": item_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Item not found")
    
    await shop_items_collection.delete_one({"item_id": item_id})
    return {"status": "success", "message": f"Item '{existing['name']}' deleted"}


@router.post("/shop/items/bulk-update")
async def bulk_update_items(
    updates: dict,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Bulk update shop items."""
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    
    item_ids = updates.get("item_ids", [])
    action = updates.get("action")
    
    if not item_ids or not action:
        raise HTTPException(status_code=400, detail="item_ids and action are required")
    
    updated_count = 0
    
    if action == "activate":
        result = await shop_items_collection.update_many(
            {"item_id": {"$in": item_ids}},
            {"$set": {"available": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        updated_count = result.modified_count
    elif action == "deactivate":
        result = await shop_items_collection.update_many(
            {"item_id": {"$in": item_ids}},
            {"$set": {"available": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        updated_count = result.modified_count
    elif action == "update_stock":
        stock_value = updates.get("stock", 0)
        result = await shop_items_collection.update_many(
            {"item_id": {"$in": item_ids}},
            {"$set": {"stock": stock_value, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        updated_count = result.modified_count
    elif action == "delete":
        result = await shop_items_collection.delete_many({"item_id": {"$in": item_ids}})
        updated_count = result.deleted_count
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    
    return {"status": "success", "action": action, "updated_count": updated_count}


@router.post("/shop/items/{item_id}/image")
async def upload_item_image(
    item_id: str,
    image_url: str = Body(..., embed=True),
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Update item image URL."""
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    
    existing = await shop_items_collection.find_one({"item_id": item_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Item not found")
    
    await shop_items_collection.update_one(
        {"item_id": item_id},
        {"$set": {
            "image_url": image_url,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"status": "success", "image_url": image_url}


# ============================================================================
# SALES ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/shop/analytics/sales")
async def get_sales_analytics(
    period: str = Query("month", description="Period: day, week, month, year"),
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Get sales analytics for the specified period."""
    # This would typically query a transactions/purchases collection
    # For now, returning mock data structure
    return {
        "period": period,
        "total_revenue": 125000,
        "total_sales": 342,
        "average_order_value": 365,
        "sales_by_day": [
            {"date": "2024-01-01", "revenue": 5000, "sales": 12},
            {"date": "2024-01-02", "revenue": 7500, "sales": 18},
            # More data points...
        ],
        "revenue_by_category": {
            "themes": 45000,
            "avatars": 35000,
            "banners": 25000,
            "bundles": 20000
        }
    }


@router.get("/shop/analytics/top-items")
async def get_top_selling_items(
    limit: int = Query(10, le=50),
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """Get top selling items."""
    shop_items_collection = db_manager.get_tenant_collection("shop_items")
    
    # Get items sorted by a sold_count field (would need to track this)
    items = await shop_items_collection.find().sort("sold_count", -1).limit(limit).to_list(length=limit)
    
    return {
        "top_items": items,
        "total_items": len(items)
    }


@router.get("/shop/analytics/revenue")
async def get_revenue_breakdown(current_user: dict = Depends(enforce_all_lockdowns)):
    """Get detailed revenue breakdown."""
    return {
        "total_revenue": 125000,
        "by_category": {
            "themes": {"revenue": 45000, "percentage": 36},
            "avatars": {"revenue": 35000, "percentage": 28},
            "banners": {"revenue": 25000, "percentage": 20},
            "bundles": {"revenue": 20000, "percentage": 16}
        },
        "by_month": [
            {"month": "2024-01", "revenue": 35000},
            {"month": "2024-02", "revenue": 42000},
            {"month": "2024-03", "revenue": 48000}
        ],
        "growth_rate": 12.5
    }


@router.get("/shop/analytics/customers")
async def get_customer_analytics(current_user: dict = Depends(enforce_all_lockdowns)):
    """Get customer analytics."""
    users_collection = db_manager.get_collection("users")
    
    # Count users with purchases
    total_customers = await users_collection.count_documents({"owned_items": {"$exists": True, "$ne": []}})
    
    return {
        "total_customers": total_customers,
        "active_customers": total_customers,  # Would need activity tracking
        "average_lifetime_value": 365,
        "repeat_purchase_rate": 45.5,
        "top_customers": []  # Would query top spenders
    }









@router.get("/shop/inventory", response_model=InventoryResponse)
async def get_inventory(current_user: dict = Depends(enforce_all_lockdowns)):
    """Get user's owned items inventory."""
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]})
    
    return {
        "themes": user.get("themes_owned", []),
        "avatars": user.get("avatars_owned", []),
        "banners": user.get("banners_owned", []),
        "bundles": user.get("bundles_owned", []),
        "total_items": len(user.get("themes_owned", [])) + len(user.get("avatars_owned", [])) + len(user.get("banners_owned", []))
    }


@router.get("/shop/balance", response_model=BalanceResponse)
async def get_balance(current_user: dict = Depends(enforce_all_lockdowns)):
    """Get user's SBD token balance."""
    users_collection = db_manager.get_collection("users")
    user = await users_collection.find_one({"username": current_user["username"]}, {"sbd_tokens": 1})
    
    return {
        "sbd_tokens": user.get("sbd_tokens", 0),
        "username": current_user["username"]
    }


@router.post(
    "/shop/themes/buy",
    tags=["Shop"],
    summary="Purchase a theme with SBD tokens",
    description="""
    Purchase a theme using SBD tokens from personal or family account balance.

    **Backward Compatibility:**
    - Supports both old format: `{"theme_id": "..."}` (defaults to personal tokens)
    - And new format: `{"theme_id": "...", "payment_method": {"type": "personal|family", "family_id": "..."}}`

    **Purchase Process:**
    1. Validates theme ID and user authentication
    2. Validates payment method (personal or family tokens)
    3. Checks if user already owns the theme
    4. Verifies sufficient SBD token balance and spending permissions
    5. Deducts tokens and adds theme to user's owned collection
    6. Records transaction with family member attribution if applicable
    7. Sends family notifications for family token purchases

    **Payment Methods:**
    - **Personal tokens**: Use your personal SBD token balance
    - **Family tokens**: Use tokens from a family account (requires spending permission)

    **Family Token Features:**
    - Spending permissions and limits enforced
    - Family member attribution in transaction logs
    - Automatic notifications to family members
    - Account freeze protection

    **Security Features:**
    - Server-side price validation (prices cannot be manipulated by client)
    - Atomic transaction processing to prevent race conditions
    - Ownership verification to prevent duplicate purchases
    - Comprehensive transaction logging with family context

    **SBD Token System:**
    - Themes cost 250 SBD tokens each
    - Tokens are deducted from selected account balance
    - All transactions are logged with unique transaction IDs
    - Failed purchases do not deduct tokens

    **Theme Ownership:**
    - Purchased themes are permanently owned
    - Can be used across all supported applications
    - Ownership is immediately available after purchase
    """,
    responses={
        200: {
            "description": "Theme purchased successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "personal_purchase": {
                            "summary": "Successful personal token purchase",
                            "value": {
                                "status": "success",
                                "theme": {
                                    "theme_id": "emotion_tracker-serenityGreen",
                                    "unlocked_at": "2024-01-01T12:00:00Z",
                                    "permanent": True,
                                    "source": "purchase",
                                    "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "note": "Bought from shop",
                                    "price": 250,
                                },
                                "payment": {"payment_type": "personal", "from_account": "username", "amount": 250},
                            },
                        },
                        "family_purchase": {
                            "summary": "Successful family token purchase",
                            "value": {
                                "status": "success",
                                "theme": {
                                    "theme_id": "emotion_tracker-serenityGreen",
                                    "unlocked_at": "2024-01-01T12:00:00Z",
                                    "permanent": True,
                                    "source": "purchase",
                                    "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "note": "Bought from shop",
                                    "price": 250,
                                },
                                "payment": {
                                    "payment_type": "family",
                                    "from_account": "family_smiths",
                                    "family_name": "Smith Family",
                                    "amount": 250,
                                    "family_member": "username",
                                },
                            },
                        },
                        "legacy_purchase": {
                            "summary": "Legacy format purchase (backward compatible)",
                            "value": {
                                "status": "success",
                                "theme": {
                                    "theme_id": "emotion_tracker-serenityGreen",
                                    "unlocked_at": "2024-01-01T12:00:00Z",
                                    "permanent": True,
                                    "source": "purchase",
                                    "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "note": "Bought from shop",
                                    "price": 250,
                                },
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid request or insufficient funds",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_theme": {
                            "summary": "Invalid theme ID",
                            "value": {"status": "error", "detail": "Invalid or missing theme_id"},
                        },
                        "already_owned": {
                            "summary": "Theme already owned",
                            "value": {"status": "error", "detail": "Theme already owned"},
                        },
                        "insufficient_personal_funds": {
                            "summary": "Not enough personal SBD tokens",
                            "value": {
                                "status": "error",
                                "detail": {
                                    "error": "INSUFFICIENT_PERSONAL_TOKENS",
                                    "message": "Insufficient personal tokens. Required: 250, Available: 100",
                                },
                            },
                        },
                        "invalid_payment_method": {
                            "summary": "Invalid payment method",
                            "value": {
                                "status": "error",
                                "detail": {
                                    "error": "INVALID_PAYMENT_TYPE",
                                    "message": "Invalid payment type: invalid. Must be 'personal' or 'family'",
                                },
                            },
                        },
                    }
                }
            },
        },
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        403: {
            "description": "Access denied - invalid client or family spending denied",
            "content": {
                "application/json": {
                    "examples": {
                        "access_denied": {
                            "summary": "Invalid client",
                            "value": {"status": "error", "detail": "Shop access denied: invalid client"},
                        },
                        "family_spending_denied": {
                            "summary": "Family spending permission denied",
                            "value": {
                                "status": "error",
                                "detail": {
                                    "error": "FAMILY_SPENDING_DENIED",
                                    "message": "You don't have permission to spend from this family account",
                                },
                            },
                        },
                    }
                }
            },
        },
        404: {
            "description": "Theme not found",
            "content": {
                "application/json": {
                    "examples": {
                        "not_found": {
                            "summary": "Theme not found",
                            "value": {"status": "error", "detail": "Theme not found"},
                        }
                    }
                }
            },
        },
        500: {"description": "Internal server error", "model": StandardErrorResponse},
    },
)
async def buy_theme(
    request: Request,
    data: dict = Body(...),  # Accept raw dict for backward compatibility
    current_user: dict = Depends(enforce_all_lockdowns),
):
    # Set up logging context
    request_id = str(uuid4())[:8]
    client_ip = security_manager.get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    username = current_user["username"]
    user_id = str(current_user["_id"])

    # Handle backward compatibility - support both old and new request formats
    if "payment_method" in data:
        # New format with payment method
        try:
            purchase_request = ThemePurchaseRequest(**data)
            theme_id = purchase_request.theme_id
            payment_method = purchase_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens
        theme_id = data.get("theme_id")
        payment_method = PaymentMethod(type="personal")

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    start_time = time.time()

    logger.info(
        "[%s] POST /shop/themes/buy - User: %s, IP: %s, Theme: %s, Payment: %s, User-Agent: %s",
        request_id,
        username,
        client_ip,
        theme_id,
        payment_method.type,
        user_agent[:100],
    )

    try:
        if not theme_id or not theme_id.startswith("emotion_tracker-"):
            logger.warning(
                "[%s] POST /shop/themes/buy validation failed - User: %s, Invalid theme_id: %s",
                request_id,
                username,
                theme_id,
            )
            return JSONResponse({"status": "error", "detail": "Invalid or missing theme_id"}, status_code=400)

        if "emotion_tracker" not in user_agent:
            logger.warning(
                "[%s] POST /shop/themes/buy access denied - User: %s, Invalid client: %s",
                request_id,
                username,
                user_agent[:100],
            )
            return JSONResponse({"status": "error", "detail": "Shop access denied: invalid client"}, status_code=403)

        # Get theme details from server-side registry
        theme_details = await get_item_details(theme_id, "theme")
        if not theme_details:
            logger.warning(
                "[%s] POST /shop/themes/buy theme not found - User: %s, Theme: %s", request_id, username, theme_id
            )
            return JSONResponse({"status": "error", "detail": "Theme not found"}, status_code=404)

        price = theme_details["price"]

        # Database operations with logging
        users_collection = db_manager.get_collection("users")

        db_start = time.time()
        user = await users_collection.find_one({"username": username}, {"themes_owned": 1})
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB find_one for user verification completed in %.3fs - User: %s", request_id, db_duration, username
        )

        if not user:
            logger.warning("[%s] POST /shop/themes/buy user not found - User: %s", request_id, username)
            return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)

        # Check ownership
        for owned in user.get("themes_owned", []):
            if owned["theme_id"] == theme_id:
                logger.warning(
                    "[%s] POST /shop/themes/buy already owned - User: %s, Theme: %s", request_id, username, theme_id
                )
                return JSONResponse({"status": "error", "detail": "Theme already owned"}, status_code=400)

        # Validate payment method and check balance
        try:
            payment_details = await validate_payment_method(payment_method, user_id, username, price)
        except HTTPException as e:
            if (
                e.status_code == 403
                and isinstance(e.detail, dict)
                and e.detail.get("error") == "FAMILY_SPENDING_DENIED"
            ):
                logger.info(
                    "[%s] Family spending denied for user %s, creating purchase request.",
                    request_id,
                    username,
                )
                try:
                    # Create a purchase request
                    purchase_request = await family_manager.create_purchase_request(
                        family_id=payment_method.family_id,
                        requester_id=user_id,
                        item_info={
                            "item_id": theme_id,
                            "name": theme_details["name"],
                            "item_type": "theme",
                            "image_url": None,  # Or get it from somewhere if available
                        },
                        cost=price,
                        request_context={
                            "request_id": request_id,
                            "ip_address": client_ip,
                        },
                    )
                    return JSONResponse(
                        {
                            "status": "pending_approval",
                            "detail": "Purchase request created and is pending approval from a family admin.",
                            "purchase_request": purchase_request,
                        },
                        status_code=202,
                    )
                except Exception as pr_e:
                    logger.error(
                        "[%s] Failed to create purchase request for user %s: %s",
                        request_id,
                        username,
                        pr_e,
                    )
                    # Fallback to the original error
                    return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

            logger.warning(
                "[%s] POST /shop/themes/buy payment validation failed - User: %s, Error: %s",
                request_id,
                username,
                e.detail,
            )
            return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

        # Prepare transaction data
        now_iso = datetime.now(timezone.utc).isoformat()
        transaction_id = str(uuid4())
        theme_entry = {
            "theme_id": theme_id,
            "unlocked_at": now_iso,
            "permanent": True,
            "source": "purchase",
            "transaction_id": transaction_id,
            "note": "Bought from shop",
            "price": price,
        }

        # Process payment
        try:
            payment_result = await process_payment(payment_details, price, theme_details, current_user, transaction_id)
        except HTTPException as e:
            logger.warning(
                "[%s] POST /shop/themes/buy payment processing failed - User: %s, Error: %s",
                request_id,
                username,
                e.detail,
            )
            return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

        # Add theme to the correct owned collection (user or family)
        db_start = time.time()
        # Default target is the purchasing user
        target_username = username
        theme_entry_to_store = dict(theme_entry)
        if payment_result.get("payment_type") == "family":
            # Store on family virtual account and include audit fields
            target_username = payment_result.get("from_account")
            theme_entry_to_store.update(
                {
                    "purchased_by_user_id": user_id,
                    "purchased_by_username": username,
                    "family_transaction_id": transaction_id,
                }
            )

        result = await users_collection.update_one(
            {"username": target_username},
            {"$push": {"themes_owned": theme_entry_to_store}},
            upsert=True,
        )
        db_duration = time.time() - db_start

        logger.info(
            "[%s] DB update_one for theme ownership completed in %.3fs - User: %s, Modified: %d",
            request_id,
            db_duration,
            username,
            result.modified_count,
        )

        if result.modified_count == 0:
            logger.error(
                "[%s] POST /shop/themes/buy failed to add theme to user - User: %s, Theme: %s",
                request_id,
                username,
                theme_id,
            )
            return JSONResponse({"status": "error", "detail": "Failed to add theme to user account"}, status_code=500)

        duration = time.time() - start_time
        logger.info(
            "[%s] POST /shop/themes/buy completed in %.3fs - User: %s, Theme: %s, Price: %d, Payment: %s, TxnID: %s",
            request_id,
            duration,
            username,
            theme_id,
            price,
            payment_method.type,
            transaction_id,
        )

        # Return format based on request type for backward compatibility
        response = {"status": "success", "theme": theme_entry}

        # Only include payment details if new format was used
        if "payment_method" in data:
            response["payment"] = payment_result

        return response

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "[%s] POST /shop/themes/buy failed after %.3fs - User: %s, Error: %s",
            request_id,
            duration,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "ip": client_ip, "request_id": request_id, "theme_id": theme_id},
            operation="buy_theme",
        )
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)


@router.post("/shop/avatars/buy", tags=["Shop"], summary="Buy an avatar with SBD tokens")
async def buy_avatar(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Purchase an avatar using SBD tokens from a personal or family account.

    This endpoint allows a user to purchase an avatar. It supports two payment methods:
    - **Personal:** Uses the user's own SBD token balance.
    - **Family:** Uses a shared family SBD token account. If the user does not have
      sufficient permissions to spend the required amount, a purchase request is
      created for an administrator to approve.

    **Purchase Process:**
    1. Validates the avatar ID and user authentication.
    2. Validates the selected payment method.
    3. Checks if the user already owns the avatar.
    4. Verifies sufficient SBD token balance and spending permissions.
    5. If payment is from a family account and permissions are insufficient, a purchase
       request is created for admin approval.
    6. Otherwise, the tokens are deducted and the avatar is added to the user's or family's
       owned collection.
    7. A transaction record is created, and for family purchases, a notification is sent.

    Args:
        request (Request): The incoming request object.
        data (dict): A dictionary containing the purchase details:
            - `avatar_id` (str): The ID of the avatar to purchase.
            - `payment_method` (PaymentMethod): The selected payment method.
        current_user (dict): The authenticated user, injected by Depends.

    Returns:
        dict: A dictionary confirming the successful purchase, or a pending approval status
              if a family purchase request was created.
    """
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])

    # Handle backward compatibility
    if "payment_method" in data:
        # New format with payment method
        try:
            purchase_request = AvatarPurchaseRequest(**data)
            avatar_id = purchase_request.avatar_id
            payment_method = purchase_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens
        avatar_id = data.get("avatar_id")
        payment_method = PaymentMethod(type="personal")

    if not avatar_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing avatar_id"}, status_code=400)

    # Get avatar details from server-side registry
    avatar_details = await get_item_details(avatar_id, "avatar")
    if not avatar_details:
        return JSONResponse({"status": "error", "detail": "Avatar not found"}, status_code=404)

    price = avatar_details["price"]

    # Check if user already owns the avatar
    user = await users_collection.find_one({"username": username}, {"avatars_owned": 1})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)

    if any(owned.get("avatar_id") == avatar_id for owned in user.get("avatars_owned", [])):
        return JSONResponse({"status": "error", "detail": "Avatar already owned"}, status_code=400)

    # Validate payment method and check balance
    try:
        payment_details = await validate_payment_method(payment_method, user_id, username, price)
    except HTTPException as e:
        if e.status_code == 403 and isinstance(e.detail, dict) and e.detail.get("error") == "FAMILY_SPENDING_DENIED":
            client_ip = security_manager.get_client_ip(request)
            request_id = str(uuid4())[:8]
            logger.info(f"[AVATAR BUY] Family spending denied for user {username}, creating purchase request.")
            try:
                # Create a purchase request
                purchase_request = await family_manager.create_purchase_request(
                    family_id=payment_method.family_id,
                    requester_id=user_id,
                    item_info={
                        "item_id": avatar_id,
                        "name": avatar_details["name"],
                        "item_type": "avatar",
                        "image_url": None,  # Or get it from somewhere if available
                    },
                    cost=price,
                    request_context={
                        "request_id": request_id,
                        "ip_address": client_ip,
                    },
                )
                return JSONResponse(
                    {
                        "status": "pending_approval",
                        "detail": "Purchase request created and is pending approval from a family admin.",
                        "purchase_request": purchase_request,
                    },
                    status_code=202,
                )
            except Exception as pr_e:
                logger.error(f"[AVATAR BUY ERROR] Failed to create purchase request for user {username}: {pr_e}")
                # Fallback to the original error
                return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

    # Prepare transaction data
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    avatar_entry = {
        "avatar_id": avatar_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price,
    }

    try:
        logger.info(
            f"[AVATAR BUY] User: {username} attempting to buy avatar_id={avatar_id} for price={price} using {payment_method.type}"
        )

        # Process payment
        payment_result = await process_payment(payment_details, price, avatar_details, current_user, transaction_id)

        # Add avatar to the correct owned collection (user or family)
        target_username = username
        avatar_entry_to_store = dict(avatar_entry)
        if payment_result.get("payment_type") == "family":
            target_username = payment_result.get("from_account")
            avatar_entry_to_store.update(
                {
                    "purchased_by_user_id": user_id,
                    "purchased_by_username": username,
                    "family_transaction_id": transaction_id,
                }
            )

        result = await users_collection.update_one(
            {"username": target_username},
            {"$push": {"avatars_owned": avatar_entry_to_store}},
            upsert=True,
        )

        logger.info(f"[AVATAR BUY] Update result for user {username}: modified_count={result.modified_count}")

        if result.modified_count == 0:
            logger.error(f"[AVATAR BUY] Failed to add avatar to user {username} buying avatar_id={avatar_id}")
            return JSONResponse({"status": "error", "detail": "Failed to add avatar to user account"}, status_code=500)

        logger.info(
            f"[AVATAR BUY] User: {username} successfully bought avatar_id={avatar_id} (txn_id={transaction_id}) using {payment_method.type}"
        )

        # Return format based on request type for backward compatibility
        response = {"status": "success", "avatar": avatar_entry}

        # Only include payment details if new format was used
        if "payment_method" in data:
            response["payment"] = payment_result

        return response

    except HTTPException as e:
        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    except Exception as e:
        logger.error(f"[AVATAR BUY ERROR] User: {username}, avatar_id={avatar_id}, error={e}")
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)


@router.post("/shop/banners/buy", tags=["Shop"], summary="Buy a banner with SBD tokens")
async def buy_banner(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Purchase a banner using SBD tokens from a personal or family account.

    This endpoint allows a user to purchase a banner. It supports two payment methods:
    - **Personal:** Uses the user's own SBD token balance.
    - **Family:** Uses a shared family SBD token account. If the user does not have
      sufficient permissions to spend the required amount, a purchase request is
      created for an administrator to approve.

    **Purchase Process:**
    1. Validates the banner ID and user authentication.
    2. Validates the selected payment method.
    3. Checks if the user already owns the banner.
    4. Verifies sufficient SBD token balance and spending permissions.
    5. If payment is from a family account and permissions are insufficient, a purchase
       request is created for admin approval.
    6. Otherwise, the tokens are deducted and the banner is added to the user's or family's
       owned collection.
    7. A transaction record is created, and for family purchases, a notification is sent.

    Args:
        request (Request): The incoming request object.
        data (dict): A dictionary containing the purchase details:
            - `banner_id` (str): The ID of the banner to purchase.
            - `payment_method` (PaymentMethod): The selected payment method.
        current_user (dict): The authenticated user, injected by Depends.

    Returns:
        dict: A dictionary confirming the successful purchase, or a pending approval status
              if a family purchase request was created.
    """
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])

    # Handle backward compatibility
    if "payment_method" in data:
        # New format with payment method
        try:
            purchase_request = BannerPurchaseRequest(**data)
            banner_id = purchase_request.banner_id
            payment_method = purchase_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens
        banner_id = data.get("banner_id")
        payment_method = PaymentMethod(type="personal")

    if not banner_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing banner_id"}, status_code=400)

    # Get banner details from server-side registry
    banner_details = await get_item_details(banner_id, "banner")
    if not banner_details:
        return JSONResponse({"status": "error", "detail": "Banner not found"}, status_code=404)

    price = banner_details["price"]

    # Check if user already owns the banner
    user = await users_collection.find_one({"username": username}, {"banners_owned": 1})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)

    if any(owned.get("banner_id") == banner_id for owned in user.get("banners_owned", [])):
        return JSONResponse({"status": "error", "detail": "Banner already owned"}, status_code=400)

    # Validate payment method and check balance
    try:
        payment_details = await validate_payment_method(payment_method, user_id, username, price)
    except HTTPException as e:
        if e.status_code == 403 and isinstance(e.detail, dict) and e.detail.get("error") == "FAMILY_SPENDING_DENIED":
            client_ip = security_manager.get_client_ip(request)
            request_id = str(uuid4())[:8]
            logger.info(f"[BANNER BUY] Family spending denied for user {username}, creating purchase request.")
            try:
                # Create a purchase request
                purchase_request = await family_manager.create_purchase_request(
                    family_id=payment_method.family_id,
                    requester_id=user_id,
                    item_info={
                        "item_id": banner_id,
                        "name": banner_details["name"],
                        "item_type": "banner",
                        "image_url": None,  # Or get it from somewhere if available
                    },
                    cost=price,
                    request_context={
                        "request_id": request_id,
                        "ip_address": client_ip,
                    },
                )
                return JSONResponse(
                    {
                        "status": "pending_approval",
                        "detail": "Purchase request created and is pending approval from a family admin.",
                        "purchase_request": purchase_request,
                    },
                    status_code=202,
                )
            except Exception as pr_e:
                logger.error(f"[BANNER BUY ERROR] Failed to create purchase request for user {username}: {pr_e}")
                # Fallback to the original error
                return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

    # Prepare transaction data
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    banner_entry = {
        "banner_id": banner_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price,
    }

    try:
        logger.info(
            f"[BANNER BUY] User: {username} attempting to buy banner_id={banner_id} for price={price} using {payment_method.type}"
        )

        # Process payment
        payment_result = await process_payment(payment_details, price, banner_details, current_user, transaction_id)

        # Add banner to the correct owned collection (user or family)
        target_username = username
        banner_entry_to_store = dict(banner_entry)
        if payment_result.get("payment_type") == "family":
            target_username = payment_result.get("from_account")
            banner_entry_to_store.update(
                {
                    "purchased_by_user_id": user_id,
                    "purchased_by_username": username,
                    "family_transaction_id": transaction_id,
                }
            )

        result = await users_collection.update_one(
            {"username": target_username},
            {"$push": {"banners_owned": banner_entry_to_store}},
            upsert=True,
        )

        logger.info(f"[BANNER BUY] Update result for user {username}: modified_count={result.modified_count}")

        if result.modified_count == 0:
            logger.error(f"[BANNER BUY] Failed to add banner to user {username} buying banner_id={banner_id}")
            return JSONResponse({"status": "error", "detail": "Failed to add banner to user account"}, status_code=500)

        logger.info(
            f"[BANNER BUY] User: {username} successfully bought banner_id={banner_id} (txn_id={transaction_id}) using {payment_method.type}"
        )

        # Return format based on request type for backward compatibility
        response = {"status": "success", "banner": banner_entry}

        # Only include payment details if new format was used
        if "payment_method" in data:
            response["payment"] = payment_result

        return response

    except HTTPException as e:
        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    except Exception as e:
        logger.error(f"[BANNER BUY ERROR] User: {username}, banner_id={banner_id}, error={e}")
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)


@router.post("/shop/bundles/buy", tags=["Shop"], summary="Buy a bundle with SBD tokens")
async def buy_bundle(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Purchase a bundle of items using SBD tokens from a personal or family account.

    This endpoint allows a user to purchase a bundle of items, such as avatars or themes.
    It supports two payment methods:
    - **Personal:** Uses the user's own SBD token balance.
    - **Family:** Uses a shared family SBD token account. If the user does not have
      sufficient permissions to spend the required amount, a purchase request is
      created for an administrator to approve.

    **Purchase Process:**
    1. Validates the bundle ID and user authentication.
    2. Validates the selected payment method.
    3. Checks if the user already owns the bundle.
    4. Verifies sufficient SBD token balance and spending permissions.
    5. If payment is from a family account and permissions are insufficient, a purchase
       request is created for admin approval.
    6. Otherwise, the tokens are deducted and the bundle and its contents are added to the
       user's or family's owned collection.
    7. A transaction record is created, and for family purchases, a notification is sent.

    Args:
        request (Request): The incoming request object.
        data (dict): A dictionary containing the purchase details:
            - `bundle_id` (str): The ID of the bundle to purchase.
            - `payment_method` (PaymentMethod): The selected payment method.
        current_user (dict): The authenticated user, injected by Depends.

    Returns:
        dict: A dictionary confirming the successful purchase, or a pending approval status
              if a family purchase request was created.
    """
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])

    # Handle backward compatibility
    if "payment_method" in data:
        # New format with payment method
        try:
            purchase_request = BundlePurchaseRequest(**data)
            bundle_id = purchase_request.bundle_id
            payment_method = purchase_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens
        bundle_id = data.get("bundle_id")
        payment_method = PaymentMethod(type="personal")

    if not bundle_id:
        return JSONResponse({"status": "error", "detail": "Invalid or missing bundle_id"}, status_code=400)

    # Get bundle details from server-side registry
    bundle_details = await get_item_details(bundle_id, "bundle")
    if not bundle_details:
        return JSONResponse({"status": "error", "detail": "Bundle not found"}, status_code=404)

    price = bundle_details["price"]

    # Check if user already owns the bundle
    user = await users_collection.find_one(
        {"username": username},
        {"bundles_owned": 1, "avatars_owned": 1, "themes_owned": 1, "banners_owned": 1},
    )
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)

    if bundle_id in user.get("bundles_owned", []):
        return JSONResponse({"status": "error", "detail": "Bundle already owned"}, status_code=400)

    # Validate payment method and check balance
    try:
        payment_details = await validate_payment_method(payment_method, user_id, username, price)
    except HTTPException as e:
        if e.status_code == 403 and isinstance(e.detail, dict) and e.detail.get("error") == "FAMILY_SPENDING_DENIED":
            client_ip = security_manager.get_client_ip(request)
            request_id = str(uuid4())[:8]
            logger.info(f"[BUNDLE BUY] Family spending denied for user {username}, creating purchase request.")
            try:
                # Create a purchase request
                purchase_request = await family_manager.create_purchase_request(
                    family_id=payment_method.family_id,
                    requester_id=user_id,
                    item_info={
                        "item_id": bundle_id,
                        "name": bundle_details["name"],
                        "item_type": "bundle",
                        "image_url": None,  # Or get it from somewhere if available
                    },
                    cost=price,
                    request_context={
                        "request_id": request_id,
                        "ip_address": client_ip,
                    },
                )
                return JSONResponse(
                    {
                        "status": "pending_approval",
                        "detail": "Purchase request created and is pending approval from a family admin.",
                        "purchase_request": purchase_request,
                    },
                    status_code=202,
                )
            except Exception as pr_e:
                logger.error(f"[BUNDLE BUY ERROR] Failed to create purchase request for user {username}: {pr_e}")
                # Fallback to the original error
                return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

    # Prepare transaction data
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid4())
    bundle_entry = {
        "bundle_id": bundle_id,
        "unlocked_at": now_iso,
        "permanent": True,
        "source": "purchase",
        "transaction_id": transaction_id,
        "note": "Bought from shop",
        "price": price,
    }

    try:
        logger.info(
            f"[BUNDLE BUY] User: {username} attempting to buy bundle_id={bundle_id} for price={price} using {payment_method.type}"
        )

        # Process payment
        payment_result = await process_payment(payment_details, price, bundle_details, current_user, transaction_id)

        # Add bundle to the correct owned collection (user or family)
        target_username = username
        bundle_entry_to_store = dict(bundle_entry)
        if payment_result.get("payment_type") == "family":
            target_username = payment_result.get("from_account")
            bundle_entry_to_store.update(
                {
                    "purchased_by_user_id": user_id,
                    "purchased_by_username": username,
                    "family_transaction_id": transaction_id,
                }
            )

        result = await users_collection.update_one(
            {"username": target_username},
            {"$push": {"bundles_owned": bundle_entry_to_store}},
            upsert=True,
        )

        if result.modified_count == 0:
            logger.error(f"[BUNDLE BUY] Failed to add bundle to user {username} buying bundle_id={bundle_id}")
            return JSONResponse({"status": "error", "detail": "Failed to add bundle to user account"}, status_code=500)

        # Auto-populate bundle contents (avatars, themes, banners)
        update_operations = {}
        now_iso_checkout = datetime.now(timezone.utc).isoformat()

        bundle_contents = BUNDLE_CONTENTS.get(bundle_id, {})

        # Add avatars from bundle
        for avatar_id in bundle_contents.get("avatars", []):
            avatar_entry = {
                "avatar_id": avatar_id,
                "unlocked_at": now_iso_checkout,
                "permanent": True,
                "source": f"bundle:{bundle_id}",
                "transaction_id": transaction_id,
                "note": f"Unlocked via bundle {bundle_id}",
                "price": 0,
            }
            update_operations.setdefault("avatars_owned", {"$each": []})["$each"].append(avatar_entry)

        # Add themes from bundle
        for theme_id in bundle_contents.get("themes", []):
            theme_entry = {
                "theme_id": theme_id,
                "unlocked_at": now_iso_checkout,
                "permanent": True,
                "source": f"bundle:{bundle_id}",
                "transaction_id": transaction_id,
                "note": f"Unlocked via bundle {bundle_id}",
                "price": 0,
            }
            update_operations.setdefault("themes_owned", {"$each": []})["$each"].append(theme_entry)

        # Add banners from bundle
        for banner_id in bundle_contents.get("banners", []):
            banner_entry = {
                "banner_id": banner_id,
                "unlocked_at": now_iso_checkout,
                "permanent": True,
                "source": f"bundle:{bundle_id}",
                "transaction_id": transaction_id,
                "note": f"Unlocked via bundle {bundle_id}",
                "price": 0,
            }
            update_operations.setdefault("banners_owned", {"$each": []})["$each"].append(banner_entry)

        # Perform all updates for bundle contents
        for owned_field, push_value in update_operations.items():
            await users_collection.update_one({"username": username}, {"$push": {owned_field: push_value}})

        logger.info(
            f"[BUNDLE BUY] User: {username} successfully bought bundle_id={bundle_id} (txn_id={transaction_id}) using {payment_method.type}"
        )

        # Return format based on request type for backward compatibility
        response = {"status": "success", "bundle": bundle_entry, "bundle_contents": bundle_contents}

        # Only include payment details if new format was used
        if "payment_method" in data:
            response["payment"] = payment_result

        return response

    except HTTPException as e:
        return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    except Exception as e:
        logger.error(f"[BUNDLE BUY ERROR] User: {username}, bundle_id={bundle_id}, error={e}")
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)
        # --- Auto-populate bundle contents ---
        bundle_contents = BUNDLE_CONTENTS.get(bundle_id, {})
        update_ops = {}
        # Add avatars from bundle
        for avatar_id in bundle_contents.get("avatars", []):
            if not any(owned.get("avatar_id") == avatar_id for owned in user.get("avatars_owned", [])):
                avatar_entry = {
                    "avatar_id": avatar_id,
                    "unlocked_at": now_iso,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id}",
                    "price": 0,
                }
                update_ops.setdefault("avatars_owned", []).append(avatar_entry)
        # Add themes from bundle
        for theme_id in bundle_contents.get("themes", []):
            if not any(owned.get("theme_id") == theme_id for owned in user.get("themes_owned", [])):
                theme_entry = {
                    "theme_id": theme_id,
                    "unlocked_at": now_iso,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id}",
                    "price": 0,
                }
                update_ops.setdefault("themes_owned", []).append(theme_entry)
        # Add banners from bundle (if you have such bundles)
        for banner_id in bundle_contents.get("banners", []):
            if not any(owned.get("banner_id") == banner_id for owned in user.get("banners_owned", [])):
                banner_entry = {
                    "banner_id": banner_id,
                    "unlocked_at": now_iso,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id}",
                    "price": 0,
                }
                update_ops.setdefault("banners_owned", []).append(banner_entry)
        # Perform the update for each owned type
        for field, entries in update_ops.items():
            await users_collection.update_one({"username": username}, {"$push": {field: {"$each": entries}}})
        return {"status": "success", "bundle": bundle_entry, "unlocked_items": update_ops}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": "Internal server error", "error": str(e)}, status_code=500)


@router.post("/shop/cart/add", tags=["shop"], summary="Add an item to the cart by ID")
async def add_to_cart(request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Add an item to the user's shopping cart for a specific application.

    This endpoint adds a specified item to the user's cart. The cart is specific to the
    application making the request, identified by the `User-Agent` header.

    **Item Types:**
    - `theme`
    - `avatar`
    - `bundle`
    - `banner`

    Args:
        request (Request): The incoming request object.
        data (dict): A dictionary containing the `item_id` and `item_type`.
        current_user (dict): The authenticated user, injected by Depends.

    Returns:
        dict: A dictionary confirming the successful addition of the item to the cart.
    """
    shop_collection = db_manager.get_tenant_collection(SHOP_COLLECTION)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    item_id = data.get("item_id")
    item_type = data.get("item_type")  # "theme", "avatar", "bundle", "banner"
    user_agent = request.headers.get("user-agent", "unknown").lower()
    app_name = user_agent.split("/")[0].strip() if "/" in user_agent else user_agent

    if not all([item_id, item_type]):
        return JSONResponse({"status": "error", "detail": "Missing item_id or item_type"}, status_code=400)

    # Check if user already owns the item
    user = await users_collection.find_one({"username": username})
    owned_field = f"{item_type}s_owned"
    id_key = f"{item_type}_id"
    if any(owned_item.get(id_key) == item_id for owned_item in user.get(owned_field, [])):
        return JSONResponse({"status": "error", "detail": "You already own this item."}, status_code=400)

    # Get item details securely from the server-side registry
    item_details = await get_item_details(item_id, item_type)
    if not item_details:
        return JSONResponse({"status": "error", "detail": "Item not found"}, status_code=404)

    # Check if item is already in the cart for this app
    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})
    cart = carts.get(app_name, [])
    if any(item.get(id_key) == item_id for item in cart):
        return JSONResponse({"status": "error", "detail": "Item already in cart."}, status_code=400)

    item_details["added_at"] = datetime.now(timezone.utc).isoformat()

    await get_or_create_shop_doc(username)
    # Use $addToSet to prevent duplicate items in the cart
    await shop_collection.update_one({"username": username}, {"$addToSet": {f"carts.{app_name}": item_details}})
    return {"status": "success", "added": item_details, "app": app_name}


@router.delete("/shop/cart/remove", tags=["shop"], summary="Remove item from a cart")
async def remove_from_cart(
    request: Request, data: dict = Body(...), current_user: dict = Depends(enforce_all_lockdowns)
):
    """
    Remove an item from the user's shopping cart for a specific application.

    This endpoint removes a specified item from the user's cart. The cart is specific to the
    application making the request, identified by the `User-Agent` header.

    Args:
        request (Request): The incoming request object.
        data (dict): A dictionary containing the `item_id` and `item_type` of the item to remove.
        current_user (dict): The authenticated user, injected by Depends.

    Returns:
        dict: A dictionary confirming the successful removal of the item from the cart.
    """
    shop_collection = db_manager.get_tenant_collection(SHOP_COLLECTION)
    username = current_user["username"]
    item_id = data.get("item_id")
    item_type = data.get("item_type")
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split("/")[0].strip() if user_agent and "/" in user_agent else user_agent

    if not all([item_id, item_type, app_name]):
        return JSONResponse(
            {"status": "error", "detail": "Missing item_id, item_type, or a valid user-agent header"}, status_code=400
        )

    # Normalize item_type to be singular for key construction
    if item_type.endswith("s"):
        item_type = item_type[:-1]

    id_key = f"{item_type}_id"
    item_to_remove = {id_key: item_id}

    # Remove from a specific app's cart
    result = await shop_collection.update_one({"username": username}, {"$pull": {f"carts.{app_name}": item_to_remove}})
    if result.modified_count > 0:
        return {"status": "success", "removed_id": item_id, "app": app_name}
    else:
        return JSONResponse(
            {"status": "error", "detail": f"Item not found in cart for app '{app_name}'"}, status_code=404
        )


@router.delete("/shop/cart/clear", tags=["shop"], summary="Clear all items from a cart")
async def clear_cart(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Clears items from a user's shopping cart for a specific app, identified by user-agent.
    """
    shop_collection = db_manager.get_tenant_collection(SHOP_COLLECTION)
    username = current_user["username"]
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split("/")[0].strip() if user_agent and "/" in user_agent else user_agent

    if not app_name:
        return JSONResponse(
            {"status": "error", "detail": "The 'user-agent' header is required and must be in a valid format."},
            status_code=400,
        )

    # Clear a specific app's cart
    result = await shop_collection.update_one(
        {"username": username, f"carts.{app_name}": {"$exists": True}}, {"$set": {f"carts.{app_name}": []}}
    )
    if result.modified_count > 0:
        return {"status": "success", "detail": f"Cart for app '{app_name}' has been cleared."}
    else:
        # This can mean the cart didn't exist or was already empty.
        return {"status": "success", "detail": f"Cart for app '{app_name}' is now empty."}


@router.get("/shop/cart", tags=["shop"], summary="Get a specific app cart")
async def get_cart(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    shop_collection = db_manager.get_tenant_collection(SHOP_COLLECTION)
    username = current_user["username"]
    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split("/")[0].strip() if user_agent and "/" in user_agent else user_agent

    if not app_name:
        return JSONResponse(
            {"status": "error", "detail": "The 'user-agent' header is required and must be in a valid format."},
            status_code=400,
        )

    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})

    # Return a specific app's cart
    cart = carts.get(app_name, [])
    return {"status": "success", "app": app_name, "cart": cart}


@router.post("/shop/cart/checkout", tags=["shop"], summary="Checkout a specific app cart with payment method selection")
async def checkout_cart(request: Request, data: dict = Body({}), current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Checkout the user's shopping cart for a specific application.

    This endpoint processes the checkout for all items in the user's cart for the application
    making the request. It supports two payment methods:
    - **Personal:** Uses the user's own SBD token balance.
    - **Family:** Uses a shared family SBD token account. If the user does not have
      sufficient permissions to spend the required amount, a purchase request is
      created for each item in the cart for an administrator to approve.

    **Checkout Process:**
    1. Calculates the total price of all items in the cart.
    2. Validates the selected payment method.
    3. Verifies sufficient SBD token balance and spending permissions.
    4. If payment is from a family account and permissions are insufficient, a purchase
       request is created for each item for admin approval.
    5. Otherwise, the total amount is deducted and the items are added to the user's or
       family's owned collection.
    6. The cart for the application is cleared.
    7. A transaction record is created, and for family purchases, a notification is sent.

    Args:
        request (Request): The incoming request object.
        data (dict): A dictionary containing the `payment_method`.
        current_user (dict): The authenticated user, injected by Depends.

    Returns:
        dict: A dictionary confirming the successful checkout, or a pending approval status
              if purchase requests were created.
    """
    shop_collection = db_manager.get_tenant_collection(SHOP_COLLECTION)
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user_id = str(current_user["_id"])

    # Handle backward compatibility
    if data and "payment_method" in data:
        # New format with payment method
        try:
            checkout_request = CartCheckoutRequest(**data)
            payment_method = checkout_request.payment_method
        except Exception as e:
            return JSONResponse({"status": "error", "detail": f"Invalid request format: {str(e)}"}, status_code=400)
    else:
        # Legacy format - default to personal tokens (empty body or no payment_method)
        payment_method = PaymentMethod(type="personal")

    user_agent = request.headers.get("user-agent", "").lower()
    app_name = user_agent.split("/")[0].strip() if user_agent and "/" in user_agent else user_agent
    if not app_name:
        return JSONResponse(
            {"status": "error", "detail": "The 'user-agent' header is required and must be in a valid format."},
            status_code=400,
        )

    doc = await get_or_create_shop_doc(username)
    carts = doc.get("carts", {})

    items_to_checkout = carts.get(app_name, [])
    if not items_to_checkout:
        return JSONResponse(
            {"status": "error", "detail": f"Cart for app '{app_name}' not found or is empty."}, status_code=404
        )

    # Calculate total price from server-side details
    total_price = sum(item.get("price", 0) for item in items_to_checkout)

    # Handle payment processing based on format
    if "payment_method" in data:
        # New format with payment method selection
        try:
            payment_details = await validate_payment_method(payment_method, user_id, username, total_price)
        except HTTPException as e:
            if (
                e.status_code == 403
                and isinstance(e.detail, dict)
                and e.detail.get("error") == "FAMILY_SPENDING_DENIED"
            ):
                client_ip = security_manager.get_client_ip(request)
                request_id_base = str(uuid4())[:8]
                logger.info(
                    f"[CART CHECKOUT] Family spending denied for user {username}, creating purchase requests for cart items."
                )

                purchase_requests = []
                try:
                    for i, item in enumerate(items_to_checkout):
                        request_id = f"{request_id_base}-{i}"
                        item_type = item.get("type")
                        item_id_key = f"{item_type}_id"
                        item_id = item.get(item_id_key)

                        purchase_request = await family_manager.create_purchase_request(
                            family_id=payment_method.family_id,
                            requester_id=user_id,
                            item_info={
                                "item_id": item_id,
                                "name": item.get("name"),
                                "item_type": item_type,
                                "image_url": item.get("image_url"),
                            },
                            cost=item.get("price"),
                            request_context={
                                "request_id": request_id,
                                "ip_address": client_ip,
                            },
                        )
                        purchase_requests.append(purchase_request)

                    return JSONResponse(
                        {
                            "status": "pending_approval",
                            "detail": "Purchase requests for cart items created and are pending approval from a family admin.",
                            "purchase_requests": purchase_requests,
                        },
                        status_code=202,
                    )
                except Exception as pr_e:
                    logger.error(
                        f"[CART CHECKOUT ERROR] Failed to create purchase requests for user {username}: {pr_e}"
                    )
                    # Fallback to the original error
                    return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

            return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)

        # Prepare transaction data
        now_iso = datetime.now(timezone.utc).isoformat()
        transaction_id = str(uuid4())
        shop_name = f"{app_name}_shop"

        # Create cart details for payment processing
        cart_details = {
            "type": "cart",
            "cart_id": f"{app_name}_cart",
            "name": f"Cart checkout for {app_name}",
            "items": items_to_checkout,
        }

        # Process payment using the selected method
        try:
            payment_result = await process_payment(
                payment_details, total_price, cart_details, current_user, transaction_id
            )
        except HTTPException as e:
            return JSONResponse({"status": "error", "detail": e.detail}, status_code=e.status_code)
    else:
        # Legacy format - use personal tokens only
        user = await users_collection.find_one({"username": username}, {"sbd_tokens": 1})
        if not user or user.get("sbd_tokens", 0) < total_price:
            return JSONResponse({"status": "error", "detail": "Not enough SBD tokens"}, status_code=400)

        # Atomically deduct tokens and log transaction (legacy way)
        now_iso = datetime.now(timezone.utc).isoformat()
        transaction_id = str(uuid4())
        shop_name = f"{app_name}_shop"

        result = await users_collection.update_one(
            {"username": username, "sbd_tokens": {"$gte": total_price}},
            {
                "$inc": {"sbd_tokens": -total_price},
                "$push": {
                    "sbd_tokens_transactions": {
                        "type": "send",
                        "to": shop_name,
                        "amount": total_price,
                        "timestamp": now_iso,
                        "transaction_id": transaction_id,
                        "note": f"Checkout cart for {shop_name}",
                    }
                },
            },
        )
        if result.modified_count == 0:
            return JSONResponse(
                {"status": "error", "detail": "Insufficient SBD tokens or race condition"}, status_code=400
            )

        payment_result = {
            "payment_type": "personal",
            "from_account": username,
            "amount": total_price,
            "transaction_id": transaction_id,
        }

    # Log receive transaction for the shop (create shop user if not exists)
    if "payment_method" in data:
        # New format - use payment details
        receive_txn = {
            "type": "receive",
            "from": payment_details["account_username"],
            "amount": total_price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"Cart checkout for {shop_name}",
        }

        # Add family member attribution if payment came from family account
        if payment_details["payment_type"] == "family":
            receive_txn["family_member_id"] = user_id
            receive_txn["family_member_username"] = username
            receive_txn["note"] = f"Cart checkout by family member @{username} for {shop_name}"
    else:
        # Legacy format - simple receive transaction
        receive_txn = {
            "type": "receive",
            "from": username,
            "amount": total_price,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": f"User checked out cart for {shop_name}",
        }

    await users_collection.update_one(
        {"username": shop_name},
        {
            "$inc": {"sbd_tokens": total_price},
            "$push": {"sbd_tokens_transactions": receive_txn},
            "$setOnInsert": {"email": f"{shop_name}@rohanbatra.in"},
        },
        upsert=True,
    )

    # Distribute purchased items to the correct `*_owned` arrays
    update_operations = {}
    now_iso_checkout = datetime.now(timezone.utc).isoformat()

    for item in items_to_checkout:
        item_type = item.get("type")
        if not item_type:
            continue

        id_key = f"{item_type}_id"
        owned_field = f"{item_type}s_owned"

        # If the item is a bundle, auto-populate its contents (avatars, themes, banners)
        if item_type == "bundle":
            bundle_id = item.get("bundle_id")
            bundle_contents = BUNDLE_CONTENTS.get(bundle_id, {})
            # Add avatars from bundle
            for avatar_id in bundle_contents.get("avatars", []):
                avatar_entry = {
                    "avatar_id": avatar_id,
                    "unlocked_at": now_iso_checkout,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id} (cart)",
                    "price": 0,
                }
                update_operations.setdefault("avatars_owned", {"$each": []})["$each"].append(avatar_entry)
            # Add themes from bundle
            for theme_id in bundle_contents.get("themes", []):
                theme_entry = {
                    "theme_id": theme_id,
                    "unlocked_at": now_iso_checkout,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id} (cart)",
                    "price": 0,
                }
                update_operations.setdefault("themes_owned", {"$each": []})["$each"].append(theme_entry)
            # Add banners from bundle
            for banner_id in bundle_contents.get("banners", []):
                banner_entry = {
                    "banner_id": banner_id,
                    "unlocked_at": now_iso_checkout,
                    "permanent": True,
                    "source": f"bundle:{bundle_id}",
                    "transaction_id": transaction_id,
                    "note": f"Unlocked via bundle {bundle_id} (cart)",
                    "price": 0,
                }
                update_operations.setdefault("banners_owned", {"$each": []})["$each"].append(banner_entry)
        # Add the bundle itself to bundles_owned
        owned_item_entry = {
            id_key: item.get(id_key),
            "unlocked_at": now_iso_checkout,
            "permanent": True,
            "source": "purchase_cart",
            "transaction_id": transaction_id,
            "note": f"Purchased via cart checkout from {app_name}",
            "price": item.get("price"),
        }
        if owned_field not in update_operations:
            update_operations[owned_field] = {"$each": []}
        update_operations[owned_field]["$each"].append(owned_item_entry)

    # Perform all updates in a single operation if possible, or one per type
    # If payment_result indicates a family payment, target the family virtual account
    target_username = username
    if payment_result.get("payment_type") == "family":
        target_username = payment_result.get("from_account")
        # Add audit metadata to each pushed entry
        for field, push_value in update_operations.items():
            if "$each" in push_value:
                for entry in push_value["$each"]:
                    entry.update(
                        {
                            "purchased_by_user_id": user_id,
                            "purchased_by_username": username,
                            "family_transaction_id": transaction_id,
                        }
                    )

    for owned_field, push_value in update_operations.items():
        await users_collection.update_one(
            {"username": target_username}, {"$push": {owned_field: push_value}}, upsert=True
        )

    # Clear the relevant cart(s)
    await shop_collection.update_one({"username": username}, {"$set": {f"carts.{app_name}": []}})

    # Return format based on request type for backward compatibility
    response = {
        "status": "success",
        "checked_out": items_to_checkout,
        "total_price": total_price,
        "transaction_id": transaction_id,
    }

    # Only include payment details if new format was used
    if "payment_method" in data:
        response["payment"] = payment_result
        response["app_name"] = app_name

    return response


@router.get("/shop/avatars/owned", tags=["shop"], summary="Get user's owned avatars")
async def get_owned_avatars(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"avatars_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "avatars_owned": user.get("avatars_owned", [])}


@router.get("/shop/banners/owned", tags=["shop"], summary="Get user's owned banners")
async def get_owned_banners(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"banners_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "banners_owned": user.get("banners_owned", [])}


@router.get("/shop/bundles/owned", tags=["shop"], summary="Get user's owned bundles")
async def get_owned_bundles(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"bundles_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "bundles_owned": user.get("bundles_owned", [])}


@router.get("/shop/themes/owned", tags=["shop"], summary="Get user's owned themes")
async def get_owned_themes(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one({"username": username}, {"themes_owned": 1, "_id": 0})
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {"status": "success", "themes_owned": user.get("themes_owned", [])}


@router.get("/shop/owned", tags=["shop"], summary="Get all user's owned shop items")
async def get_all_owned(current_user: dict = Depends(enforce_all_lockdowns)):
    users_collection = db_manager.get_collection("users")
    username = current_user["username"]
    user = await users_collection.find_one(
        {"username": username},
        {"avatars_owned": 1, "banners_owned": 1, "bundles_owned": 1, "themes_owned": 1, "_id": 0},
    )
    if not user:
        return JSONResponse({"status": "error", "detail": "User not found"}, status_code=404)
    return {
        "status": "success",
        "avatars_owned": user.get("avatars_owned", []),
        "banners_owned": user.get("banners_owned", []),
        "bundles_owned": user.get("bundles_owned", []),
        "themes_owned": user.get("themes_owned", []),
    }
