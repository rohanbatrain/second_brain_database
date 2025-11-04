# Shop & Asset Management MCP Tools

## Overview

Shop and asset management tools provide comprehensive functionality for browsing digital assets, making purchases, managing owned and rented items, and handling SBD token transactions. All tools include proper security validation and transaction logging.

## Shop Browsing Tools

### list_shop_items

Browse available items in the digital asset shop.

**Parameters:**
- `category` (string, optional): Item category ("avatars", "banners", "themes")
- `limit` (number, optional): Number of items to return (default: 20, max: 100)
- `offset` (number, optional): Pagination offset (default: 0)
- `sort_by` (string, optional): Sort criteria ("name", "price", "popularity", "newest")
- `filter` (object, optional): Additional filters

**Permissions Required:** `shop:browse`

**Example:**
```python
items = await mcp_client.call_tool("list_shop_items", {
    "category": "avatars",
    "limit": 10,
    "sort_by": "popularity",
    "filter": {
        "price_range": {"min": 0, "max": 100},
        "tags": ["fantasy", "character"]
    }
})

# Response
{
    "items": [
        {
            "id": "64f8a1b2c3d4e5f6a7b8c9d0",
            "name": "Dragon Warrior Avatar",
            "description": "Epic fantasy warrior with dragon armor",
            "category": "avatars",
            "price": 75,
            "rental_price": 15,
            "rental_duration": 30,
            "tags": ["fantasy", "warrior", "dragon"],
            "preview_url": "https://example.com/previews/dragon-warrior.png",
            "popularity_score": 95,
            "created_at": "2024-01-15T10:00:00Z",
            "is_featured": true,
            "is_new": false
        }
    ],
    "total_count": 156,
    "has_more": true,
    "categories": ["avatars", "banners", "themes"],
    "price_range": {"min": 5, "max": 500}
}
```

### get_item_details

Get detailed information about a specific shop item.

**Parameters:**
- `item_id` (string, required): Item identifier

**Permissions Required:** `shop:browse`

**Example:**
```python
item_details = await mcp_client.call_tool("get_item_details", {
    "item_id": "64f8a1b2c3d4e5f6a7b8c9d0"
})

# Response
{
    "id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "name": "Dragon Warrior Avatar",
    "description": "Epic fantasy warrior with dragon armor and magical weapons",
    "long_description": "This premium avatar features...",
    "category": "avatars",
    "price": 75,
    "rental_price": 15,
    "rental_duration": 30,
    "tags": ["fantasy", "warrior", "dragon", "premium"],
    "preview_images": [
        "https://example.com/previews/dragon-warrior-1.png",
        "https://example.com/previews/dragon-warrior-2.png"
    ],
    "animation_preview": "https://example.com/previews/dragon-warrior.gif",
    "creator": "ArtistStudio",
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-16T14:30:00Z",
    "popularity_score": 95,
    "purchase_count": 1247,
    "rating": 4.8,
    "reviews_count": 89,
    "is_featured": true,
    "is_exclusive": false,
    "availability": "available",
    "file_size": "2.5 MB",
    "resolution": "512x512",
    "format": "PNG"
}
```

### search_shop_items

Search for items using text query and filters.

**Parameters:**
- `query` (string, required): Search query
- `category` (string, optional): Category filter
- `limit` (number, optional): Results limit (default: 20)
- `filters` (object, optional): Additional search filters

**Permissions Required:** `shop:browse`

**Example:**
```python
search_results = await mcp_client.call_tool("search_shop_items", {
    "query": "dragon fantasy",
    "category": "avatars",
    "limit": 15,
    "filters": {
        "price_max": 100,
        "rating_min": 4.0,
        "is_animated": true
    }
})

# Response
{
    "query": "dragon fantasy",
    "results": [
        {
            "id": "64f8a1b2c3d4e5f6a7b8c9d0",
            "name": "Dragon Warrior Avatar",
            "description": "Epic fantasy warrior with dragon armor",
            "price": 75,
            "rental_price": 15,
            "preview_url": "https://example.com/previews/dragon-warrior.png",
            "relevance_score": 0.95,
            "match_highlights": ["Dragon", "fantasy"]
        }
    ],
    "total_results": 23,
    "search_time_ms": 45,
    "suggestions": ["dragon knight", "fantasy warrior", "mythical creatures"],
    "filters_applied": {
        "category": "avatars",
        "price_max": 100,
        "rating_min": 4.0
    }
}
```

### get_shop_categories

Get all available shop categories with item counts.

**Parameters:** None

**Permissions Required:** `shop:browse`

