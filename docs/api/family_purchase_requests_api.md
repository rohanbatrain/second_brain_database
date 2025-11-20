# Family Purchase Request API Documentation

## 1. Feature Overview

The Family Purchase Request system allows family members to request the purchase of shop items using the shared family wallet, even if they do not have direct spending permissions or if the item's cost exceeds their personal spending limit. This creates a moderated workflow where family administrators can approve or deny these purchase requests.

### Key Concepts

-   **Purchase Request:** When a family member attempts to buy an item with family funds but lacks the necessary permissions, the system automatically creates a `PurchaseRequest` instead of failing the transaction.
-   **Admin Approval:** Family administrators are notified of new purchase requests and can view all pending requests for their family. They have the authority to either `approve` or `deny` them.
-   **Automatic Fulfillment:** Upon approval, the system automatically processes the payment from the family wallet and grants the item to the original requester.
-   **Notifications:** The system sends notifications to both admins (when a request is created) and the requester (when their request is approved or denied).

## 2. Client-Side Workflow

This section details the sequence of events and API calls for both family members and administrators.

### 2.1. Member's Workflow: Requesting a Purchase

1.  **Attempt a Purchase:** The user attempts to buy an item from the shop using the `family` payment method, as they normally would (e.g., by calling `POST /shop/themes/buy`).

2.  **Handle the "Pending Approval" Response:** If the purchase cannot be completed immediately due to a permissions issue (like an exceeded spending limit), the API will respond with a `202 Accepted` status code. This indicates that a purchase request has been created successfully.

    **Example `202 Accepted` Response:**
    ```json
    {
        "status": "pending_approval",
        "detail": "Purchase request created and is pending approval from a family admin.",
        "purchase_request": {
            "request_id": "pr_a1b2c3d4e5f6",
            "family_id": "fam_12345",
            "requester_info": {
                "user_id": "user_abc",
                "username": "requester_username"
            },
            "item_info": {
                "item_id": "theme_solar_flare",
                "name": "Solar Flare Theme",
                "item_type": "theme",
                "image_url": null
            },
            "cost": 500,
            "status": "PENDING",
            "created_at": "2025-10-23T10:00:00Z",
            "reviewed_by_info": null,
            "reviewed_at": null,
            "denial_reason": null,
            "transaction_id": null
        }
    }
    ```
    Your application should inform the user that their request has been sent to the family admins for approval.

3.  **Check Request Status:** To see the status of their pending requests, the member's device should periodically call the `GET /family/wallet/purchase-requests` endpoint, filtering by the `family_id`. The API will automatically only return requests initiated by that user.

### 2.2. Admin's Workflow: Managing Requests

1.  **View All Requests:** A family administrator can retrieve a list of all purchase requests for their family (including those from other members) by calling the `GET /family/wallet/purchase-requests` endpoint. The app should display this list in a dedicated "Approvals" section.

2.  **Approve a Request:** To approve a request, the admin's client will make a `POST` call to the approval endpoint.

    -   **Endpoint:** `POST /family/wallet/purchase-requests/{request_id}/approve`
    -   **Action:** The system validates the admin's permissions, verifies funds, calls the `process_payment` logic to transfer the tokens and grant the item to the *original requester*, and updates the request status to `APPROVED`.
    -   **UI:** The request should be removed from the pending list and perhaps moved to an "approved" or "history" tab.

3.  **Deny a Request:** To deny a request, the admin's client will make a `POST` call to the denial endpoint, optionally including a reason.

    -   **Endpoint:** `POST /family/wallet/purchase-requests/{request_id}/deny`
    -   **Action:** The system updates the request's status to `DENIED` and records the reason for the denial. No payment is processed.
    -   **UI:** The request should be removed from the pending list.

## 3. API Endpoint Details

All endpoints are located under the `/family` prefix.

### GET `/wallet/purchase-requests`

-   **Description:** Retrieves a list of purchase requests. The results are automatically filtered based on the user's role: admins see all requests for the specified family, while members only see their own.
-   **Method:** `GET`
-   **Authentication:** Required (standard user or admin).
-   **Query Parameters:**
    -   `family_id` (string, required): The ID of the family to fetch requests for.
-   **Success Response (`200 OK`):**
    ```json
    [
        {
            "request_id": "pr_a1b2c3d4e5f6",
            "family_id": "fam_12345",
            "requester_info": { "user_id": "user_abc", "username": "requester_username" },
            "item_info": { "item_id": "theme_solar_flare", "name": "Solar Flare Theme", "item_type": "theme", "image_url": null },
            "cost": 500,
            "status": "PENDING",
            "created_at": "2025-10-23T10:00:00Z",
            "reviewed_by_info": null,
            "reviewed_at": null,
            "denial_reason": null,
            "transaction_id": null
        }
    ]
    ```
-   **Error Responses:**
    -   `400 Bad Request`: If `family_id` is missing or invalid.
    -   `401 Unauthorized`: If the user is not authenticated.

### POST `/wallet/purchase-requests/{request_id}/approve`

-   **Description:** Approves a specific purchase request. This is an admin-only action.
-   **Method:** `POST`
-   **Authentication:** Required (family administrator).
-   **Path Parameters:**
    -   `request_id` (string, required): The ID of the purchase request to approve.
-   **Request Body:** None.
-   **Success Response (`200 OK`):** Returns the updated purchase request object with the status `APPROVED`.
    ```json
    {
        "request_id": "pr_a1b2c3d4e5f6",
        "status": "APPROVED",
        // ... other fields
        "reviewed_by_info": { "user_id": "admin_xyz", "username": "admin_username" },
        "reviewed_at": "2025-10-23T11:00:00Z",
        "transaction_id": "txn_new_purchase_abc"
    }
    ```
-   **Error Responses:**
    -   `400 Bad Request`: If the request is not in `PENDING` state or if the family has insufficient funds.
    -   `401 Unauthorized`: If the user is not authenticated.
    -   `403 Forbidden`: If the user is not an administrator of the family.
    -   `404 Not Found`: If the `request_id` does not exist.

### POST `/wallet/purchase-requests/{request_id}/deny`

-   **Description:** Denies a specific purchase request. This is an admin-only action.
-   **Method:** `POST`
-   **Authentication:** Required (family administrator).
-   **Path Parameters:**
    -   `request_id` (string, required): The ID of the purchase request to deny.
-   **Request Body:**
    ```json
    {
        "reason": "This item is too expensive."
    }
    ```
    -   `reason` (string, optional): An optional message explaining why the request was denied.
-   **Success Response (`200 OK`):** Returns the updated purchase request object with the status `DENIED`.
    ```json
    {
        "request_id": "pr_a1b2c3d4e5f6",
        "status": "DENIED",
        // ... other fields
        "reviewed_by_info": { "user_id": "admin_xyz", "username": "admin_username" },
        "reviewed_at": "2025-10-23T11:05:00Z",
        "denial_reason": "This item is too expensive."
    }
    ```
-   **Error Responses:**
    -   `400 Bad Request`: If the request is not in `PENDING` state.
    -   `401 Unauthorized`: If the user is not authenticated.
    -   `403 Forbidden`: If the user is not an administrator of the family.
    -   `404 Not Found`: If the `request_id` does not exist.

---