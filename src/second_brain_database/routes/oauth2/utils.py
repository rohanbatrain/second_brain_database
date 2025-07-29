"""
OAuth2 utility functions.

This module provides utility functions for OAuth2 operations, including type-safe
conversions and data validation helpers.
"""

from typing import Union

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.oauth2.models import ClientType

logger = get_logger(prefix="[OAuth2 Utils]")


def get_client_type_string(client_type: Union[ClientType, str]) -> str:
    """
    Convert ClientType to string representation safely.
    
    This function handles the type inconsistency issue where ClientType can be either
    an enum object or a string value depending on how it was deserialized by Pydantic.
    It provides type-safe conversion that works with both formats.
    
    Args:
        client_type: ClientType enum object or string value ("confidential" or "public")
        
    Returns:
        String representation of the client type ("confidential" or "public")
        
    Raises:
        ValueError: If client_type is not a valid ClientType value or is None
        TypeError: If client_type is not a string or ClientType enum
        
    Examples:
        >>> # With enum object
        >>> get_client_type_string(ClientType.CONFIDENTIAL)
        'confidential'
        
        >>> # With string value
        >>> get_client_type_string("public")
        'public'
        
        >>> # Error cases
        >>> get_client_type_string("invalid")
        ValueError: Invalid client_type value: 'invalid'. Must be 'confidential' or 'public'
        
        >>> get_client_type_string(None)
        ValueError: client_type cannot be None
        
        >>> get_client_type_string(123)
        TypeError: client_type must be a ClientType enum or string, got <class 'int'>
    """
    original_value = client_type
    original_type = type(client_type).__name__
    
    try:
        # Handle None input
        if client_type is None:
            logger.error(
                "Client type conversion failed: client_type cannot be None",
                extra={
                    "operation": "client_type_conversion",
                    "original_value": None,
                    "original_type": "NoneType",
                    "error_type": "ValueError",
                    "security_relevant": True
                }
            )
            raise ValueError("client_type cannot be None")
        
        # Handle ClientType enum object
        if isinstance(client_type, ClientType):
            converted_value = client_type.value
            logger.debug(
                "Client type conversion successful: enum to string",
                extra={
                    "operation": "client_type_conversion",
                    "original_value": str(client_type),
                    "original_type": original_type,
                    "converted_value": converted_value,
                    "conversion_type": "enum_to_string",
                    "success": True
                }
            )
            return converted_value
        
        # Handle string input
        if isinstance(client_type, str):
            # Validate that the string is a valid ClientType value
            valid_values = [ct.value for ct in ClientType]
            if client_type not in valid_values:
                logger.error(
                    f"Client type conversion failed: invalid string value '{client_type}'",
                    extra={
                        "operation": "client_type_conversion",
                        "original_value": client_type,
                        "original_type": original_type,
                        "valid_values": valid_values,
                        "error_type": "ValueError",
                        "security_relevant": True
                    }
                )
                raise ValueError(
                    f"Invalid client_type value: '{client_type}'. "
                    f"Must be one of: {', '.join(repr(v) for v in valid_values)}"
                )
            
            logger.debug(
                "Client type conversion successful: string passthrough",
                extra={
                    "operation": "client_type_conversion",
                    "original_value": client_type,
                    "original_type": original_type,
                    "converted_value": client_type,
                    "conversion_type": "string_passthrough",
                    "success": True
                }
            )
            return client_type
        
        # Handle invalid type
        logger.error(
            f"Client type conversion failed: invalid type {original_type}",
            extra={
                "operation": "client_type_conversion",
                "original_value": str(original_value),
                "original_type": original_type,
                "expected_types": ["ClientType", "str"],
                "error_type": "TypeError",
                "security_relevant": True
            }
        )
        raise TypeError(
            f"client_type must be a ClientType enum or string, got {type(client_type)}"
        )
        
    except Exception as e:
        # Log any unexpected errors during conversion
        if not isinstance(e, (ValueError, TypeError)):
            logger.error(
                f"Unexpected error during client type conversion: {str(e)}",
                extra={
                    "operation": "client_type_conversion",
                    "original_value": str(original_value),
                    "original_type": original_type,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "security_relevant": True
                },
                exc_info=True
            )
        raise