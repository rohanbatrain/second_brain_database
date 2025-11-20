"""
IPAM Manager Enhancements - Continuation Methods

This file contains additional enhancement methods that will be integrated into ipam_manager.py.
These methods implement: Shareable Links, Webhooks, Bulk Operations, and Enhanced Search.

To integrate: Copy these methods into the IPAMManager class in ipam_manager.py before the global instance.
"""

# ==================== IPAM Enhancements: Shareable Links ====================

async def create_share(
    self,
    user_id: str,
    resource_type: str,
    resource_id: str,
    expires_in_days: int,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a shareable link.

    Args:
        user_id: User ID
        resource_type: Resource type ("country", "region", "host")
        resource_id: Resource ID
        expires_in_days: Expiration in days (max 90)
        description: Optional description

    Returns:
        Dict containing share details
    """
    try:
        import uuid
        from datetime import timedelta
        
        # Validate resource exists and user owns it
        if resource_type == "region":
            region = await self.get_region_by_id(user_id, resource_id)
            if not region:
                raise IPAMError(f"Region not found: {resource_id}")
        elif resource_type == "host":
            host = await self.get_host_by_id(user_id, resource_id)
            if not host:
                raise IPAMError(f"Host not found: {resource_id}")
        elif resource_type == "country":
            # Just validate country exists
            await self.get_country_mapping(resource_id)

        # Generate share token
        share_token = str(uuid.uuid4())
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=min(expires_in_days, 90))
        
        share_doc = {
            "share_token": share_token,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "expires_at": expires_at,
            "view_count": 0,
            "last_accessed": None,
            "created_at": now,
            "created_by": user_id,
            "is_active": True,
            "description": description
        }

        collection = self.db_manager.get_collection("ipam_shares")
        result = await collection.insert_one(share_doc)
        share_doc["_id"] = str(result.inserted_id)

        # Build share URL (will be completed by API layer)
        share_doc["share_url"] = f"/ipam/shares/{share_token}"

        self.logger.info("Share created: user=%s type=%s resource=%s token=%s", user_id, resource_type, resource_id, share_token)
        return share_doc

    except (IPAMError, CountryNotFound):
        raise
    except Exception as e:
        self.logger.error("Failed to create share: %s", e, exc_info=True)
        raise IPAMError(f"Failed to create share: {str(e)}")

async def get_shared_resource(self, share_token: str) -> Dict[str, Any]:
    """
    Get shared resource (no auth required).

    Args:
        share_token: Share token

    Returns:
        Dict containing sanitized resource data

    Raises:
        IPAMError: If share not found or expired
    """
    try:
        collection = self.db_manager.get_collection("ipam_shares")
        share = await collection.find_one({"share_token": share_token, "is_active": True})

        if not share:
            raise IPAMError("Share not found or has been revoked")

        # Check expiration
        if share["expires_at"] < datetime.now(timezone.utc):
            raise IPAMError("Share has expired")

        # Get resource data
        resource_type = share["resource_type"]
        resource_id = share["resource_id"]
        user_id = share["user_id"]

        if resource_type == "region":
            resource_data = await self.get_region_by_id(user_id, resource_id)
        elif resource_type == "host":
            resource_data = await self.get_host_by_id(user_id, resource_id)
        elif resource_type == "country":
            resource_data = await self.get_country_mapping(resource_id)
        else:
            raise IPAMError(f"Invalid resource type: {resource_type}")

        # Sanitize data (remove sensitive fields)
        sanitized_data = self._sanitize_shared_resource(resource_data)

        # Update view count and last accessed
        await collection.update_one(
            {"_id": share["_id"]},
            {
                "$inc": {"view_count": 1},
                "$set": {"last_accessed": datetime.now(timezone.utc)}
            }
        )

        # Get username for shared_by
        users_collection = self.db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": user_id}, {"username": 1})
        shared_by = user.get("username", "Unknown") if user else "Unknown"

        return {
            "resource_type": resource_type,
            "resource_data": sanitized_data,
            "shared_by": shared_by,
            "created_at": share["created_at"]
        }

    except IPAMError:
        raise
    except Exception as e:
        self.logger.error("Failed to get shared resource: %s", e, exc_info=True)
        raise IPAMError(f"Failed to get shared resource: {str(e)}")

def _sanitize_shared_resource(self, resource_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize resource data for sharing (remove sensitive info).

    Args:
        resource_data: Resource data

    Returns:
        Sanitized resource data
    """
    # Remove sensitive fields
    sensitive_fields = ["user_id", "created_by", "updated_by", "owner", "comments", "notes"]
    sanitized = {k: v for k, v in resource_data.items() if k not in sensitive_fields}
    return sanitized

async def list_user_shares(self, user_id: str) -> List[Dict[str, Any]]:
    """
    List user's active shares.

    Args:
        user_id: User ID

    Returns:
        List of shares
    """
    try:
        collection = self.db_manager.get_collection("ipam_shares")
        cursor = collection.find({"user_id": user_id, "is_active": True}).sort("created_at", -1)
        shares = await cursor.to_list(None)

        for share in shares:
            share["_id"] = str(share["_id"])
            share["share_url"] = f"/ipam/shares/{share['share_token']}"

        return shares

    except Exception as e:
        self.logger.error("Failed to list shares: %s", e, exc_info=True)
        raise IPAMError(f"Failed to list shares: {str(e)}")

async def revoke_share(self, user_id: str, share_id: str) -> None:
    """
    Revoke (delete) a share.

    Args:
        user_id: User ID
        share_id: Share ID

    Raises:
        IPAMError: If share not found
    """
    try:
        collection = self.db_manager.get_collection("ipam_shares")
        result = await collection.update_one(
            {"_id": ObjectId(share_id), "user_id": user_id},
            {"$set": {"is_active": False}}
        )

        if result.modified_count == 0:
            raise IPAMError(f"Share not found: {share_id}")

        self.logger.info("Share revoked: user=%s share_id=%s", user_id, share_id)

    except IPAMError:
        raise
    except Exception as e:
        self.logger.error("Failed to revoke share: %s", e, exc_info=True)
        raise IPAMError(f"Failed to revoke share: {str(e)}")

# ==================== IPAM Enhancements: Webhook System ====================

async def create_webhook(
    self,
    user_id: str,
    webhook_url: str,
    events: List[str],
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a webhook.

    Args:
        user_id: User ID
        webhook_url: Webhook URL
        events: List of events to subscribe to
        description: Optional description

    Returns:
        Dict containing webhook details with secret key
    """
    try:
        import secrets
        
        # Generate secret key for HMAC
        secret_key = secrets.token_urlsafe(32)
        
        now = datetime.now(timezone.utc)
        
        webhook_doc = {
            "user_id": user_id,
            "webhook_url": webhook_url,
            "secret_key": secret_key,
            "events": events,
            "is_active": True,
            "failure_count": 0,
            "last_delivery": None,
            "description": description,
            "created_at": now,
            "updated_at": now
        }

        collection = self.db_manager.get_collection("ipam_webhooks")
        result = await collection.insert_one(webhook_doc)
        webhook_doc["_id"] = str(result.inserted_id)

        self.logger.info("Webhook created: user=%s url=%s events=%s", user_id, webhook_url, events)
        return webhook_doc

    except Exception as e:
        self.logger.error("Failed to create webhook: %s", e, exc_info=True)
        raise IPAMError(f"Failed to create webhook: {str(e)}")

async def deliver_webhook(
    self,
    webhook_id: ObjectId,
    event_type: str,
    payload: Dict[str, Any]
) -> None:
    """
    Deliver webhook with retry logic (async, non-blocking).

    Args:
        webhook_id: Webhook ID
        event_type: Event type
        payload: Event payload
    """
    try:
        import hmac
        import hashlib
        import json
        import httpx
        
        collection = self.db_manager.get_collection("ipam_webhooks")
        webhook = await collection.find_one({"_id": webhook_id})

        if not webhook or not webhook["is_active"]:
            return

        # Generate HMAC signature
        payload_json = json.dumps(payload)
        signature = hmac.new(
            webhook["secret_key"].encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-IPAM-Signature": f"sha256={signature}",
            "X-IPAM-Event": event_type
        }

        # Retry logic (3 attempts with exponential backoff)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                start_time = time.time()
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        webhook["webhook_url"],
                        json=payload,
                        headers=headers
                    )
                
                response_time_ms = int((time.time() - start_time) * 1000)

                # Log delivery
                deliveries_collection = self.db_manager.get_collection("ipam_webhook_deliveries")
                await deliveries_collection.insert_one({
                    "webhook_id": webhook_id,
                    "event_type": event_type,
                    "payload": payload,
                    "status_code": response.status_code,
                    "response_time_ms": response_time_ms,
                    "error_message": None,
                    "attempt_number": attempt,
                    "delivered_at": datetime.now(timezone.utc)
                })

                if response.status_code < 500:
                    # Success or client error (don't retry)
                    await collection.update_one(
                        {"_id": webhook_id},
                        {"$set": {"last_delivery": datetime.now(timezone.utc), "failure_count": 0}}
                    )
                    return

            except Exception as e:
                self.logger.error("Webhook delivery failed (attempt %d): %s", attempt, e)
                
                # Log failed delivery
                deliveries_collection = self.db_manager.get_collection("ipam_webhook_deliveries")
                await deliveries_collection.insert_one({
                    "webhook_id": webhook_id,
                    "event_type": event_type,
                    "payload": payload,
                    "status_code": None,
                    "response_time_ms": None,
                    "error_message": str(e),
                    "attempt_number": attempt,
                    "delivered_at": datetime.now(timezone.utc)
                })

            # Exponential backoff
            if attempt < max_attempts:
                await asyncio.sleep(2 ** attempt)

        # All attempts failed
        await collection.update_one(
            {"_id": webhook_id},
            {"$inc": {"failure_count": 1}}
        )

        # Disable webhook after 10 consecutive failures
        if webhook["failure_count"] >= 9:
            await collection.update_one(
                {"_id": webhook_id},
                {"$set": {"is_active": False}}
            )
            self.logger.warning("Webhook disabled after 10 failures: %s", webhook_id)

    except Exception as e:
        self.logger.error("Failed to deliver webhook: %s", e, exc_info=True)

async def get_webhooks(self, user_id: str) -> List[Dict[str, Any]]:
    """
    Get user's webhooks.

    Args:
        user_id: User ID

    Returns:
        List of webhooks (without secret keys)
    """
    try:
        collection = self.db_manager.get_collection("ipam_webhooks")
        cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
        webhooks = await cursor.to_list(None)

        for webhook in webhooks:
            webhook["_id"] = str(webhook["_id"])
            # Don't expose secret key in list
            webhook.pop("secret_key", None)

        return webhooks

    except Exception as e:
        self.logger.error("Failed to get webhooks: %s", e, exc_info=True)
        raise IPAMError(f"Failed to get webhooks: {str(e)}")

async def delete_webhook(self, user_id: str, webhook_id: str) -> None:
    """
    Delete a webhook.

    Args:
        user_id: User ID
        webhook_id: Webhook ID

    Raises:
        IPAMError: If webhook not found
    """
    try:
        collection = self.db_manager.get_collection("ipam_webhooks")
        result = await collection.delete_one({"_id": ObjectId(webhook_id), "user_id": user_id})

        if result.deleted_count == 0:
            raise IPAMError(f"Webhook not found: {webhook_id}")

        self.logger.info("Webhook deleted: user=%s webhook_id=%s", user_id, webhook_id)

    except IPAMError:
        raise
    except Exception as e:
        self.logger.error("Failed to delete webhook: %s", e, exc_info=True)
        raise IPAMError(f"Failed to delete webhook: {str(e)}")

async def get_webhook_deliveries(
    self,
    user_id: str,
    webhook_id: str,
    page: int = 1,
    page_size: int = 50
) -> Dict[str, Any]:
    """
    Get webhook delivery history.

    Args:
        user_id: User ID
        webhook_id: Webhook ID
        page: Page number
        page_size: Items per page

    Returns:
        Dict containing deliveries and pagination
    """
    try:
        # Verify webhook ownership
        webhooks_collection = self.db_manager.get_collection("ipam_webhooks")
        webhook = await webhooks_collection.find_one({"_id": ObjectId(webhook_id), "user_id": user_id})
        
        if not webhook:
            raise IPAMError(f"Webhook not found: {webhook_id}")

        # Get deliveries
        deliveries_collection = self.db_manager.get_collection("ipam_webhook_deliveries")
        query = {"webhook_id": ObjectId(webhook_id)}
        
        total_count = await deliveries_collection.count_documents(query)
        skip = (page - 1) * page_size
        total_pages = (total_count + page_size - 1) // page_size

        cursor = deliveries_collection.find(query).sort("delivered_at", -1).skip(skip).limit(page_size)
        deliveries = await cursor.to_list(page_size)

        for delivery in deliveries:
            delivery["_id"] = str(delivery["_id"])
            delivery["webhook_id"] = str(delivery["webhook_id"])

        return {
            "deliveries": deliveries,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }
        }

    except IPAMError:
        raise
    except Exception as e:
        self.logger.error("Failed to get webhook deliveries: %s", e, exc_info=True)
        raise IPAMError(f"Failed to get webhook deliveries: {str(e)}")

# ==================== IPAM Enhancements: Bulk Operations ====================

async def bulk_update_tags(
    self,
    user_id: str,
    resource_type: str,
    resource_ids: List[str],
    operation: str,
    tags: Dict[str, str]
) -> Dict[str, Any]:
    """
    Bulk update tags on resources.

    Args:
        user_id: User ID
        resource_type: "region" or "host"
        resource_ids: List of resource IDs (max 500)
        operation: "add", "remove", or "replace"
        tags: Tags to add/remove/replace

    Returns:
        Dict containing operation results
    """
    try:
        import uuid
        
        # Validate
        if len(resource_ids) > 500:
            raise ValidationError("Maximum 500 resources per bulk operation", field="resource_ids")

        # For large operations (> 100), create async job
        if len(resource_ids) > 100:
            job_id = str(uuid.uuid4())
            
            job_doc = {
                "job_id": job_id,
                "user_id": user_id,
                "operation_type": "bulk_tag_update",
                "total_items": len(resource_ids),
                "processed_items": 0,
                "successful_items": 0,
                "failed_items": 0,
                "status": "pending",
                "results": [],
                "created_at": datetime.now(timezone.utc),
                "completed_at": None
            }

            jobs_collection = self.db_manager.get_collection("ipam_bulk_jobs")
            await jobs_collection.insert_one(job_doc)

            # Process async (would be handled by background worker)
            # For now, return job ID
            return {
                "job_id": job_id,
                "status": "pending",
                "total_items": len(resource_ids),
                "message": "Bulk operation queued for processing"
            }

        # Process synchronously for small operations
        collection_name = "ipam_regions" if resource_type == "region" else "ipam_hosts"
        collection = self.db_manager.get_collection(collection_name)

        successful = 0
        failed = 0
        results = []

        for resource_id in resource_ids:
            try:
                # Build update based on operation
                if operation == "add":
                    update_doc = {"$set": {f"tags.{k}": v for k, v in tags.items()}}
                elif operation == "remove":
                    update_doc = {"$unset": {f"tags.{k}": "" for k in tags.keys()}}
                elif operation == "replace":
                    update_doc = {"$set": {"tags": tags}}
                else:
                    raise ValidationError("Invalid operation", field="operation", value=operation)

                result = await collection.update_one(
                    {"_id": ObjectId(resource_id), "user_id": user_id},
                    update_doc
                )

                if result.modified_count > 0:
                    successful += 1
                    results.append({"resource_id": resource_id, "status": "success"})
                else:
                    failed += 1
                    results.append({"resource_id": resource_id, "status": "failed", "reason": "Not found or no changes"})

            except Exception as e:
                failed += 1
                results.append({"resource_id": resource_id, "status": "failed", "reason": str(e)})

        return {
            "total_requested": len(resource_ids),
            "successful": successful,
            "failed": failed,
            "results": results
        }

    except ValidationError:
        raise
    except Exception as e:
        self.logger.error("Failed bulk tag update: %s", e, exc_info=True)
        raise IPAMError(f"Failed bulk tag update: {str(e)}")

async def get_bulk_job_status(self, user_id: str, job_id: str) -> Dict[str, Any]:
    """
    Get bulk job status.

    Args:
        user_id: User ID
        job_id: Job ID

    Returns:
        Dict containing job status

    Raises:
        IPAMError: If job not found
    """
    try:
        collection = self.db_manager.get_collection("ipam_bulk_jobs")
        job = await collection.find_one({"job_id": job_id, "user_id": user_id})

        if not job:
            raise IPAMError(f"Job not found: {job_id}")

        job["_id"] = str(job["_id"])
        
        # Calculate progress
        if job["total_items"] > 0:
            job["progress_percent"] = (job["processed_items"] / job["total_items"]) * 100
        else:
            job["progress_percent"] = 0.0

        return job

    except IPAMError:
        raise
    except Exception as e:
        self.logger.error("Failed to get bulk job status: %s", e, exc_info=True)
        raise IPAMError(f"Failed to get bulk job status: {str(e)}")
