"""
Shop and Asset Management MCP Tools

MCP tools for comprehensive shop browsing, purchase management, asset ownership,
and SBD token operations using existing shop and asset management patterns.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ....config import settings
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPToolError, MCPValidationError
from ..modern_server import mcp
from ..security import authenticated_tool, get_mcp_user_context

logger = get_logger(prefix="[MCP_ShopTools]")

# Import manager instances and utilities
from ....database import db_manager
from ....managers.redis_manager import redis_manager
from ....managers.security_manager import security_manager
from ....routes.shop.routes import BUNDLE_CONTENTS, get_item_details

# Pydantic models for MCP tool parameters and responses


class ShopItem(BaseModel):
    """Shop item information model."""

    item_id: str
    name: str
    price: int
    item_type: str  # "theme", "avatar", "banner", "bundle"
    description: Optional[str] = None
    category: Optional[str] = None
    featured: bool = False
    new_arrival: bool = False
    image_url: Optional[str] = None
    bundle_contents: Optional[Dict[str, List[str]]] = None


class ShopSearchFilters(BaseModel):
    """Search filters for shop items."""

    item_type: Optional[str] = Field(None, description="Filter by item type (theme, avatar, banner, bundle)")
    category: Optional[str] = Field(None, description="Filter by category")
    min_price: Optional[int] = Field(None, description="Minimum price filter")
    max_price: Optional[int] = Field(None, description="Maximum price filter")
    featured_only: bool = Field(False, description="Show only featured items")
    new_arrivals_only: bool = Field(False, description="Show only new arrivals")


class PurchaseTransaction(BaseModel):
    """Purchase transaction information."""

    transaction_id: str
    item_id: str
    item_name: str
    item_type: str
    amount: int
    payment_type: str
    timestamp: datetime
    status: str
    note: Optional[str] = None


class UserAsset(BaseModel):
    """User owned asset information."""

    asset_id: str
    asset_type: str
    name: str
    owned: bool = False
    rented: bool = False
    rental_expires: Optional[datetime] = None
    acquired_at: datetime
    source: str  # "purchase", "rental", "bundle", etc.
    price_paid: int = 0


# Shop Browsing and Search Tools (Task 6.1)


@authenticated_tool(
    name="list_shop_items",
    description="Browse available shop items with optional filtering",
    permissions=["shop:read"],
    rate_limit_action="shop_browse",
)
async def list_shop_items(
    item_type: Optional[str] = None, category: Optional[str] = None, limit: int = 50, offset: int = 0
) -> Dict[str, Any]:
    """
    Browse available shop items with optional filtering by type and category.

    Args:
        item_type: Filter by item type (theme, avatar, banner, bundle)
        category: Filter by category
        limit: Maximum number of items to return (default: 50, max: 100)
        offset: Number of items to skip for pagination

    Returns:
        Dictionary containing list of shop items and pagination info
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0

    try:
        # Create comprehensive shop catalog based on existing item registry
        shop_items = []

        # Add themes
        if not item_type or item_type == "theme":
            theme_items = [
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
            ]
            shop_items.extend(theme_items)

        # Add avatars
        if not item_type or item_type == "avatar":
            avatar_items = [
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
            ]
            shop_items.extend(avatar_items)

        # Add banners
        if not item_type or item_type == "banner":
            banner_items = [
                {
                    "item_id": "emotion_tracker-static-banner-earth-1",
                    "name": "Earth Banner",
                    "price": 100,
                    "item_type": "banner",
                    "category": "nature",
                    "description": "Beautiful Earth landscape banner",
                }
            ]
            shop_items.extend(banner_items)

        # Add bundles
        if not item_type or item_type == "bundle":
            bundle_items = [
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
            ]
            shop_items.extend(bundle_items)

        # Apply category filter
        if category:
            shop_items = [item for item in shop_items if item.get("category") == category]

        # Apply pagination
        total_items = len(shop_items)
        paginated_items = shop_items[offset : offset + limit]

        # Create audit trail
        await create_mcp_audit_trail(
            operation="list_shop_items",
            user_context=user_context,
            resource_type="shop",
            resource_id="catalog",
            metadata={
                "item_type": item_type,
                "category": category,
                "limit": limit,
                "offset": offset,
                "total_found": total_items,
            },
        )

        logger.info(
            "User %s browsed shop items: type=%s, category=%s, found=%d",
            user_context.username,
            item_type,
            category,
            total_items,
        )

        return {
            "status": "success",
            "items": paginated_items,
            "pagination": {
                "total": total_items,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_items,
            },
            "filters_applied": {"item_type": item_type, "category": category},
        }

    except Exception as e:
        logger.error("Failed to list shop items for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to browse shop items: {str(e)}")