**Example:**
```python
categories = await mcp_client.call_tool("get_shop_categories")

# Response
{
    "categories": [
        {
            "name": "avatars",
            "display_name": "Avatars",
            "description": "Profile avatars and character representations",
            "item_count": 1247,
            "subcategories": [
                {"name": "fantasy", "item_count": 456},
                {"name": "sci-fi", "item_count": 234},
                {"name": "realistic", "item_count": 189}
            ],
            "price_range": {"min": 5, "max": 200}
        },
        {
            "name": "banners",
            "display_name": "Banners",
            "description": "Profile banners and backgrounds",
            "item_count": 892,
            "subcategories": [
                {"name": "nature", "item_count": 234},
                {"name": "abstract", "item_count": 198},
                {"name": "space", "item_count": 156}
            ],
            "price_range": {"min": 10, "max": 150}
        }
    ],
    "total_items": 2139,
    "featured_category": "avatars"
}
```

### get_featured_items

Get currently featured items in the shop.

**Parameters:**
- `limit` (number, optional): Number of items to return (default: 10)

**Permissions Required:** `shop:browse`

**Example:**
```python
featured = await mcp_client.call_tool("get_featured_items", {
    "limit": 5
})

# Response
{
    "featured_items": [
        {
            "id": "64f8a1b2c3d4e5f6a7b8c9d0",
            "name": "Dragon Warrior Avatar",
            "category": "avatars",
            "price": 75,
            "discount_price": 60,
            "discount_percentage": 20,
            "preview_url": "https://example.com/previews/dragon-warrior.png",
            "featured_reason": "Editor's Choice",
            "featured_until": "2024-02-01T00:00:00Z"
        }
    ],
    "promotion": {
        "title": "Fantasy Week Sale",
        "description": "20% off all fantasy-themed items",
        "ends_at": "2024-02-01T00:00:00Z"
    }
}
```

## Purchase and Transaction Tools

### purchase_item

Purchase an item from the shop.

**Parameters:**
- `item_id` (string, required): Item to purchase
- `quantity` (number, optional): Quantity (default: 1)
- `payment_method` (string, optional): Payment method ("sbd_tokens", "family_tokens")

**Permissions Required:** `shop:purchase`

**Example:**
```python
purchase_result = await mcp_client.call_tool("purchase_item", {
    "item_id": "64f8a1b2c3d4e5f6a7b8c9d0",
    "quantity": 1,
    "payment_method": "sbd_tokens"
})

# Response
{
    "success": true,
    "transaction_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "item": {
        "id": "64f8a1b2c3d4e5f6a7b8c9d0",
        "name": "Dragon Warrior Avatar",
        "category": "avatars"
    },
    "quantity": 1,
    "total_cost": 75,
    "payment_method": "sbd_tokens",
    "remaining_balance": 425,
    "purchase_date": "2024-01-20T15:30:00Z",
    "download_url": "https://example.com/downloads/dragon-warrior-avatar.zip",
    "license": "personal_use",
    "message": "Purchase completed successfully!"
}
```

### get_purchase_history

Get user's purchase history.

**Parameters:**
- `limit` (number, optional): Number of transactions to return (default: 20)
- `offset` (number, optional): Pagination offset
- `category` (string, optional): Filter by item category

**Permissions Required:** `shop:purchase`

**Example:**
```python
history = await mcp_client.call_tool("get_purchase_history", {
    "limit": 10,
    "category": "avatars"
})

# Response
{
    "transactions": [
        {
            "transaction_id": "64f8a1b2c3d4e5f6a7b8c9d1",
            "item": {
                "id": "64f8a1b2c3d4e5f6a7b8c9d0",
                "name": "Dragon Warrior Avatar",
                "category": "avatars"
            },
            "quantity": 1,
            "cost": 75,
            "payment_method": "sbd_tokens",
            "purchase_date": "2024-01-20T15:30:00Z",
            "status": "completed",
            "download_count": 1,
            "last_downloaded": "2024-01-20T15:35:00Z"
        }
    ],
    "total_transactions": 15,
    "total_spent": 1250,
    "most_purchased_category": "avatars",
    "has_more": true
}
```

### get_transaction_details

Get detailed information about a specific transaction.

**Parameters:**
- `transaction_id` (string, required): Transaction identifier

**Permissions Required:** `shop:purchase`

