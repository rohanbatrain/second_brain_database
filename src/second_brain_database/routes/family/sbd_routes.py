"""
Family SBD token management routes.

This module provides REST API endpoints for managing family SBD token accounts,
spending permissions, and financial controls.
"""

from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from second_brain_database.managers.family_manager import (
    AccountFrozen,
    FamilyError,
    FamilyNotFound,
    InsufficientPermissions,
    SpendingLimitExceeded,
    family_manager,
)
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.routes.family.models import (
    FreezeAccountRequest,
    SBDAccountResponse,
    UpdateSpendingPermissionsRequest,
)

logger = get_logger(prefix="[Family SBD Routes]")

router = APIRouter(prefix="/family", tags=["Family SBD"])


@router.get("/{family_id}/sbd-account", response_model=SBDAccountResponse)
async def get_family_sbd_account(
    request: Request,
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> SBDAccountResponse:
    """
    Get family SBD account details including balance and spending permissions.
    
    Returns comprehensive information about the family's shared SBD token account,
    including current balance, spending permissions for all members, and recent transactions.
    
    **Rate Limiting:** 30 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    
    **Returns:**
    - SBD account information with permissions and transaction history
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_sbd_account_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )
    
    try:
        account_data = await family_manager.get_family_sbd_account(family_id, user_id)
        
        logger.debug("Retrieved SBD account for family %s by user %s", family_id, user_id)
        
        return SBDAccountResponse(
            account_username=account_data["account_username"],
            balance=account_data["balance"],
            is_frozen=account_data["is_frozen"],
            frozen_by=account_data.get("frozen_by"),
            frozen_at=account_data.get("frozen_at"),
            spending_permissions=account_data["spending_permissions"],
            notification_settings=account_data["notification_settings"],
            recent_transactions=account_data.get("recent_transactions", [])
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for SBD account request: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for SBD account access: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get family SBD account: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "SBD_ACCOUNT_RETRIEVAL_FAILED",
                "message": "Failed to retrieve SBD account information"
            }
        )


@router.put("/{family_id}/sbd-account/permissions")
async def update_spending_permissions(
    request: Request,
    family_id: str,
    permissions_request: UpdateSpendingPermissionsRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Update spending permissions for a family member.
    
    Allows family administrators to set spending limits and permissions
    for family members. Changes are logged and notifications are sent.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Target user must be a family member
    
    **Returns:**
    - Updated permission information
    """
    admin_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_update_permissions_{admin_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        # Perform the update
        await family_manager.update_spending_permissions(
            family_id,
            admin_id,
            permissions_request.user_id,
            {
                "spending_limit": permissions_request.spending_limit,
                "can_spend": permissions_request.can_spend
            }
        )

        # Retrieve full updated account to return to frontend (frontend expects full SBDAccount shape)
        account_data = await family_manager.get_family_sbd_account(family_id, admin_id)

        logger.info("Updated spending permissions for user %s in family %s by admin %s", 
                   permissions_request.user_id, family_id, admin_id)

        return JSONResponse(
            content=account_data,
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for permissions update: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for spending permissions update: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to update spending permissions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "PERMISSIONS_UPDATE_FAILED",
                "message": str(e)
            }
        )


@router.post("/{family_id}/sbd-account/freeze")
async def freeze_unfreeze_account(
    request: Request,
    family_id: str,
    freeze_request: FreezeAccountRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Freeze or unfreeze the family SBD account.
    
    Allows family administrators to temporarily freeze the shared account
    to prevent spending during disputes or emergencies. Deposits continue
    to work but all spending is blocked.
    
    **Rate Limiting:** 5 requests per hour per user
    
    **Requirements:**
    - User must be a family administrator
    - Reason required for freezing
    
    **Returns:**
    - Account freeze status and details
    """
    admin_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_freeze_account_{admin_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )
    
    try:
        if freeze_request.action == "freeze":
            result = await family_manager.freeze_family_account(
                family_id, admin_id, freeze_request.reason
            )
            message = "Family account frozen successfully"
        else:
            result = await family_manager.unfreeze_family_account(family_id, admin_id)
            message = "Family account unfrozen successfully"
        
        logger.info("Family account %s: %s by admin %s", 
                   freeze_request.action, family_id, admin_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": message,
                "data": {
                    "family_id": family_id,
                    "is_frozen": result["is_frozen"],
                    "frozen_by": result.get("frozen_by"),
                    "frozen_at": result.get("frozen_at").isoformat() if result.get("frozen_at") else None,
                    "reason": result.get("reason")
                }
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for account freeze: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for account freeze: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to %s family account: %s", freeze_request.action, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ACCOUNT_FREEZE_FAILED",
                "message": str(e)
            }
        )


@router.get("/{family_id}/sbd-account/transactions")
async def get_family_transactions(
    request: Request,
    family_id: str,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Get family SBD account transaction history.
    
    Returns paginated transaction history for the family's shared SBD account
    with member attribution and detailed transaction information.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    
    **Returns:**
    - Paginated transaction history with member details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_transactions_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        transactions_data = await family_manager.get_family_transactions(
            family_id, user_id, skip, limit
        )
        
        logger.debug("Retrieved %d transactions for family %s by user %s", 
                    len(transactions_data["transactions"]), family_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "data": {
                    "family_id": family_id,
                    "account_username": transactions_data["account_username"],
                    "current_balance": transactions_data["current_balance"],
                    "transactions": transactions_data["transactions"],
                    "pagination": {
                        "skip": skip,
                        "limit": limit,
                        "total": transactions_data["total_transactions"],
                        "has_more": transactions_data["has_more"]
                    }
                }
            },
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for transactions request: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for transaction history: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get family transactions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "TRANSACTIONS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve transaction history"
            }
        )


@router.post("/{family_id}/sbd-account/validate-spending")
async def validate_spending_permission(
    request: Request,
    family_id: str,
    amount: int,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Validate if the current user can spend the specified amount from family account.
    
    Checks spending permissions, limits, and account status before allowing
    a transaction. Used by the SBD token system for permission validation.
    
    **Rate Limiting:** 50 requests per hour per user
    
    **Requirements:**
    - User must be a family member
    - Amount must be positive
    
    **Returns:**
    - Validation result with detailed permission information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_validate_spending_{user_id}",
        rate_limit_requests=50,
        rate_limit_period=3600
    )
    
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_AMOUNT",
                "message": "Amount must be positive"
            }
        )
    
    try:
        # Get family account username for validation
        family_data = await family_manager.get_family_by_id(family_id)
        family_username = family_data["sbd_account"]["account_username"]
        
        # Validate spending permission
        can_spend = await family_manager.validate_family_spending(
            family_username, user_id, amount, {"request": request, "user": current_user}
        )
        
        # Get detailed permission information
        permissions = family_data["sbd_account"]["spending_permissions"].get(user_id, {})
        
        logger.debug("Spending validation for user %s in family %s: amount=%d, can_spend=%s", 
                    user_id, family_id, amount, can_spend)
        
        response_data = {
            "status": "success",
            "data": {
                "can_spend": can_spend,
                "amount": amount,
                "family_id": family_id,
                "account_username": family_username,
                "user_permissions": {
                    "spending_limit": permissions.get("spending_limit", 0),
                    "can_spend": permissions.get("can_spend", False),
                    "role": permissions.get("role", "member")
                },
                "account_status": {
                    "is_frozen": family_data["sbd_account"]["is_frozen"],
                    "current_balance": await family_manager.get_family_sbd_balance(family_username)
                }
            }
        }
        
        if not can_spend:
            # Determine the reason for denial
            if family_data["sbd_account"]["is_frozen"]:
                response_data["data"]["denial_reason"] = "ACCOUNT_FROZEN"
                response_data["data"]["denial_message"] = "Family account is currently frozen"
            elif not permissions.get("can_spend", False):
                response_data["data"]["denial_reason"] = "NO_SPENDING_PERMISSION"
                response_data["data"]["denial_message"] = "You don't have permission to spend from this family account"
            elif permissions.get("spending_limit", 0) != -1 and amount > permissions.get("spending_limit", 0):
                response_data["data"]["denial_reason"] = "SPENDING_LIMIT_EXCEEDED"
                response_data["data"]["denial_message"] = f"Amount exceeds your spending limit of {permissions.get('spending_limit', 0)} tokens"
            else:
                response_data["data"]["denial_reason"] = "INSUFFICIENT_BALANCE"
                response_data["data"]["denial_message"] = "Insufficient balance in family account"
        
        return JSONResponse(
            content=response_data,
            status_code=status.HTTP_200_OK
        )
        
    except FamilyNotFound:
        logger.warning("Family not found for spending validation: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for spending validation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to validate spending permission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "VALIDATION_FAILED",
                "message": "Failed to validate spending permission"
            }
        )


@router.get("/{family_id}/sbd-account/available-balance")
async def get_family_available_balance(
    request: Request,
    family_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    Get available balance information for a family SBD account.

    Returns comprehensive available balance information including total balance,
    available balance considering user permissions, account status, and spending limits.

    **Rate Limiting:** 30 requests per hour per user

    **Requirements:**
    - User must be a family member

    **Returns:**
    - Available balance information with permission details and account status
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"family_available_balance_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )

    try:
        available_balance_data = await family_manager.get_family_available_balance(family_id, user_id)

        logger.debug("Retrieved available balance for family %s by user %s: %d available of %d total",
                    family_id, user_id, available_balance_data["available_balance"],
                    available_balance_data["total_balance"])

        return JSONResponse(
            content={
                "status": "success",
                "data": available_balance_data
            },
            status_code=status.HTTP_200_OK
        )

    except FamilyNotFound:
        logger.warning("Family not found for available balance request: %s", family_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FAMILY_NOT_FOUND",
                "message": "Family not found"
            }
        )
    except InsufficientPermissions as e:
        logger.warning("Insufficient permissions for available balance access: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": str(e)
            }
        )
    except FamilyError as e:
        logger.error("Failed to get family available balance: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "AVAILABLE_BALANCE_RETRIEVAL_FAILED",
                "message": "Failed to retrieve available balance information"
            }
        )