@authenticated_tool(
    name="get_item_details",
    description="Get detailed information about a specific shop item",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_item_details_tool(item_id: str, item_type: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific shop item including pricing and availability.

    Args:
        item_id: The ID of the item to get details for
        item_type: The type of item (theme, avatar, banner, bundle)

    Returns:
        Dictionary containing detailed item information

    Raises:
        MCPValidationError: If item not found or invalid parameters
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if not item_id or not item_type:
        raise MCPValidationError("Both item_id and item_type are required")

    valid_types = ["theme", "avatar", "banner", "bundle"]
    if item_type not in valid_types:
        raise MCPValidationError(f"Invalid item_type. Must be one of: {valid_types}")

    try:
        # Get item details from existing shop registry
        item_details = await get_item_details(item_id, item_type)

        if not item_details:
            raise MCPValidationError(f"Item not found: {item_id}")

        # Enhance with additional metadata
        enhanced_details = dict(item_details)

        # Add bundle contents if it's a bundle
        if item_type == "bundle" and item_id in BUNDLE_CONTENTS:
            enhanced_details["bundle_contents"] = BUNDLE_CONTENTS[item_id]
            enhanced_details["bundle_item_count"] = sum(len(items) for items in BUNDLE_CONTENTS[item_id].values())

        # Check if user already owns this item
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one(
            {"username": user_context.username}, {f"{item_type}s_owned": 1, "bundles_owned": 1}
        )

        already_owned = False
        if user:
            owned_items = user.get(f"{item_type}s_owned", [])
            if item_type == "bundle":
                already_owned = item_id in user.get("bundles_owned", [])
            else:
                id_key = f"{item_type}_id"
                already_owned = any(owned.get(id_key) == item_id for owned in owned_items)

        enhanced_details["already_owned"] = already_owned
        enhanced_details["available_for_purchase"] = not already_owned

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_item_details",
            resource_type="shop_item",
            resource_id=item_id,
            metadata={"item_type": item_type, "already_owned": already_owned},
            user_context=user_context,
        )

        logger.info(
            "User %s viewed item details: %s (%s), owned=%s", user_context.username, item_id, item_type, already_owned
        )

        return {"status": "success", "item": enhanced_details}

    except MCPValidationError:
        raise
    except Exception as e:
        logger.error("Failed to get item details for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get item details: {str(e)}")


@authenticated_tool(
    name="search_shop_items",
    description="Search shop items with advanced filtering capabilities",
    permissions=["shop:read"],
    rate_limit_action="shop_search",
)
async def search_shop_items(
    query: Optional[str] = None,
    item_type: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    featured_only: bool = False,
    new_arrivals_only: bool = False,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Search shop items with advanced filtering and text search capabilities.

    Args:
        query: Text search query for item names and descriptions
        item_type: Filter by item type (theme, avatar, banner, bundle)
        category: Filter by category
        min_price: Minimum price filter
        max_price: Maximum price filter
        featured_only: Show only featured items
        new_arrivals_only: Show only new arrivals
        limit: Maximum number of results to return

    Returns:
        Dictionary containing search results and applied filters
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if limit > 50:
        limit = 50
    if limit < 1:
        limit = 1

    try:
        # Get all items first (reuse list_shop_items logic)
        all_items_result = await list_shop_items(item_type=item_type, category=category, limit=1000)
        all_items = all_items_result["items"]

        # Apply search filters
        filtered_items = all_items

        # Text search
        if query:
            query_lower = query.lower()
            filtered_items = [
                item
                for item in filtered_items
                if query_lower in item.get("name", "").lower() or query_lower in item.get("description", "").lower()
            ]

        # Price filters
        if min_price is not None:
            filtered_items = [item for item in filtered_items if item.get("price", 0) >= min_price]

        if max_price is not None:
            filtered_items = [item for item in filtered_items if item.get("price", 0) <= max_price]

        # Feature filters
        if featured_only:
            filtered_items = [item for item in filtered_items if item.get("featured", False)]

        if new_arrivals_only:
            filtered_items = [item for item in filtered_items if item.get("new_arrival", False)]

        # Apply limit
        result_items = filtered_items[:limit]

        # Create audit trail
        await create_mcp_audit_trail(
            operation="search_shop_items",
            resource_type="shop",
            resource_id="search",
            metadata={
                "query": query,
                "filters": {
                    "item_type": item_type,
                    "category": category,
                    "min_price": min_price,
                    "max_price": max_price,
                    "featured_only": featured_only,
                    "new_arrivals_only": new_arrivals_only,
                },
                "results_count": len(result_items),
                "total_matches": len(filtered_items),
            },
            user_context=user_context,
        )

        logger.info(
            "User %s searched shop items: query='%s', found=%d/%d",
            user_context.username,
            query or "",
            len(result_items),
            len(filtered_items),
        )

        return {
            "status": "success",
            "items": result_items,
            "search_info": {
                "query": query,
                "total_matches": len(filtered_items),
                "returned_count": len(result_items),
                "filters_applied": {
                    "item_type": item_type,
                    "category": category,
                    "price_range": [min_price, max_price] if min_price or max_price else None,
                    "featured_only": featured_only,
                    "new_arrivals_only": new_arrivals_only,
                },
            },
        }

    except Exception as e:
        logger.error("Failed to search shop items for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to search shop items: {str(e)}")


@authenticated_tool(
    name="get_shop_categories",
    description="Get available shop categories for browsing",
    permissions=["shop:read"],
    rate_limit_action="shop_browse",
)
async def get_shop_categories() -> Dict[str, Any]:
    """
    Get all available shop categories organized by item type.

    Returns:
        Dictionary containing categories organized by item type
    """
    user_context = get_mcp_user_context()

    try:
        # Define available categories based on existing shop structure
        categories = {
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

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_shop_categories",
            user_context=user_context,
            resource_type="shop",
            resource_id="categories",
            metadata={"categories_count": sum(len(cats) for cats in categories.values())},
        )

        logger.info("User %s retrieved shop categories", user_context.username)

        return {"status": "success", "categories": categories, "item_types": list(categories.keys())}

    except Exception as e:
        logger.error("Failed to get shop categories for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get shop categories: {str(e)}")


@authenticated_tool(
    name="get_featured_items",
    description="Get currently featured shop items",
    permissions=["shop:read"],
    rate_limit_action="shop_browse",
)
async def get_featured_items(limit: int = 10) -> Dict[str, Any]:
    """
    Get currently featured shop items across all categories.

    Args:
        limit: Maximum number of featured items to return

    Returns:
        Dictionary containing featured items
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if limit > 20:
        limit = 20
    if limit < 1:
        limit = 1

    try:
        # Use search with featured_only filter
        featured_result = await search_shop_items(featured_only=True, limit=limit)

        featured_items = featured_result["items"]

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_featured_items",
            user_context=user_context,
            resource_type="shop",
            resource_id="featured",
            metadata={"featured_count": len(featured_items)},
        )

        logger.info("User %s retrieved %d featured items", user_context.username, len(featured_items))

        return {"status": "success", "featured_items": featured_items, "count": len(featured_items)}

    except Exception as e:
        logger.error("Failed to get featured items for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get featured items: {str(e)}")


@authenticated_tool(
    name="get_new_arrivals",
    description="Get recently added shop items",
    permissions=["shop:read"],
    rate_limit_action="shop_browse",
)
async def get_new_arrivals(limit: int = 10) -> Dict[str, Any]:
    """
    Get recently added shop items marked as new arrivals.

    Args:
        limit: Maximum number of new arrivals to return

    Returns:
        Dictionary containing new arrival items
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if limit > 20:
        limit = 20
    if limit < 1:
        limit = 1

    try:
        # Use search with new_arrivals_only filter
        new_arrivals_result = await search_shop_items(new_arrivals_only=True, limit=limit)

        new_items = new_arrivals_result["items"]

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_new_arrivals",
            user_context=user_context,
            resource_type="shop",
            resource_id="new_arrivals",
            metadata={"new_arrivals_count": len(new_items)},
        )

        logger.info("User %s retrieved %d new arrival items", user_context.username, len(new_items))

        return {"status": "success", "new_arrivals": new_items, "count": len(new_items)}

    except Exception as e:
        logger.error("Failed to get new arrivals for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get new arrivals: {str(e)}")


# Purchase and Transaction Tools (Task 6.2)


@authenticated_tool(
    name="purchase_item",
    description="Purchase a shop item with SBD tokens",
    permissions=["shop:purchase"],
    rate_limit_action="shop_purchase",
)
async def purchase_item(
    item_id: str, item_type: str, payment_method: str = "personal", family_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Purchase a shop item using SBD tokens from personal or family account.

    Args:
        item_id: The ID of the item to purchase
        item_type: The type of item (theme, avatar, banner, bundle)
        payment_method: Payment method ("personal" or "family")
        family_id: Family ID if using family tokens

    Returns:
        Dictionary containing purchase confirmation and transaction details

    Raises:
        MCPValidationError: If item not found or invalid parameters
        MCPAuthorizationError: If insufficient funds or permissions
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if not item_id or not item_type:
        raise MCPValidationError("Both item_id and item_type are required")

    valid_types = ["theme", "avatar", "banner", "bundle"]
    if item_type not in valid_types:
        raise MCPValidationError(f"Invalid item_type. Must be one of: {valid_types}")

    valid_payment_methods = ["personal", "family"]
    if payment_method not in valid_payment_methods:
        raise MCPValidationError(f"Invalid payment_method. Must be one of: {valid_payment_methods}")

    if payment_method == "family" and not family_id:
        raise MCPValidationError("family_id is required when using family payment method")

    try:
        # Get item details and validate existence
        item_details = await get_item_details(item_id, item_type)
        if not item_details:
            raise MCPValidationError(f"Item not found: {item_id}")

        price = item_details["price"]

        # Check if user already owns this item
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one(
            {"username": user_context.username}, {f"{item_type}s_owned": 1, "bundles_owned": 1, "sbd_tokens": 1}
        )

        if not user:
            raise MCPValidationError("User not found")

        # Check ownership
        already_owned = False
        if item_type == "bundle":
            already_owned = item_id in user.get("bundles_owned", [])
        else:
            owned_items = user.get(f"{item_type}s_owned", [])
            id_key = f"{item_type}_id"
            already_owned = any(owned.get(id_key) == item_id for owned in owned_items)

        if already_owned:
            raise MCPValidationError(f"{item_type.title()} already owned")

        # Validate payment method and process purchase
        from uuid import uuid4

        from ....routes.shop.routes import PaymentMethod, process_payment, validate_payment_method

        payment_obj = PaymentMethod(type=payment_method, family_id=family_id)

        # Validate payment method and check balance
        payment_details = await validate_payment_method(payment_obj, user_context.user_id, user_context.username, price)

        # Prepare transaction data
        now_iso = datetime.now().isoformat()
        transaction_id = str(uuid4())

        # Create current_user dict for process_payment
        current_user = {"_id": user_context.user_id, "username": user_context.username}

        # Process payment
        payment_result = await process_payment(payment_details, price, item_details, current_user, transaction_id)

        # Add item to user's owned collection
        item_entry = {
            f"{item_type}_id": item_id,
            "unlocked_at": now_iso,
            "permanent": True,
            "source": "purchase",
            "transaction_id": transaction_id,
            "note": "Bought from shop via MCP",
            "price": price,
        }

        # Determine target account for storage
        target_username = user_context.username
        if payment_result.get("payment_type") == "family":
            target_username = payment_result.get("from_account")
            item_entry.update(
                {
                    "purchased_by_user_id": user_context.user_id,
                    "purchased_by_username": user_context.username,
                    "family_transaction_id": transaction_id,
                }
            )

        # Update user's owned items
        if item_type == "bundle":
            update_result = await users_collection.update_one(
                {"username": target_username}, {"$push": {"bundles_owned": item_id}}, upsert=True
            )
        else:
            update_result = await users_collection.update_one(
                {"username": target_username}, {"$push": {f"{item_type}s_owned": item_entry}}, upsert=True
            )

        if update_result.modified_count == 0:
            raise MCPToolError(f"Failed to add {item_type} to user account")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="purchase_item",
            resource_type="shop_item",
            resource_id=item_id,
            metadata={
                "item_type": item_type,
                "price": price,
                "payment_method": payment_method,
                "family_id": family_id,
                "transaction_id": transaction_id,
            },
            user_context=user_context,
        )

        logger.info(
            "User %s purchased %s %s for %d tokens via %s payment (txn: %s)",
            user_context.username,
            item_type,
            item_id,
            price,
            payment_method,
            transaction_id,
        )

        return {
            "status": "success",
            "purchase": {
                "item_id": item_id,
                "item_type": item_type,
                "item_name": item_details.get("name", "Unknown Item"),
                "price": price,
                "transaction_id": transaction_id,
                "purchased_at": now_iso,
                "payment_method": payment_method,
                "target_account": target_username,
            },
            "payment": payment_result,
        }

    except MCPValidationError:
        raise
    except Exception as e:
        logger.error("Failed to purchase item for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to purchase item: {str(e)}")


@authenticated_tool(
    name="get_purchase_history",
    description="Get user's purchase history from shop transactions",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_purchase_history(limit: int = 20, offset: int = 0, item_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get user's purchase history including all shop transactions.

    Args:
        limit: Maximum number of transactions to return
        offset: Number of transactions to skip for pagination
        item_type: Filter by item type (theme, avatar, banner, bundle)

    Returns:
        Dictionary containing purchase history and pagination info
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0

    try:
        users_collection = db_manager.get_collection("users")

        # Get user's SBD token transactions
        user = await users_collection.find_one({"username": user_context.username}, {"sbd_tokens_transactions": 1})

        if not user:
            raise MCPValidationError("User not found")

        all_transactions = user.get("sbd_tokens_transactions", [])

        # Filter for shop purchases (transactions to emotion_tracker_shop)
        shop_transactions = []
        for txn in all_transactions:
            if (
                txn.get("type") == "send"
                and txn.get("to") == "emotion_tracker_shop"
                and "shop" in txn.get("note", "").lower()
            ):

                # Extract item information from transaction
                transaction_data = {
                    "transaction_id": txn.get("transaction_id"),
                    "amount": txn.get("amount"),
                    "timestamp": txn.get("timestamp"),
                    "note": txn.get("note"),
                    "item_type": txn.get("shop_item_type", "unknown"),
                    "item_id": txn.get("shop_item_id", "unknown"),
                    "payment_type": "family" if txn.get("family_member_id") else "personal",
                }

                # Add family information if it's a family transaction
                if txn.get("family_member_id"):
                    transaction_data.update(
                        {
                            "family_member_id": txn.get("family_member_id"),
                            "family_member_username": txn.get("family_member_username"),
                        }
                    )

                shop_transactions.append(transaction_data)

        # Sort by timestamp (most recent first)
        shop_transactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Apply item type filter if specified
        if item_type:
            shop_transactions = [txn for txn in shop_transactions if txn.get("item_type") == item_type]

        # Apply pagination
        total_transactions = len(shop_transactions)
        paginated_transactions = shop_transactions[offset : offset + limit]

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_purchase_history",
            user_context=user_context,
            resource_type="shop",
            resource_id="purchase_history",
            metadata={"limit": limit, "offset": offset, "item_type": item_type, "total_found": total_transactions},
        )

        logger.info(
            "User %s retrieved purchase history: %d transactions found", user_context.username, total_transactions
        )

        return {
            "status": "success",
            "transactions": paginated_transactions,
            "pagination": {
                "total": total_transactions,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_transactions,
            },
            "filters_applied": {"item_type": item_type},
        }

    except Exception as e:
        logger.error("Failed to get purchase history for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get purchase history: {str(e)}")


@authenticated_tool(
    name="get_transaction_details",
    description="Get detailed information about a specific transaction",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_transaction_details(transaction_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific shop transaction.

    Args:
        transaction_id: The ID of the transaction to get details for

    Returns:
        Dictionary containing detailed transaction information

    Raises:
        MCPValidationError: If transaction not found
    """
    user_context = get_mcp_user_context()

    if not transaction_id:
        raise MCPValidationError("transaction_id is required")

    try:
        users_collection = db_manager.get_collection("users")

        # Get user's transactions
        user = await users_collection.find_one({"username": user_context.username}, {"sbd_tokens_transactions": 1})

        if not user:
            raise MCPValidationError("User not found")

        # Find the specific transaction
        transaction = None
        for txn in user.get("sbd_tokens_transactions", []):
            if txn.get("transaction_id") == transaction_id:
                transaction = txn
                break

        if not transaction:
            raise MCPValidationError(f"Transaction not found: {transaction_id}")

        # Enhance transaction with additional details
        enhanced_transaction = dict(transaction)

        # Add item details if it's a shop transaction
        if transaction.get("type") == "send" and transaction.get("to") == "emotion_tracker_shop":

            item_type = transaction.get("shop_item_type")
            item_id = transaction.get("shop_item_id")

            if item_type and item_id:
                try:
                    item_details = await get_item_details(item_id, item_type)
                    if item_details:
                        enhanced_transaction["item_details"] = item_details
                except Exception as e:
                    logger.warning("Failed to get item details for transaction %s: %s", transaction_id, e)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_transaction_details",
            resource_type="transaction",
            resource_id=transaction_id,
            metadata={"transaction_type": transaction.get("type")},
            user_context=user_context,
        )

        logger.info("User %s retrieved transaction details: %s", user_context.username, transaction_id)

        return {"status": "success", "transaction": enhanced_transaction}

    except MCPValidationError:
        raise
    except Exception as e:
        logger.error("Failed to get transaction details for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get transaction details: {str(e)}")


@authenticated_tool(
    name="validate_purchase",
    description="Validate if a purchase can be made before attempting it",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def validate_purchase(
    item_id: str, item_type: str, payment_method: str = "personal", family_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate if a purchase can be made without actually processing it.

    Args:
        item_id: The ID of the item to validate
        item_type: The type of item (theme, avatar, banner, bundle)
        payment_method: Payment method ("personal" or "family")
        family_id: Family ID if using family tokens

    Returns:
        Dictionary containing validation results and any issues
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if not item_id or not item_type:
        raise MCPValidationError("Both item_id and item_type are required")

    valid_types = ["theme", "avatar", "banner", "bundle"]
    if item_type not in valid_types:
        raise MCPValidationError(f"Invalid item_type. Must be one of: {valid_types}")

    valid_payment_methods = ["personal", "family"]
    if payment_method not in valid_payment_methods:
        raise MCPValidationError(f"Invalid payment_method. Must be one of: {valid_payment_methods}")

    try:
        validation_results = {"can_purchase": True, "issues": [], "warnings": []}

        # Check if item exists
        item_details = await get_item_details(item_id, item_type)
        if not item_details:
            validation_results["can_purchase"] = False
            validation_results["issues"].append(f"Item not found: {item_id}")
            return {"status": "success", "validation": validation_results}

        price = item_details["price"]
        validation_results["item_details"] = item_details

        # Check if user already owns this item
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one(
            {"username": user_context.username}, {f"{item_type}s_owned": 1, "bundles_owned": 1, "sbd_tokens": 1}
        )

        if not user:
            validation_results["can_purchase"] = False
            validation_results["issues"].append("User not found")
            return {"status": "success", "validation": validation_results}

        # Check ownership
        already_owned = False
        if item_type == "bundle":
            already_owned = item_id in user.get("bundles_owned", [])
        else:
            owned_items = user.get(f"{item_type}s_owned", [])
            id_key = f"{item_type}_id"
            already_owned = any(owned.get(id_key) == item_id for owned in owned_items)

        if already_owned:
            validation_results["can_purchase"] = False
            validation_results["issues"].append(f"{item_type.title()} already owned")

        # Validate payment method
        try:
            from ....routes.shop.routes import PaymentMethod, validate_payment_method

            payment_obj = PaymentMethod(type=payment_method, family_id=family_id)
            payment_details = await validate_payment_method(
                payment_obj, user_context.user_id, user_context.username, price
            )

            validation_results["payment_details"] = {
                "payment_type": payment_details["payment_type"],
                "account_username": payment_details["account_username"],
                "balance": payment_details["balance"],
                "sufficient_funds": payment_details["balance"] >= price,
            }

            if payment_details["balance"] < price:
                validation_results["can_purchase"] = False
                validation_results["issues"].append(
                    f"Insufficient funds. Required: {price}, Available: {payment_details['balance']}"
                )

        except Exception as e:
            validation_results["can_purchase"] = False
            validation_results["issues"].append(f"Payment validation failed: {str(e)}")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="validate_purchase",
            resource_type="shop_item",
            resource_id=item_id,
            metadata={
                "item_type": item_type,
                "payment_method": payment_method,
                "can_purchase": validation_results["can_purchase"],
                "issues_count": len(validation_results["issues"]),
            },
            user_context=user_context,
        )

        logger.info(
            "User %s validated purchase for %s %s: can_purchase=%s",
            user_context.username,
            item_type,
            item_id,
            validation_results["can_purchase"],
        )

        return {"status": "success", "validation": validation_results}

    except MCPValidationError:
        raise
    except Exception as e:
        logger.error("Failed to validate purchase for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to validate purchase: {str(e)}")


@authenticated_tool(
    name="get_spending_summary",
    description="Get user's spending summary and financial overview",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_spending_summary(days: int = 30, include_family: bool = True) -> Dict[str, Any]:
    """
    Get user's spending summary and financial overview for shop purchases.

    Args:
        days: Number of days to include in summary (default: 30)
        include_family: Whether to include family spending data

    Returns:
        Dictionary containing spending summary and analytics
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if days < 1:
        days = 1
    if days > 365:
        days = 365

    try:
        users_collection = db_manager.get_collection("users")

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_date_iso = start_date.isoformat()

        # Get user's transactions
        user = await users_collection.find_one(
            {"username": user_context.username}, {"sbd_tokens_transactions": 1, "sbd_tokens": 1}
        )

        if not user:
            raise MCPValidationError("User not found")

        current_balance = user.get("sbd_tokens", 0)
        all_transactions = user.get("sbd_tokens_transactions", [])

        # Filter transactions within date range
        recent_transactions = [txn for txn in all_transactions if txn.get("timestamp", "") >= start_date_iso]

        # Analyze shop spending
        shop_spending = {
            "total_spent": 0,
            "transaction_count": 0,
            "items_purchased": 0,
            "by_item_type": {},
            "by_payment_method": {"personal": 0, "family": 0},
            "transactions": [],
        }

        for txn in recent_transactions:
            if txn.get("type") == "send" and txn.get("to") == "emotion_tracker_shop":

                amount = txn.get("amount", 0)
                shop_spending["total_spent"] += amount
                shop_spending["transaction_count"] += 1
                shop_spending["items_purchased"] += 1

                # Categorize by item type
                item_type = txn.get("shop_item_type", "unknown")
                shop_spending["by_item_type"][item_type] = shop_spending["by_item_type"].get(item_type, 0) + amount

                # Categorize by payment method
                payment_method = "family" if txn.get("family_member_id") else "personal"
                shop_spending["by_payment_method"][payment_method] += amount

                shop_spending["transactions"].append(
                    {
                        "transaction_id": txn.get("transaction_id"),
                        "amount": amount,
                        "timestamp": txn.get("timestamp"),
                        "item_type": item_type,
                        "item_id": txn.get("shop_item_id"),
                        "payment_method": payment_method,
                    }
                )

        # Calculate other spending (non-shop transactions)
        other_spending = 0
        for txn in recent_transactions:
            if txn.get("type") == "send" and txn.get("to") != "emotion_tracker_shop":
                other_spending += txn.get("amount", 0)

        # Get family spending data if requested
        family_spending_data = {}
        if include_family:
            try:
                from ....managers.family_manager import family_manager

                user_families = await family_manager.get_user_families(user_context.user_id)

                for family in user_families:
                    family_id = family["family_id"]
                    try:
                        # Get family SBD account
                        sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)

                        family_spending_data[family_id] = {
                            "family_name": family["name"],
                            "balance": sbd_account["balance"],
                            "can_spend": sbd_account["spending_permissions"]
                            .get(user_context.user_id, {})
                            .get("can_spend", False),
                            "spending_limit": sbd_account["spending_permissions"]
                            .get(user_context.user_id, {})
                            .get("spending_limit", 0),
                        }
                    except Exception as e:
                        logger.warning("Failed to get family spending data for %s: %s", family_id, e)
                        continue
            except Exception as e:
                logger.warning("Failed to get family spending data: %s", e)

        # Create summary
        summary = {
            "period": {"days": days, "start_date": start_date_iso, "end_date": end_date.isoformat()},
            "current_balance": current_balance,
            "shop_spending": shop_spending,
            "other_spending": other_spending,
            "total_spending": shop_spending["total_spent"] + other_spending,
            "family_accounts": family_spending_data if include_family else {},
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_spending_summary",
            user_context=user_context,
            resource_type="shop",
            resource_id="spending_summary",
            metadata={
                "days": days,
                "include_family": include_family,
                "total_spent": shop_spending["total_spent"],
                "transaction_count": shop_spending["transaction_count"],
            },
        )

        logger.info(
            "User %s retrieved spending summary: %d days, %d shop transactions, %d total spent",
            user_context.username,
            days,
            shop_spending["transaction_count"],
            shop_spending["total_spent"],
        )

        return {"status": "success", "summary": summary}

    except Exception as e:
        logger.error("Failed to get spending summary for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get spending summary: {str(e)}")


# Asset Management Tools (Task 6.3)


@authenticated_tool(
    name="get_user_assets",
    description="Get all assets owned or rented by the user",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_user_assets(
    asset_type: Optional[str] = None, include_rented: bool = True, include_owned: bool = True
) -> Dict[str, Any]:
    """
    Get all assets owned or rented by the user across all categories.

    Args:
        asset_type: Filter by asset type (theme, avatar, banner, bundle)
        include_rented: Whether to include rented assets
        include_owned: Whether to include owned assets

    Returns:
        Dictionary containing user's assets organized by type
    """
    user_context = get_mcp_user_context()

    try:
        users_collection = db_manager.get_collection("users")

        # Get user's asset data
        user = await users_collection.find_one(
            {"username": user_context.username},
            {
                "themes_owned": 1,
                "avatars_owned": 1,
                "banners_owned": 1,
                "bundles_owned": 1,
                "themes_rented": 1,
                "avatars_rented": 1,
                "banners_rented": 1,
            },
        )

        if not user:
            raise MCPValidationError("User not found")

        assets = {"owned": {}, "rented": {}, "summary": {"total_owned": 0, "total_rented": 0, "by_type": {}}}

        # Process owned assets
        if include_owned:
            asset_types = ["theme", "avatar", "banner", "bundle"]
            for atype in asset_types:
                if asset_type and atype != asset_type:
                    continue

                if atype == "bundle":
                    # Bundles are stored as simple list of IDs
                    owned_bundles = user.get("bundles_owned", [])
                    assets["owned"][atype] = []

                    for bundle_id in owned_bundles:
                        try:
                            bundle_details = await get_item_details(bundle_id, "bundle")
                            if bundle_details:
                                assets["owned"][atype].append(
                                    {
                                        "asset_id": bundle_id,
                                        "asset_type": atype,
                                        "name": bundle_details.get("name", "Unknown Bundle"),
                                        "owned": True,
                                        "rented": False,
                                        "acquired_at": "unknown",  # Bundles don't have timestamp
                                        "source": "purchase",
                                        "price_paid": bundle_details.get("price", 0),
                                    }
                                )
                        except Exception as e:
                            logger.warning("Failed to get bundle details for %s: %s", bundle_id, e)
                            continue
                else:
                    # Other assets are stored as objects with metadata
                    owned_items = user.get(f"{atype}s_owned", [])
                    assets["owned"][atype] = []

                    for item in owned_items:
                        asset_id = item.get(f"{atype}_id")
                        if asset_id:
                            try:
                                item_details = await get_item_details(asset_id, atype)
                                asset_info = {
                                    "asset_id": asset_id,
                                    "asset_type": atype,
                                    "name": (
                                        item_details.get("name", "Unknown Item") if item_details else "Unknown Item"
                                    ),
                                    "owned": True,
                                    "rented": False,
                                    "acquired_at": item.get("unlocked_at", "unknown"),
                                    "source": item.get("source", "unknown"),
                                    "price_paid": item.get("price", 0),
                                    "transaction_id": item.get("transaction_id"),
                                    "permanent": item.get("permanent", True),
                                }

                                # Add family purchase info if available
                                if item.get("purchased_by_username"):
                                    asset_info["purchased_by"] = item.get("purchased_by_username")
                                    asset_info["family_purchase"] = True

                                assets["owned"][atype].append(asset_info)
                            except Exception as e:
                                logger.warning("Failed to get item details for %s: %s", asset_id, e)
                                continue

                assets["summary"]["total_owned"] += len(assets["owned"].get(atype, []))
                assets["summary"]["by_type"][f"{atype}_owned"] = len(assets["owned"].get(atype, []))

        # Process rented assets
        if include_rented:
            rental_types = ["theme", "avatar", "banner"]  # Bundles can't be rented
            for atype in rental_types:
                if asset_type and atype != asset_type:
                    continue

                rented_items = user.get(f"{atype}s_rented", [])
                assets["rented"][atype] = []

                for item in rented_items:
                    asset_id = item.get(f"{atype}_id")
                    if asset_id:
                        # Check if rental is still active
                        rental_expires = item.get("rental_expires")
                        is_active = True
                        if rental_expires:
                            try:
                                expires_dt = datetime.fromisoformat(rental_expires.replace("Z", "+00:00"))
                                is_active = expires_dt > datetime.now(timezone.utc)
                            except Exception:
                                is_active = False

                        try:
                            item_details = await get_item_details(asset_id, atype)
                            asset_info = {
                                "asset_id": asset_id,
                                "asset_type": atype,
                                "name": item_details.get("name", "Unknown Item") if item_details else "Unknown Item",
                                "owned": False,
                                "rented": True,
                                "rental_active": is_active,
                                "rental_expires": rental_expires,
                                "acquired_at": item.get("rented_at", "unknown"),
                                "source": "rental",
                                "price_paid": item.get("rental_cost", 0),
                                "rental_duration": item.get("rental_duration_days", 0),
                            }

                            assets["rented"][atype].append(asset_info)
                        except Exception as e:
                            logger.warning("Failed to get rented item details for %s: %s", asset_id, e)
                            continue

                assets["summary"]["total_rented"] += len(assets["rented"].get(atype, []))
                assets["summary"]["by_type"][f"{atype}_rented"] = len(assets["rented"].get(atype, []))

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_assets",
            resource_type="user_assets",
            resource_id=user_context.username,
            metadata={
                "asset_type": asset_type,
                "include_rented": include_rented,
                "include_owned": include_owned,
                "total_owned": assets["summary"]["total_owned"],
                "total_rented": assets["summary"]["total_rented"],
            },
            user_context=user_context,
        )

        logger.info(
            "User %s retrieved assets: %d owned, %d rented",
            user_context.username,
            assets["summary"]["total_owned"],
            assets["summary"]["total_rented"],
        )

        return {"status": "success", "assets": assets}

    except Exception as e:
        logger.error("Failed to get user assets for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get user assets: {str(e)}")


@authenticated_tool(
    name="get_owned_avatars",
    description="Get all avatars owned by the user",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_owned_avatars() -> Dict[str, Any]:
    """
    Get all avatars owned by the user with detailed information.

    Returns:
        Dictionary containing owned avatars
    """
    user_context = get_mcp_user_context()

    try:
        # Use the general asset function with avatar filter
        assets_result = await get_user_assets(asset_type="avatar", include_rented=False, include_owned=True)

        owned_avatars = assets_result["assets"]["owned"].get("avatar", [])

        return {"status": "success", "avatars": owned_avatars, "count": len(owned_avatars)}

    except Exception as e:
        logger.error("Failed to get owned avatars for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get owned avatars: {str(e)}")


@authenticated_tool(
    name="get_rented_avatars",
    description="Get all avatars currently rented by the user",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_rented_avatars() -> Dict[str, Any]:
    """
    Get all avatars currently rented by the user with rental information.

    Returns:
        Dictionary containing rented avatars
    """
    user_context = get_mcp_user_context()

    try:
        # Use the general asset function with avatar filter
        assets_result = await get_user_assets(asset_type="avatar", include_rented=True, include_owned=False)

        rented_avatars = assets_result["assets"]["rented"].get("avatar", [])

        # Filter only active rentals
        active_rentals = [avatar for avatar in rented_avatars if avatar.get("rental_active", False)]

        return {
            "status": "success",
            "avatars": active_rentals,
            "count": len(active_rentals),
            "total_rentals": len(rented_avatars),
        }

    except Exception as e:
        logger.error("Failed to get rented avatars for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get rented avatars: {str(e)}")


@authenticated_tool(
    name="get_owned_banners",
    description="Get all banners owned by the user",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_owned_banners() -> Dict[str, Any]:
    """
    Get all banners owned by the user with detailed information.

    Returns:
        Dictionary containing owned banners
    """
    user_context = get_mcp_user_context()

    try:
        # Use the general asset function with banner filter
        assets_result = await get_user_assets(asset_type="banner", include_rented=False, include_owned=True)

        owned_banners = assets_result["assets"]["owned"].get("banner", [])

        return {"status": "success", "banners": owned_banners, "count": len(owned_banners)}

    except Exception as e:
        logger.error("Failed to get owned banners for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get owned banners: {str(e)}")


@authenticated_tool(
    name="get_rented_banners",
    description="Get all banners currently rented by the user",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_rented_banners() -> Dict[str, Any]:
    """
    Get all banners currently rented by the user with rental information.

    Returns:
        Dictionary containing rented banners
    """
    user_context = get_mcp_user_context()

    try:
        # Use the general asset function with banner filter
        assets_result = await get_user_assets(asset_type="banner", include_rented=True, include_owned=False)

        rented_banners = assets_result["assets"]["rented"].get("banner", [])

        # Filter only active rentals
        active_rentals = [banner for banner in rented_banners if banner.get("rental_active", False)]

        return {
            "status": "success",
            "banners": active_rentals,
            "count": len(active_rentals),
            "total_rentals": len(rented_banners),
        }

    except Exception as e:
        logger.error("Failed to get rented banners for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get rented banners: {str(e)}")


@authenticated_tool(
    name="get_owned_themes",
    description="Get all themes owned by the user",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_owned_themes() -> Dict[str, Any]:
    """
    Get all themes owned by the user with detailed information.

    Returns:
        Dictionary containing owned themes
    """
    user_context = get_mcp_user_context()

    try:
        # Use the general asset function with theme filter
        assets_result = await get_user_assets(asset_type="theme", include_rented=False, include_owned=True)

        owned_themes = assets_result["assets"]["owned"].get("theme", [])

        return {"status": "success", "themes": owned_themes, "count": len(owned_themes)}

    except Exception as e:
        logger.error("Failed to get owned themes for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get owned themes: {str(e)}")


@authenticated_tool(
    name="get_rented_themes",
    description="Get all themes currently rented by the user",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_rented_themes() -> Dict[str, Any]:
    """
    Get all themes currently rented by the user with rental information.

    Returns:
        Dictionary containing rented themes
    """
    user_context = get_mcp_user_context()

    try:
        # Use the general asset function with theme filter
        assets_result = await get_user_assets(asset_type="theme", include_rented=True, include_owned=False)

        rented_themes = assets_result["assets"]["rented"].get("theme", [])

        # Filter only active rentals
        active_rentals = [theme for theme in rented_themes if theme.get("rental_active", False)]

        return {
            "status": "success",
            "themes": active_rentals,
            "count": len(active_rentals),
            "total_rentals": len(rented_themes),
        }

    except Exception as e:
        logger.error("Failed to get rented themes for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get rented themes: {str(e)}")


@authenticated_tool(
    name="get_asset_usage_history",
    description="Get usage history for user's assets",
    permissions=["shop:read"],
    rate_limit_action="shop_read",
)
async def get_asset_usage_history(asset_type: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
    """
    Get usage history and analytics for user's assets.

    Args:
        asset_type: Filter by asset type (theme, avatar, banner)
        days: Number of days to include in history

    Returns:
        Dictionary containing asset usage history and analytics
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if days < 1:
        days = 1
    if days > 365:
        days = 365

    try:
        # Get user's assets first
        assets_result = await get_user_assets(asset_type=asset_type, include_rented=True, include_owned=True)

        # Calculate usage analytics
        usage_history = {
            "period": {
                "days": days,
                "start_date": (datetime.now() - timedelta(days=days)).isoformat(),
                "end_date": datetime.now().isoformat(),
            },
            "summary": {
                "total_assets": 0,
                "owned_assets": 0,
                "rented_assets": 0,
                "active_rentals": 0,
                "expired_rentals": 0,
            },
            "by_type": {},
            "recent_acquisitions": [],
            "expiring_rentals": [],
        }

        # Process owned assets
        for asset_type_key, assets in assets_result["assets"]["owned"].items():
            usage_history["summary"]["total_assets"] += len(assets)
            usage_history["summary"]["owned_assets"] += len(assets)

            usage_history["by_type"][asset_type_key] = {"owned": len(assets), "rented": 0, "total": len(assets)}

            # Find recent acquisitions
            for asset in assets:
                acquired_at = asset.get("acquired_at")
                if acquired_at and acquired_at != "unknown":
                    try:
                        acquired_dt = datetime.fromisoformat(acquired_at.replace("Z", "+00:00"))
                        if acquired_dt > datetime.now(timezone.utc) - timedelta(days=days):
                            usage_history["recent_acquisitions"].append(
                                {
                                    "asset_id": asset["asset_id"],
                                    "asset_type": asset["asset_type"],
                                    "name": asset["name"],
                                    "acquired_at": acquired_at,
                                    "source": asset["source"],
                                    "price_paid": asset.get("price_paid", 0),
                                }
                            )
                    except Exception:
                        continue

        # Process rented assets
        for asset_type_key, assets in assets_result["assets"]["rented"].items():
            usage_history["summary"]["total_assets"] += len(assets)
            usage_history["summary"]["rented_assets"] += len(assets)

            if asset_type_key not in usage_history["by_type"]:
                usage_history["by_type"][asset_type_key] = {"owned": 0, "rented": 0, "total": 0}

            usage_history["by_type"][asset_type_key]["rented"] = len(assets)
            usage_history["by_type"][asset_type_key]["total"] += len(assets)

            # Analyze rental status
            for asset in assets:
                if asset.get("rental_active", False):
                    usage_history["summary"]["active_rentals"] += 1
                else:
                    usage_history["summary"]["expired_rentals"] += 1

                # Check for expiring rentals (within next 7 days)
                rental_expires = asset.get("rental_expires")
                if rental_expires:
                    try:
                        expires_dt = datetime.fromisoformat(rental_expires.replace("Z", "+00:00"))
                        days_until_expiry = (expires_dt - datetime.now(timezone.utc)).days

                        if 0 <= days_until_expiry <= 7:
                            usage_history["expiring_rentals"].append(
                                {
                                    "asset_id": asset["asset_id"],
                                    "asset_type": asset["asset_type"],
                                    "name": asset["name"],
                                    "expires_at": rental_expires,
                                    "days_remaining": days_until_expiry,
                                    "rental_active": asset.get("rental_active", False),
                                }
                            )
                    except Exception:
                        continue

        # Sort recent acquisitions by date (newest first)
        usage_history["recent_acquisitions"].sort(key=lambda x: x.get("acquired_at", ""), reverse=True)

        # Sort expiring rentals by expiry date (soonest first)
        usage_history["expiring_rentals"].sort(key=lambda x: x.get("expires_at", ""))

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_asset_usage_history",
            resource_type="user_assets",
            resource_id=user_context.username,
            metadata={
                "asset_type": asset_type,
                "days": days,
                "total_assets": usage_history["summary"]["total_assets"],
                "recent_acquisitions": len(usage_history["recent_acquisitions"]),
                "expiring_rentals": len(usage_history["expiring_rentals"]),
            },
            user_context=user_context,
        )

        logger.info(
            "User %s retrieved asset usage history: %d total assets, %d recent acquisitions",
            user_context.username,
            usage_history["summary"]["total_assets"],
            len(usage_history["recent_acquisitions"]),
        )

        return {"status": "success", "usage_history": usage_history}

    except Exception as e:
        logger.error("Failed to get asset usage history for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get asset usage history: {str(e)}")


# SBD Token Management Tools (Task 6.4)


@authenticated_tool(
    name="get_sbd_balance",
    description="Get user's current SBD token balance",
    permissions=["sbd:read"],
    rate_limit_action="sbd_read",
)
async def get_sbd_balance(include_family: bool = True) -> Dict[str, Any]:
    """
    Get user's current SBD token balance including personal and family accounts.

    Args:
        include_family: Whether to include family account balances

    Returns:
        Dictionary containing personal and family SBD token balances
    """
    user_context = get_mcp_user_context()

    try:
        users_collection = db_manager.get_collection("users")

        # Get personal balance
        user = await users_collection.find_one({"username": user_context.username}, {"sbd_tokens": 1})

        if not user:
            raise MCPValidationError("User not found")

        personal_balance = user.get("sbd_tokens", 0)

        balance_info = {
            "personal": {"balance": personal_balance, "account_username": user_context.username},
            "family_accounts": [],
        }

        # Get family balances if requested
        if include_family:
            try:
                from ....managers.family_manager import family_manager

                user_families = await family_manager.get_user_families(user_context.user_id)

                for family in user_families:
                    family_id = family["family_id"]
                    try:
                        # Get family SBD account details
                        sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)

                        # Check if user has access to view balance
                        user_permissions = sbd_account["spending_permissions"].get(user_context.user_id, {})
                        can_view = user_permissions.get("can_spend", False) or family["role"] in ["owner", "admin"]

                        if can_view:
                            balance_info["family_accounts"].append(
                                {
                                    "family_id": family_id,
                                    "family_name": family["name"],
                                    "balance": sbd_account["balance"],
                                    "account_username": sbd_account["account_username"],
                                    "can_spend": user_permissions.get("can_spend", False),
                                    "spending_limit": user_permissions.get("spending_limit", 0),
                                    "is_frozen": sbd_account["is_frozen"],
                                    "user_role": family["role"],
                                }
                            )
                    except Exception as e:
                        logger.warning("Failed to get family SBD account for %s: %s", family_id, e)
                        continue
            except Exception as e:
                logger.warning("Failed to get family balances: %s", e)

        # Calculate totals
        total_accessible = personal_balance
        for family_account in balance_info["family_accounts"]:
            if family_account["can_spend"] and not family_account["is_frozen"]:
                spending_limit = family_account["spending_limit"]
                if spending_limit == -1:  # Unlimited
                    total_accessible += family_account["balance"]
                else:
                    total_accessible += min(spending_limit, family_account["balance"])

        balance_info["summary"] = {
            "total_personal": personal_balance,
            "total_family_accounts": len(balance_info["family_accounts"]),
            "total_accessible": total_accessible,
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_sbd_balance",
            resource_type="sbd_tokens",
            resource_id=user_context.username,
            metadata={
                "include_family": include_family,
                "personal_balance": personal_balance,
                "family_accounts_count": len(balance_info["family_accounts"]),
                "total_accessible": total_accessible,
            },
            user_context=user_context,
        )

        logger.info(
            "User %s retrieved SBD balance: personal=%d, family_accounts=%d, total_accessible=%d",
            user_context.username,
            personal_balance,
            len(balance_info["family_accounts"]),
            total_accessible,
        )

        return {"status": "success", "balances": balance_info}

    except Exception as e:
        logger.error("Failed to get SBD balance for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get SBD balance: {str(e)}")


@authenticated_tool(
    name="get_sbd_transaction_history",
    description="Get user's SBD token transaction history",
    permissions=["sbd:read"],
    rate_limit_action="sbd_read",
)
async def get_sbd_transaction_history(
    limit: int = 20, offset: int = 0, transaction_type: Optional[str] = None, include_family: bool = True
) -> Dict[str, Any]:
    """
    Get user's SBD token transaction history including personal and family transactions.

    Args:
        limit: Maximum number of transactions to return
        offset: Number of transactions to skip for pagination
        transaction_type: Filter by transaction type (send, receive)
        include_family: Whether to include family account transactions

    Returns:
        Dictionary containing transaction history and pagination info
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0

    try:
        users_collection = db_manager.get_collection("users")

        # Get personal transactions
        user = await users_collection.find_one({"username": user_context.username}, {"sbd_tokens_transactions": 1})

        if not user:
            raise MCPValidationError("User not found")

        personal_transactions = user.get("sbd_tokens_transactions", [])

        # Add account source to personal transactions
        for txn in personal_transactions:
            txn["account_source"] = "personal"
            txn["account_username"] = user_context.username

        all_transactions = personal_transactions.copy()

        # Get family transactions if requested
        family_transactions = []
        if include_family:
            try:
                from ....managers.family_manager import family_manager

                user_families = await family_manager.get_user_families(user_context.user_id)

                for family in user_families:
                    family_id = family["family_id"]
                    try:
                        # Get family SBD account details
                        sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)

                        # Check if user has access to view transactions
                        user_permissions = sbd_account["spending_permissions"].get(user_context.user_id, {})
                        can_view = user_permissions.get("can_spend", False) or family["role"] in ["owner", "admin"]

                        if can_view:
                            # Get family account transactions
                            family_account = await users_collection.find_one(
                                {"username": sbd_account["account_username"]}, {"sbd_tokens_transactions": 1}
                            )

                            if family_account:
                                family_txns = family_account.get("sbd_tokens_transactions", [])

                                # Add family context to transactions
                                for txn in family_txns:
                                    enhanced_txn = dict(txn)
                                    enhanced_txn["account_source"] = "family"
                                    enhanced_txn["account_username"] = sbd_account["account_username"]
                                    enhanced_txn["family_id"] = family_id
                                    enhanced_txn["family_name"] = family["name"]

                                    # Highlight transactions by this user
                                    if txn.get("family_member_id") == user_context.user_id:
                                        enhanced_txn["initiated_by_user"] = True

                                    family_transactions.append(enhanced_txn)
                    except Exception as e:
                        logger.warning("Failed to get family transactions for %s: %s", family_id, e)
                        continue
            except Exception as e:
                logger.warning("Failed to get family transactions: %s", e)

        all_transactions.extend(family_transactions)

        # Apply transaction type filter
        if transaction_type:
            all_transactions = [txn for txn in all_transactions if txn.get("type") == transaction_type]

        # Sort by timestamp (most recent first)
        all_transactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Apply pagination
        total_transactions = len(all_transactions)
        paginated_transactions = all_transactions[offset : offset + limit]

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_sbd_transaction_history",
            resource_type="sbd_transactions",
            resource_id=user_context.username,
            metadata={
                "limit": limit,
                "offset": offset,
                "transaction_type": transaction_type,
                "include_family": include_family,
                "total_found": total_transactions,
                "personal_transactions": len(personal_transactions),
                "family_transactions": len(family_transactions),
            },
            user_context=user_context,
        )

        logger.info(
            "User %s retrieved SBD transaction history: %d total, %d personal, %d family",
            user_context.username,
            total_transactions,
            len(personal_transactions),
            len(family_transactions),
        )

        return {
            "status": "success",
            "transactions": paginated_transactions,
            "pagination": {
                "total": total_transactions,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_transactions,
            },
            "summary": {
                "personal_transactions": len(personal_transactions),
                "family_transactions": len(family_transactions),
                "total_transactions": total_transactions,
            },
            "filters_applied": {"transaction_type": transaction_type, "include_family": include_family},
        }

    except Exception as e:
        logger.error("Failed to get SBD transaction history for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get SBD transaction history: {str(e)}")


@authenticated_tool(
    name="transfer_sbd_tokens",
    description="Transfer SBD tokens to another user",
    permissions=["sbd:transfer"],
    rate_limit_action="sbd_transfer",
)
async def transfer_sbd_tokens(
    to_username: str,
    amount: int,
    note: Optional[str] = None,
    from_account: str = "personal",
    family_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transfer SBD tokens from user's account to another user.

    Args:
        to_username: Username of the recipient
        amount: Amount of tokens to transfer
        note: Optional note for the transaction
        from_account: Source account ("personal" or "family")
        family_id: Family ID if transferring from family account

    Returns:
        Dictionary containing transfer confirmation and transaction details

    Raises:
        MCPValidationError: If invalid parameters or insufficient funds
        MCPAuthorizationError: If not authorized to transfer from family account
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if not to_username or not amount:
        raise MCPValidationError("to_username and amount are required")

    if amount <= 0:
        raise MCPValidationError("Amount must be positive")

    if amount > 10000:  # Reasonable transfer limit
        raise MCPValidationError("Amount exceeds maximum transfer limit (10,000 tokens)")

    if from_account not in ["personal", "family"]:
        raise MCPValidationError("from_account must be 'personal' or 'family'")

    if from_account == "family" and not family_id:
        raise MCPValidationError("family_id is required when transferring from family account")

    if to_username == user_context.username:
        raise MCPValidationError("Cannot transfer tokens to yourself")

    try:
        users_collection = db_manager.get_collection("users")

        # Validate recipient exists
        recipient = await users_collection.find_one({"username": to_username}, {"_id": 1})

        if not recipient:
            raise MCPValidationError(f"Recipient user not found: {to_username}")

        # Prepare transfer based on account type
        if from_account == "personal":
            # Personal account transfer - use existing SBD transfer route logic
            from ....routes.sbd_tokens.routes import transfer_sbd_tokens_internal

            # Create transfer request
            transfer_result = await transfer_sbd_tokens_internal(
                from_user=user_context.username,
                to_user=to_username,
                amount=amount,
                note=note or f"Transfer via MCP from {user_context.username}",
            )

            transaction_info = {
                "from_account": "personal",
                "from_username": user_context.username,
                "to_username": to_username,
                "amount": amount,
                "note": note,
                "transaction_id": transfer_result.get("transaction_id"),
                "timestamp": datetime.now().isoformat(),
            }

        else:  # family account transfer
            from ....managers.family_manager import family_manager

            # Validate family access and spending permission
            try:
                sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)

                user_permissions = sbd_account["spending_permissions"].get(user_context.user_id, {})
                can_spend = user_permissions.get("can_spend", False)
                spending_limit = user_permissions.get("spending_limit", 0)

                if not can_spend:
                    raise MCPAuthorizationError("You don't have permission to spend from this family account")

                if sbd_account["is_frozen"]:
                    raise MCPAuthorizationError("Family account is frozen and cannot be used for transfers")

                if spending_limit != -1 and amount > spending_limit:
                    raise MCPAuthorizationError(f"Amount exceeds your spending limit of {spending_limit} tokens")

                if sbd_account["balance"] < amount:
                    raise MCPValidationError(
                        f"Insufficient family account balance. Available: {sbd_account['balance']}"
                    )

            except Exception as e:
                if isinstance(e, (MCPAuthorizationError, MCPValidationError)):
                    raise
                raise MCPToolError(f"Failed to validate family account access: {str(e)}")

            # Process family account transfer
            try:
                transfer_result = await family_manager.transfer_family_tokens(
                    family_id=family_id,
                    from_user_id=user_context.user_id,
                    to_username=to_username,
                    amount=amount,
                    note=note or f"Family transfer via MCP from {user_context.username}",
                )

                transaction_info = {
                    "from_account": "family",
                    "from_username": sbd_account["account_username"],
                    "family_id": family_id,
                    "initiated_by": user_context.username,
                    "to_username": to_username,
                    "amount": amount,
                    "note": note,
                    "transaction_id": transfer_result.get("transaction_id"),
                    "timestamp": datetime.now().isoformat(),
                }

            except Exception as e:
                raise MCPToolError(f"Failed to process family transfer: {str(e)}")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="transfer_sbd_tokens",
            resource_type="sbd_transfer",
            resource_id=transaction_info.get("transaction_id", "unknown"),
            metadata={
                "from_account": from_account,
                "to_username": to_username,
                "amount": amount,
                "family_id": family_id,
                "note": note,
            },
            user_context=user_context,
        )

        logger.info(
            "User %s transferred %d SBD tokens from %s account to %s (txn: %s)",
            user_context.username,
            amount,
            from_account,
            to_username,
            transaction_info.get("transaction_id", "unknown"),
        )

        return {"status": "success", "transfer": transaction_info}

    except (MCPValidationError, MCPAuthorizationError):
        raise
    except Exception as e:
        logger.error("Failed to transfer SBD tokens for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to transfer SBD tokens: {str(e)}")


@authenticated_tool(
    name="get_sbd_earning_history",
    description="Get user's SBD token earning history and sources",
    permissions=["sbd:read"],
    rate_limit_action="sbd_read",
)
async def get_sbd_earning_history(limit: int = 20, offset: int = 0, days: int = 30) -> Dict[str, Any]:
    """
    Get user's SBD token earning history including all income sources.

    Args:
        limit: Maximum number of earning records to return
        offset: Number of records to skip for pagination
        days: Number of days to include in history

    Returns:
        Dictionary containing earning history and analytics
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0
    if days < 1:
        days = 1
    if days > 365:
        days = 365

    try:
        users_collection = db_manager.get_collection("users")

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_date_iso = start_date.isoformat()

        # Get user's transactions
        user = await users_collection.find_one({"username": user_context.username}, {"sbd_tokens_transactions": 1})

        if not user:
            raise MCPValidationError("User not found")

        all_transactions = user.get("sbd_tokens_transactions", [])

        # Filter for earning transactions (receive type) within date range
        earning_transactions = []
        for txn in all_transactions:
            if txn.get("type") == "receive" and txn.get("timestamp", "") >= start_date_iso:
                earning_transactions.append(txn)

        # Sort by timestamp (most recent first)
        earning_transactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Analyze earnings by source
        earnings_analysis = {
            "total_earned": 0,
            "transaction_count": len(earning_transactions),
            "by_source": {},
            "by_type": {},
            "daily_breakdown": {},
        }

        for txn in earning_transactions:
            amount = txn.get("amount", 0)
            earnings_analysis["total_earned"] += amount

            # Categorize by source (from field)
            source = txn.get("from", "unknown")
            earnings_analysis["by_source"][source] = earnings_analysis["by_source"].get(source, 0) + amount

            # Categorize by transaction type based on note or source
            note = txn.get("note", "").lower()
            if "ad" in note or "admob" in note:
                txn_type = "advertising"
            elif "family" in note:
                txn_type = "family_transfer"
            elif "reward" in note or "bonus" in note:
                txn_type = "rewards"
            elif "transfer" in note:
                txn_type = "user_transfer"
            else:
                txn_type = "other"

            earnings_analysis["by_type"][txn_type] = earnings_analysis["by_type"].get(txn_type, 0) + amount

            # Daily breakdown
            try:
                txn_date = datetime.fromisoformat(txn.get("timestamp", "")).date().isoformat()
                earnings_analysis["daily_breakdown"][txn_date] = (
                    earnings_analysis["daily_breakdown"].get(txn_date, 0) + amount
                )
            except Exception:
                continue

        # Apply pagination to transactions
        total_earnings = len(earning_transactions)
        paginated_earnings = earning_transactions[offset : offset + limit]

        # Calculate average daily earnings
        if days > 0:
            avg_daily_earnings = earnings_analysis["total_earned"] / days
        else:
            avg_daily_earnings = 0

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_sbd_earning_history",
            resource_type="sbd_earnings",
            resource_id=user_context.username,
            metadata={
                "limit": limit,
                "offset": offset,
                "days": days,
                "total_earned": earnings_analysis["total_earned"],
                "transaction_count": earnings_analysis["transaction_count"],
            },
            user_context=user_context,
        )

        logger.info(
            "User %s retrieved SBD earning history: %d transactions, %d total earned over %d days",
            user_context.username,
            earnings_analysis["transaction_count"],
            earnings_analysis["total_earned"],
            days,
        )

        return {
            "status": "success",
            "earnings": {
                "transactions": paginated_earnings,
                "analysis": earnings_analysis,
                "summary": {
                    "period_days": days,
                    "total_earned": earnings_analysis["total_earned"],
                    "transaction_count": earnings_analysis["transaction_count"],
                    "average_daily_earnings": round(avg_daily_earnings, 2),
                    "top_earning_source": (
                        max(earnings_analysis["by_source"].items(), key=lambda x: x[1], default=("none", 0))[0]
                        if earnings_analysis["by_source"]
                        else "none"
                    ),
                },
            },
            "pagination": {
                "total": total_earnings,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_earnings,
            },
        }

    except Exception as e:
        logger.error("Failed to get SBD earning history for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get SBD earning history: {str(e)}")


@authenticated_tool(
    name="get_sbd_spending_analytics",
    description="Get comprehensive SBD token spending analytics and insights",
    permissions=["sbd:read"],
    rate_limit_action="sbd_read",
)
async def get_sbd_spending_analytics(days: int = 30, include_family: bool = True) -> Dict[str, Any]:
    """
    Get comprehensive SBD token spending analytics including patterns and insights.

    Args:
        days: Number of days to include in analytics
        include_family: Whether to include family spending analytics

    Returns:
        Dictionary containing detailed spending analytics and insights
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if days < 1:
        days = 1
    if days > 365:
        days = 365

    try:
        users_collection = db_manager.get_collection("users")

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_date_iso = start_date.isoformat()

        # Get user's transactions
        user = await users_collection.find_one(
            {"username": user_context.username}, {"sbd_tokens_transactions": 1, "sbd_tokens": 1}
        )

        if not user:
            raise MCPValidationError("User not found")

        current_balance = user.get("sbd_tokens", 0)
        all_transactions = user.get("sbd_tokens_transactions", [])

        # Filter for spending transactions (send type) within date range
        spending_transactions = []
        earning_transactions = []

        for txn in all_transactions:
            if txn.get("timestamp", "") >= start_date_iso:
                if txn.get("type") == "send":
                    spending_transactions.append(txn)
                elif txn.get("type") == "receive":
                    earning_transactions.append(txn)

        # Analyze spending patterns
        spending_analytics = {
            "period": {"days": days, "start_date": start_date_iso, "end_date": end_date.isoformat()},
            "current_balance": current_balance,
            "spending_summary": {
                "total_spent": 0,
                "transaction_count": len(spending_transactions),
                "average_transaction": 0,
                "largest_transaction": 0,
                "smallest_transaction": float("inf") if spending_transactions else 0,
            },
            "earning_summary": {"total_earned": 0, "transaction_count": len(earning_transactions)},
            "net_change": 0,
            "spending_by_category": {},
            "spending_by_recipient": {},
            "daily_spending": {},
            "spending_trends": {},
            "insights": [],
        }

        # Analyze spending transactions
        for txn in spending_transactions:
            amount = txn.get("amount", 0)
            spending_analytics["spending_summary"]["total_spent"] += amount

            # Track largest and smallest transactions
            if amount > spending_analytics["spending_summary"]["largest_transaction"]:
                spending_analytics["spending_summary"]["largest_transaction"] = amount
            if amount < spending_analytics["spending_summary"]["smallest_transaction"]:
                spending_analytics["spending_summary"]["smallest_transaction"] = amount

            # Categorize spending
            recipient = txn.get("to", "unknown")
            note = txn.get("note", "").lower()

            # Spending by recipient
            spending_analytics["spending_by_recipient"][recipient] = (
                spending_analytics["spending_by_recipient"].get(recipient, 0) + amount
            )

            # Spending by category
            if "shop" in note or recipient == "emotion_tracker_shop":
                category = "shop_purchases"
            elif "transfer" in note:
                category = "user_transfers"
            elif "family" in note:
                category = "family_transfers"
            else:
                category = "other"

            spending_analytics["spending_by_category"][category] = (
                spending_analytics["spending_by_category"].get(category, 0) + amount
            )

            # Daily spending breakdown
            try:
                txn_date = datetime.fromisoformat(txn.get("timestamp", "")).date().isoformat()
                spending_analytics["daily_spending"][txn_date] = (
                    spending_analytics["daily_spending"].get(txn_date, 0) + amount
                )
            except Exception:
                continue

        # Analyze earning transactions
        for txn in earning_transactions:
            amount = txn.get("amount", 0)
            spending_analytics["earning_summary"]["total_earned"] += amount

        # Calculate averages and net change
        if spending_analytics["spending_summary"]["transaction_count"] > 0:
            spending_analytics["spending_summary"]["average_transaction"] = round(
                spending_analytics["spending_summary"]["total_spent"]
                / spending_analytics["spending_summary"]["transaction_count"],
                2,
            )

        if spending_analytics["spending_summary"]["smallest_transaction"] == float("inf"):
            spending_analytics["spending_summary"]["smallest_transaction"] = 0

        spending_analytics["net_change"] = (
            spending_analytics["earning_summary"]["total_earned"]
            - spending_analytics["spending_summary"]["total_spent"]
        )

        # Calculate spending trends
        if days >= 7:
            # Weekly comparison
            week_ago = (end_date - timedelta(days=7)).isoformat()
            recent_week_spending = sum(
                txn.get("amount", 0) for txn in spending_transactions if txn.get("timestamp", "") >= week_ago
            )

            if days >= 14:
                previous_week_spending = sum(
                    txn.get("amount", 0)
                    for txn in spending_transactions
                    if week_ago > txn.get("timestamp", "") >= (end_date - timedelta(days=14)).isoformat()
                )

                if previous_week_spending > 0:
                    week_change = ((recent_week_spending - previous_week_spending) / previous_week_spending) * 100
                    spending_analytics["spending_trends"]["weekly_change_percent"] = round(week_change, 2)

        # Generate insights
        insights = []

        # Balance insights
        if current_balance < 100:
            insights.append(
                {
                    "type": "warning",
                    "message": "Your SBD token balance is running low. Consider earning more tokens or reducing spending.",
                }
            )

        # Spending pattern insights
        total_spent = spending_analytics["spending_summary"]["total_spent"]
        if total_spent > 0:
            shop_spending = spending_analytics["spending_by_category"].get("shop_purchases", 0)
            shop_percentage = (shop_spending / total_spent) * 100

            if shop_percentage > 80:
                insights.append(
                    {"type": "info", "message": f"Most of your spending ({shop_percentage:.1f}%) is on shop purchases."}
                )

            # Daily average insights
            avg_daily_spending = total_spent / days
            if avg_daily_spending > 50:
                insights.append(
                    {
                        "type": "info",
                        "message": f"You're spending an average of {avg_daily_spending:.1f} tokens per day.",
                    }
                )

        # Net change insights
        if spending_analytics["net_change"] < 0:
            insights.append(
                {
                    "type": "warning",
                    "message": f"You've spent {abs(spending_analytics['net_change'])} more tokens than you've earned in the last {days} days.",
                }
            )
        elif spending_analytics["net_change"] > 0:
            insights.append(
                {
                    "type": "positive",
                    "message": f"You've earned {spending_analytics['net_change']} more tokens than you've spent in the last {days} days.",
                }
            )

        spending_analytics["insights"] = insights

        # Get family spending analytics if requested
        family_analytics = {}
        if include_family:
            try:
                from ....managers.family_manager import family_manager

                user_families = await family_manager.get_user_families(user_context.user_id)

                for family in user_families:
                    family_id = family["family_id"]
                    try:
                        # Get family spending data
                        sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)

                        user_permissions = sbd_account["spending_permissions"].get(user_context.user_id, {})
                        can_view = user_permissions.get("can_spend", False) or family["role"] in ["owner", "admin"]

                        if can_view:
                            family_analytics[family_id] = {
                                "family_name": family["name"],
                                "balance": sbd_account["balance"],
                                "user_spending_limit": user_permissions.get("spending_limit", 0),
                                "can_spend": user_permissions.get("can_spend", False),
                                "is_frozen": sbd_account["is_frozen"],
                            }
                    except Exception as e:
                        logger.warning("Failed to get family analytics for %s: %s", family_id, e)
                        continue
            except Exception as e:
                logger.warning("Failed to get family analytics: %s", e)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_sbd_spending_analytics",
            resource_type="sbd_analytics",
            resource_id=user_context.username,
            metadata={
                "days": days,
                "include_family": include_family,
                "total_spent": spending_analytics["spending_summary"]["total_spent"],
                "total_earned": spending_analytics["earning_summary"]["total_earned"],
                "net_change": spending_analytics["net_change"],
                "insights_count": len(insights),
            },
            user_context=user_context,
        )

        logger.info(
            "User %s retrieved SBD spending analytics: %d days, %d spent, %d earned, net: %d",
            user_context.username,
            days,
            spending_analytics["spending_summary"]["total_spent"],
            spending_analytics["earning_summary"]["total_earned"],
            spending_analytics["net_change"],
        )

        return {
            "status": "success",
            "analytics": {"personal": spending_analytics, "family": family_analytics if include_family else {}},
        }

    except Exception as e:
        logger.error("Failed to get SBD spending analytics for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get SBD spending analytics: {str(e)}")