**Example:**
```python
transaction = await mcp_client.call_tool("get_transaction_details", {
    "transaction_id": "64f8a1b2c3d4e5f6a7b8c9d1"
})

# Response
{
    "transaction_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "item": {
        "id": "64f8a1b2c3d4e5f6a7b8c9d0",
        "name": "Dragon Warrior Avatar",
        "category": "avatars",
        "description": "Epic fantasy warrior with dragon armor"
    },
    "quantity": 1,
    "unit_price": 75,
    "total_cost": 75,
    "payment_method": "sbd_tokens",
    "purchase_date": "2024-01-20T15:30:00Z",
    "status": "completed",
    "download_info": {
        "download_url": "https://example.com/downloads/dragon-warrior-avatar.zip",
        "download_count": 1,
        "download_limit": 5,
        "last_downloaded": "2024-01-20T15:35:00Z",
        "expires_at": "2024-07-20T15:30:00Z"
    },
    "license": {
        "type": "personal_use",
        "terms": "Personal use only, no commercial redistribution"
    },
    "refund_eligible": true,
    "refund_deadline": "2024-01-27T15:30:00Z"
}
```

### refund_purchase

Request a refund for a purchase.

**Parameters:**
- `transaction_id` (string, required): Transaction to refund
- `reason` (string, required): Refund reason

**Permissions Required:** `shop:refund`

**Example:**
```python
refund_result = await mcp_client.call_tool("refund_purchase", {
    "transaction_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "reason": "Item not as described"
})

# Response
{
    "success": true,
    "refund_id": "64f8a1b2c3d4e5f6a7b8c9d2",
    "transaction_id": "64f8a1b2c3d4e5f6a7b8c9d1",
    "refund_amount": 75,
    "refund_method": "sbd_tokens",
    "processing_time": "1-3 business days",
    "status": "processing",
    "message": "Refund request submitted successfully"
}
```

## Asset Management Tools

### get_user_assets

Get all assets owned or rented by the user.

**Parameters:**
- `category` (string, optional): Filter by category
- `type` (string, optional): Filter by ownership type ("owned", "rented")
- `limit` (number, optional): Results limit

**Permissions Required:** `shop:browse`

**Example:**
```python
assets = await mcp_client.call_tool("get_user_assets", {
    "category": "avatars",
    "type": "owned"
})

# Response
{
    "assets": [
        {
            "id": "64f8a1b2c3d4e5f6a7b8c9d0",
            "name": "Dragon Warrior Avatar",
            "category": "avatars",
            "ownership_type": "owned",
            "acquired_date": "2024-01-20T15:30:00Z",
            "purchase_price": 75,
            "current_value": 75,
            "usage_count": 5,
            "last_used": "2024-01-22T10:15:00Z",
            "is_currently_active": true,
            "download_url": "https://example.com/downloads/dragon-warrior-avatar.zip"
        }
    ],
    "summary": {
        "total_owned": 12,
        "total_rented": 3,
        "total_value": 890,
        "most_used_category": "avatars"
    }
}
```

### get_rented_avatars

Get all currently rented avatars.

**Parameters:** None

**Permissions Required:** `shop:browse`

**Example:**
```python
rented_avatars = await mcp_client.call_tool("get_rented_avatars")

# Response
{
    "rented_avatars": [
        {
            "id": "64f8a1b2c3d4e5f6a7b8c9d3",
            "name": "Cyber Ninja Avatar",
            "rental_start": "2024-01-15T10:00:00Z",
            "rental_end": "2024-02-14T10:00:00Z",
            "days_remaining": 18,
            "rental_cost": 20,
            "auto_renew": false,
            "usage_count": 8,
            "can_extend": true,
            "extension_cost": 15
        }
    ],
    "total_rented": 1,
    "total_rental_cost": 20,
    "expiring_soon": 0
}
```

### rent_asset

Rent an asset for a specified duration.

**Parameters:**
- `item_id` (string, required): Item to rent
- `duration_days` (number, optional): Rental duration (default: 30)
- `auto_renew` (boolean, optional): Enable auto-renewal (default: false)

**Permissions Required:** `shop:purchase`

**Example:**
```python
rental_result = await mcp_client.call_tool("rent_asset", {
    "item_id": "64f8a1b2c3d4e5f6a7b8c9d4",
    "duration_days": 30,
    "auto_renew": false
})

# Response
{
    "success": true,
    "rental_id": "64f8a1b2c3d4e5f6a7b8c9d5",
    "item": {
        "id": "64f8a1b2c3d4e5f6a7b8c9d4",
        "name": "Space Explorer Avatar",
        "category": "avatars"
    },
    "rental_start": "2024-01-20T16:00:00Z",
    "rental_end": "2024-02-19T16:00:00Z",
    "rental_cost": 25,
    "remaining_balance": 400,
    "download_url": "https://example.com/downloads/space-explorer-avatar.zip",
    "auto_renew": false,
    "message": "Asset rented successfully!"
}
```

