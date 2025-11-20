# Digital Shop API Documentation

This document provides comprehensive API documentation for the Digital Shop platform.

## Base URL

```
https://api.secondbraindatabase.com/api/shop
```

## Authentication

All API requests require authentication using JWT tokens.

### Headers

```http
Authorization: Bearer <your_jwt_token>
Content-Type: application/json
```

## Endpoints

### Items

#### Get All Items

Retrieve a list of all available shop items with optional filtering and pagination.

**Endpoint**: `GET /items`

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number (default: 1) |
| `limit` | integer | No | Items per page (default: 20, max: 100) |
| `category` | string | No | Filter by category slug |
| `minPrice` | number | No | Minimum price filter |
| `maxPrice` | number | No | Maximum price filter |
| `minRating` | number | No | Minimum rating (1-5) |
| `sortBy` | string | No | Sort field: `price`, `rating`, `createdAt`, `popularity` |
| `sortOrder` | string | No | Sort order: `asc` or `desc` |
| `search` | string | No | Search term for name/description |

**Example Request**:

```bash
curl -X GET "https://api.secondbraindatabase.com/api/shop/items?category=themes&minPrice=10&maxPrice=50&sortBy=rating&sortOrder=desc" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "item_123",
        "name": "Premium Dark Theme",
        "description": "A beautiful dark theme for modern websites",
        "price": 29.99,
        "category": {
          "id": "cat_1",
          "name": "Themes",
          "slug": "themes"
        },
        "images": [
          "https://cdn.example.com/theme1.jpg",
          "https://cdn.example.com/theme1-preview.jpg"
        ],
        "rating": 4.8,
        "reviewCount": 156,
        "purchaseCount": 1240,
        "createdAt": "2024-01-15T10:30:00Z",
        "updatedAt": "2024-11-01T14:20:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 45,
      "totalPages": 3
    }
  }
}
```

#### Get Item by ID

Retrieve detailed information about a specific item.

**Endpoint**: `GET /items/:id`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Item ID |

**Example Request**:

```bash
curl -X GET "https://api.secondbraindatabase.com/api/shop/items/item_123" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "id": "item_123",
    "name": "Premium Dark Theme",
    "description": "A beautiful dark theme for modern websites with responsive design and customizable components.",
    "longDescription": "Detailed markdown description...",
    "price": 29.99,
    "category": {
      "id": "cat_1",
      "name": "Themes",
      "slug": "themes"
    },
    "images": [
      "https://cdn.example.com/theme1.jpg",
      "https://cdn.example.com/theme1-preview.jpg"
    ],
    "rating": 4.8,
    "reviewCount": 156,
    "purchaseCount": 1240,
    "features": [
      "Responsive design",
      "Dark mode support",
      "Customizable colors",
      "SEO optimized"
    ],
    "specifications": {
      "version": "2.1.0",
      "compatibility": "All modern browsers",
      "fileSize": "2.5 MB"
    },
    "createdAt": "2024-01-15T10:30:00Z",
    "updatedAt": "2024-11-01T14:20:00Z"
  }
}
```

#### Create Item (Admin Only)

Create a new shop item.

**Endpoint**: `POST /items`

**Request Body**:

```json
{
  "name": "New Premium Plugin",
  "description": "Short description",
  "longDescription": "Detailed description in markdown",
  "price": 39.99,
  "categoryId": "cat_2",
  "images": [
    "https://cdn.example.com/plugin1.jpg"
  ],
  "features": [
    "Feature 1",
    "Feature 2"
  ],
  "specifications": {
    "version": "1.0.0",
    "compatibility": "All platforms"
  }
}
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "id": "item_456",
    "name": "New Premium Plugin",
    "price": 39.99,
    "createdAt": "2024-11-20T10:00:00Z"
  }
}
```

#### Update Item (Admin Only)

Update an existing item.

**Endpoint**: `PUT /items/:id`

**Request Body**: Same as Create Item (all fields optional)

#### Delete Item (Admin Only)

Delete an item from the shop.

**Endpoint**: `DELETE /items/:id`

**Example Response**:

```json
{
  "success": true,
  "message": "Item deleted successfully"
}
```

---

### Categories

#### Get All Categories

Retrieve all item categories.

**Endpoint**: `GET /categories`

**Example Response**:

```json
{
  "success": true,
  "data": [
    {
      "id": "cat_1",
      "name": "Themes",
      "slug": "themes",
      "description": "Website themes and templates",
      "itemCount": 45
    },
    {
      "id": "cat_2",
      "name": "Plugins",
      "slug": "plugins",
      "description": "Functional plugins and extensions",
      "itemCount": 32
    }
  ]
}
```