### extend_rental

Extend an existing rental period.

**Parameters:**
- `rental_id` (string, required): Rental to extend
- `additional_days` (number, required): Days to add

**Permissions Required:** `shop:purchase`

**Example:**
```python
extension_result = await mcp_client.call_tool("extend_rental", {
    "rental_id": "64f8a1b2c3d4e5f6a7b8c9d5",
    "additional_days": 15
})

# Response
{
    "success": true,
    "rental_id": "64f8a1b2c3d4e5f6a7b8c9d5",
    "previous_end_date": "2024-02-19T16:00:00Z",
    "new_end_date": "2024-03-05T16:00:00Z",
    "extension_cost": 12,
    "remaining_balance": 388,
    "message": "Rental extended successfully!"
}
```

### cancel_rental

Cancel an active rental (if cancellation is allowed).

**Parameters:**
- `rental_id` (string, required): Rental to cancel
- `reason` (string, optional): Cancellation reason

**Permissions Required:** `shop:purchase`

**Example:**
```python
cancellation_result = await mcp_client.call_tool("cancel_rental", {
    "rental_id": "64f8a1b2c3d4e5f6a7b8c9d5",
    "reason": "No longer needed"
})

# Response
{
    "success": true,
    "rental_id": "64f8a1b2c3d4e5f6a7b8c9d5",
    "cancellation_date": "2024-01-22T14:30:00Z",
    "refund_amount": 18,
    "refund_method": "sbd_tokens",
    "message": "Rental cancelled. Partial refund processed."
}
```

## SBD Token Management Tools

### get_sbd_balance

Get current SBD token balance and account information.

**Parameters:** None

**Permissions Required:** `shop:browse`

**Example:**
```python
balance_info = await mcp_client.call_tool("get_sbd_balance")

# Response
{
    "current_balance": 425,
    "pending_transactions": 2,
    "pending_amount": 50,
    "available_balance": 375,
    "total_earned": 2000,
    "total_spent": 1575,
    "last_transaction": "2024-01-20T15:30:00Z",
    "account_status": "active",
    "spending_limit": 1000,
    "spending_limit_period": "monthly",
    "current_period_spent": 150
}
```

### get_sbd_transaction_history

Get SBD token transaction history.

**Parameters:**
- `limit` (number, optional): Number of transactions (default: 20)
- `transaction_type` (string, optional): Filter by type ("earned", "spent", "transfer")

**Permissions Required:** `shop:browse`

**Example:**
```python
sbd_history = await mcp_client.call_tool("get_sbd_transaction_history", {
    "limit": 10,
    "transaction_type": "spent"
})

# Response
{
    "transactions": [
        {
            "transaction_id": "64f8a1b2c3d4e5f6a7b8c9d1",
            "type": "spent",
            "amount": -75,
            "description": "Purchase: Dragon Warrior Avatar",
            "timestamp": "2024-01-20T15:30:00Z",
            "balance_after": 425,
            "related_item": {
                "id": "64f8a1b2c3d4e5f6a7b8c9d0",
                "name": "Dragon Warrior Avatar",
                "category": "avatars"
            }
        }
    ],
    "total_transactions": 45,
    "period_summary": {
        "earned_this_month": 200,
        "spent_this_month": 150,
        "net_change": 50
    }
}
```

### transfer_sbd_tokens

Transfer SBD tokens to another user.

**Parameters:**
- `recipient_id` (string, required): Recipient user ID
- `amount` (number, required): Amount to transfer
- `message` (string, optional): Transfer message

**Permissions Required:** `shop:transfer`

**Example:**
```python
transfer_result = await mcp_client.call_tool("transfer_sbd_tokens", {
    "recipient_id": "64f8a1b2c3d4e5f6a7b8c9d6",
    "amount": 50,
    "message": "Thanks for helping with the project!"
})

# Response
{
    "success": true,
    "transfer_id": "64f8a1b2c3d4e5f6a7b8c9d7",
    "amount": 50,
    "recipient": {
        "id": "64f8a1b2c3d4e5f6a7b8c9d6",
        "username": "friend_user"
    },
    "new_balance": 375,
    "transfer_fee": 0,
    "timestamp": "2024-01-22T16:45:00Z",
    "message": "Transfer completed successfully!"
}
```

### request_sbd_tokens

Request SBD tokens (for family members or special circumstances).

**Parameters:**
- `amount` (number, required): Amount requested
- `reason` (string, required): Reason for request
- `family_id` (string, optional): Family ID if requesting from family funds