#### Create Category (Admin Only)

**Endpoint**: `POST /categories`

**Request Body**:

```json
{
  "name": "Assets",
  "slug": "assets",
  "description": "Digital assets and resources"
}
```

---

### Purchases

#### Get User Purchases

Retrieve all purchases for the authenticated user.

**Endpoint**: `GET /purchases`

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number |
| `limit` | integer | No | Items per page |

**Example Response**:

```json
{
  "success": true,
  "data": {
    "purchases": [
      {
        "id": "purchase_789",
        "item": {
          "id": "item_123",
          "name": "Premium Dark Theme",
          "images": ["https://cdn.example.com/theme1.jpg"]
        },
        "price": 29.99,
        "purchasedAt": "2024-11-15T14:30:00Z",
        "downloadUrl": "https://cdn.example.com/downloads/theme1.zip"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 5,
      "totalPages": 1
    }
  }
}
```

#### Create Purchase

Purchase an item.

**Endpoint**: `POST /purchases`

**Request Body**:

```json
{
  "itemId": "item_123",
  "paymentMethod": "sbd_tokens"
}
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "id": "purchase_789",
    "itemId": "item_123",
    "price": 29.99,
    "purchasedAt": "2024-11-20T10:00:00Z",
    "downloadUrl": "https://cdn.example.com/downloads/theme1.zip",
    "remainingTokens": 170.01
  }
}
```

**Error Responses**:

```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Insufficient SBD tokens for this purchase"
  }
}
```

---

### Reviews

#### Get Item Reviews

Get reviews for a specific item.

**Endpoint**: `GET /items/:id/reviews`

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number |
| `limit` | integer | No | Reviews per page |
| `minRating` | integer | No | Filter by minimum rating |

**Example Response**:

```json
{
  "success": true,
  "data": {
    "reviews": [
      {
        "id": "review_101",
        "user": {
          "id": "user_1",
          "name": "John Doe",
          "avatar": "https://cdn.example.com/avatar1.jpg"
        },
        "rating": 5,
        "comment": "Excellent theme! Very customizable and well-documented.",
        "createdAt": "2024-11-10T09:15:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 10,
      "total": 156,
      "totalPages": 16
    },
    "averageRating": 4.8
  }
}
```

#### Create Review

Add a review for a purchased item.

**Endpoint**: `POST /items/:id/reviews`

**Request Body**:

```json
{
  "rating": 5,
  "comment": "Great product! Highly recommended."
}
```

**Requirements**:
- User must have purchased the item
- User can only review once per item

---

## Error Handling

All API errors follow this format:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  }
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or missing authentication token |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `INSUFFICIENT_FUNDS` | 400 | Not enough tokens for purchase |
| `ALREADY_PURCHASED` | 400 | Item already purchased |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Rate Limiting

- **Rate Limit**: 100 requests per minute per user
- **Headers**: Rate limit info included in response headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1700000000
```

---

## Webhooks

Subscribe to shop events (Admin only):

### Available Events

- `item.created` - New item added
- `item.updated` - Item modified
- `item.deleted` - Item removed
- `purchase.completed` - Purchase successful
- `review.created` - New review added

### Webhook Payload

```json
{
  "event": "purchase.completed",
  "timestamp": "2024-11-20T10:00:00Z",
  "data": {
    "purchaseId": "purchase_789",
    "userId": "user_1",
    "itemId": "item_123",
    "price": 29.99
  }
}
```

---

## SDK Examples

### JavaScript/TypeScript

```typescript
import { ShopAPI } from '@sbd/shop-sdk';

const shop = new ShopAPI({
  apiKey: 'YOUR_API_KEY',
  baseURL: 'https://api.secondbraindatabase.com'
});

// Get items
const items = await shop.items.list({
  category: 'themes',
  sortBy: 'rating',
  sortOrder: 'desc'
});

// Purchase item
const purchase = await shop.purchases.create({
  itemId: 'item_123',
  paymentMethod: 'sbd_tokens'
});
```

### Python

```python
from sbd_shop import ShopClient

client = ShopClient(api_key='YOUR_API_KEY')

# Get items
items = client.items.list(
    category='themes',
    sort_by='rating',
    sort_order='desc'
)

# Purchase item
purchase = client.purchases.create(
    item_id='item_123',
    payment_method='sbd_tokens'
)
```

---

**Last Updated**: November 2024  
**API Version**: 1.0

For questions or support, contact: api-support@secondbraindatabase.com