**Permissions Required:** `shop:request_tokens`

**Example:**
```python
request_result = await mcp_client.call_tool("request_sbd_tokens", {
    "amount": 100,
    "reason": "Need tokens for avatar purchase",
    "family_id": "64f8a1b2c3d4e5f6a7b8c9d8"
})

# Response
{
    "success": true,
    "request_id": "64f8a1b2c3d4e5f6a7b8c9d9",
    "amount": 100,
    "reason": "Need tokens for avatar purchase",
    "status": "pending",
    "submitted_at": "2024-01-22T17:00:00Z",
    "estimated_review_time": "24 hours",
    "message": "Token request submitted for review"
}
```

## Analytics and Insights Tools

### get_spending_summary

Get spending analytics and insights.

**Parameters:**
- `period` (string, optional): Time period ("week", "month", "year")

**Permissions Required:** `shop:browse`

**Example:**
```python
spending_summary = await mcp_client.call_tool("get_spending_summary", {
    "period": "month"
})

# Response
{
    "period": "month",
    "total_spent": 150,
    "total_earned": 200,
    "net_change": 50,
    "transaction_count": 8,
    "average_transaction": 18.75,
    "spending_by_category": {
        "avatars": 100,
        "banners": 30,
        "themes": 20
    },
    "most_expensive_purchase": {
        "item_name": "Dragon Warrior Avatar",
        "amount": 75,
        "date": "2024-01-20T15:30:00Z"
    },
    "spending_trend": "increasing",
    "budget_status": {
        "monthly_limit": 200,
        "spent": 150,
        "remaining": 50,
        "percentage_used": 75
    }
}
```

### get_asset_usage_history

Get usage statistics for owned and rented assets.

**Parameters:**
- `asset_id` (string, optional): Specific asset ID
- `period` (string, optional): Time period for statistics

**Permissions Required:** `shop:browse`

**Example:**
```python
usage_history = await mcp_client.call_tool("get_asset_usage_history", {
    "period": "month"
})

# Response
{
    "period": "month",
    "total_assets": 15,
    "active_assets": 8,
    "usage_statistics": [
        {
            "asset_id": "64f8a1b2c3d4e5f6a7b8c9d0",
            "name": "Dragon Warrior Avatar",
            "category": "avatars",
            "usage_count": 12,
            "total_usage_time": "48 hours",
            "last_used": "2024-01-22T10:15:00Z",
            "usage_trend": "increasing"
        }
    ],
    "most_used_asset": {
        "name": "Dragon Warrior Avatar",
        "usage_count": 12
    },
    "least_used_assets": 3,
    "recommendations": [
        "Consider using your Cyber Ninja Avatar more often",
        "Your Space Explorer Banner hasn't been used recently"
    ]
}
```

## Error Handling

### Common Shop Errors

**Insufficient Balance:**
```json
{
    "error": {
        "code": "INSUFFICIENT_BALANCE",
        "message": "Insufficient SBD tokens for purchase",
        "details": {
            "required": 75,
            "available": 50,
            "shortfall": 25
        }
    }
}
```

**Item Not Available:**
```json
{
    "error": {
        "code": "ITEM_NOT_AVAILABLE",
        "message": "Item is no longer available for purchase",
        "details": {
            "item_id": "64f8a1b2c3d4e5f6a7b8c9d0",
            "reason": "discontinued",
            "alternatives": ["64f8a1b2c3d4e5f6a7b8c9d1"]
        }
    }
}
```

**Purchase Limit Exceeded:**
```json
{
    "error": {
        "code": "PURCHASE_LIMIT_EXCEEDED",
        "message": "Monthly spending limit exceeded",
        "details": {
            "limit": 200,
            "current_spent": 180,
            "attempted_purchase": 75,
            "reset_date": "2024-02-01T00:00:00Z"
        }
    }
}
```

## Best Practices

### Shopping Recommendations

1. **Browse categories** to discover new items
2. **Use search filters** to find specific items
3. **Check item details** before purchasing
4. **Consider rental options** for temporary use
5. **Monitor spending** against budgets

### Asset Management

1. **Organize assets** by category and usage
2. **Track rental expiration dates** to avoid unexpected charges
3. **Use analytics** to optimize asset usage
4. **Keep download links** accessible for re-downloads
5. **Review refund policies** before purchases

### Performance Optimization

1. **Cache shop data** appropriately on client side
2. **Use pagination** for large result sets
3. **Implement proper loading states** for purchases
4. **Handle network errors** gracefully during transactions
5. **Batch related operations** when possible