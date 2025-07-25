"""
WebAuthn cryptographic operations for attestation and assertion parsing.

This module provides functionality for parsing WebAuthn attestation objects,
extracting public keys, verifying signatures, and handling CBOR data structures.
Follows existing validation patterns with comprehensive error handling and logging.
"""

import base64
import hashlib
import json
import struct
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.logging_utils import (
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(name="Second_Brain_Database_WebAuthn_Crypto", prefix="[WEBAUTHN-CRYPTO]")

# CBOR major types
CBOR_MAJOR_TYPE_UNSIGNED = 0
CBOR_MAJOR_TYPE_NEGATIVE = 1
CBOR_MAJOR_TYPE_BYTES = 2
CBOR_MAJOR_TYPE_TEXT = 3
CBOR_MAJOR_TYPE_ARRAY = 4
CBOR_MAJOR_TYPE_MAP = 5
CBOR_MAJOR_TYPE_TAG = 6
CBOR_MAJOR_TYPE_FLOAT = 7

# COSE algorithm identifiers
COSE_ALG_ES256 = -7  # ECDSA w/ SHA-256
COSE_ALG_RS256 = -257  # RSASSA-PKCS1-v1_5 w/ SHA-256

# COSE key types
COSE_KEY_TYPE_EC2 = 2  # Elliptic Curve Keys w/ x- and y-coordinate pair
COSE_KEY_TYPE_RSA = 3  # RSA Key

# COSE key parameters
COSE_KEY_PARAM_KTY = 1  # Key Type
COSE_KEY_PARAM_ALG = 3  # Algorithm
COSE_KEY_PARAM_CRV = -1  # Curve (for EC2 keys)
COSE_KEY_PARAM_X = -2  # X coordinate (for EC2 keys)
COSE_KEY_PARAM_Y = -3  # Y coordinate (for EC2 keys)
COSE_KEY_PARAM_N = -1  # Modulus (for RSA keys)
COSE_KEY_PARAM_E = -2  # Exponent (for RSA keys)


class CBORDecodeError(Exception):
    """Exception raised when CBOR decoding fails."""
    pass


class WebAuthnCryptoError(Exception):
    """Exception raised when WebAuthn cryptographic operations fail."""
    pass


@log_performance("cbor_decode")
def cbor_decode(data: bytes) -> Any:
    """
    Simplified CBOR decoder for WebAuthn attestation objects.
    
    This is a basic implementation that handles the CBOR structures
    commonly found in WebAuthn attestation objects. For production use,
    consider using a full CBOR library like cbor2.
    
    Args:
        data (bytes): CBOR encoded data
        
    Returns:
        Any: Decoded CBOR data
        
    Raises:
        CBORDecodeError: If CBOR decoding fails
    """
    logger.debug("Decoding CBOR data (%d bytes)", len(data))
    
    try:
        offset = 0
        result, _ = _cbor_decode_item(data, offset)
        logger.debug("Successfully decoded CBOR data")
        return result
    except Exception as e:
        logger.error("Failed to decode CBOR data: %s", e)
        log_error_with_context(
            e,
            context={"data_length": len(data), "data_preview": data[:50].hex()},
            operation="cbor_decode"
        )
        raise CBORDecodeError(f"CBOR decode failed: {str(e)}") from e


def _cbor_decode_item(data: bytes, offset: int) -> Tuple[Any, int]:
    """
    Decode a single CBOR item from data starting at offset.
    
    Args:
        data (bytes): CBOR data
        offset (int): Starting offset
        
    Returns:
        Tuple[Any, int]: Decoded item and new offset
        
    Raises:
        CBORDecodeError: If decoding fails
    """
    if offset >= len(data):
        raise CBORDecodeError("Unexpected end of CBOR data")
    
    initial_byte = data[offset]
    major_type = (initial_byte >> 5) & 0x07
    additional_info = initial_byte & 0x1f
    offset += 1
    
    # Decode length/value based on additional info
    if additional_info < 24:
        value = additional_info
    elif additional_info == 24:
        if offset >= len(data):
            raise CBORDecodeError("Unexpected end of CBOR data")
        value = data[offset]
        offset += 1
    elif additional_info == 25:
        if offset + 1 >= len(data):
            raise CBORDecodeError("Unexpected end of CBOR data")
        value = struct.unpack(">H", data[offset:offset+2])[0]
        offset += 2
    elif additional_info == 26:
        if offset + 3 >= len(data):
            raise CBORDecodeError("Unexpected end of CBOR data")
        value = struct.unpack(">I", data[offset:offset+4])[0]
        offset += 4
    elif additional_info == 27:
        if offset + 7 >= len(data):
            raise CBORDecodeError("Unexpected end of CBOR data")
        value = struct.unpack(">Q", data[offset:offset+8])[0]
        offset += 8
    else:
        raise CBORDecodeError(f"Unsupported additional info: {additional_info}")
    
    # Decode based on major type
    if major_type == CBOR_MAJOR_TYPE_UNSIGNED:
        return value, offset
    elif major_type == CBOR_MAJOR_TYPE_NEGATIVE:
        return -1 - value, offset
    elif major_type == CBOR_MAJOR_TYPE_BYTES:
        if offset + value > len(data):
            raise CBORDecodeError("Unexpected end of CBOR data")
        result = data[offset:offset+value]
        return result, offset + value
    elif major_type == CBOR_MAJOR_TYPE_TEXT:
        if offset + value > len(data):
            raise CBORDecodeError("Unexpected end of CBOR data")
        result = data[offset:offset+value].decode('utf-8')
        return result, offset + value
    elif major_type == CBOR_MAJOR_TYPE_ARRAY:
        result = []
        for _ in range(value):
            item, offset = _cbor_decode_item(data, offset)
            result.append(item)
        return result, offset
    elif major_type == CBOR_MAJOR_TYPE_MAP:
        result = {}
        for _ in range(value):
            key, offset = _cbor_decode_item(data, offset)
            val, offset = _cbor_decode_item(data, offset)
            result[key] = val
        return result, offset
    elif major_type == CBOR_MAJOR_TYPE_FLOAT:
        if additional_info == 20:  # False
            return False, offset
        elif additional_info == 21:  # True
            return True, offset
        elif additional_info == 22:  # Null
            return None, offset
        else:
            raise CBORDecodeError(f"Unsupported float/simple value: {additional_info}")
    else:
        raise CBORDecodeError(f"Unsupported major type: {major_type}")


@log_performance("parse_attestation_object")
def parse_attestation_object(attestation_object_b64: str) -> Dict[str, Any]:
    """
    Parse WebAuthn attestation object and extract key components.
    
    Args:
        attestation_object_b64 (str): Base64url encoded attestation object
        
    Returns:
        Dict[str, Any]: Parsed attestation object with extracted components
        
    Raises:
        WebAuthnCryptoError: If parsing fails
    """
    logger.info("Parsing WebAuthn attestation object")
    
    try:
        # Decode base64url
        attestation_object_bytes = base64.urlsafe_b64decode(attestation_object_b64 + '==')
        logger.debug("Decoded attestation object (%d bytes)", len(attestation_object_bytes))
        
        # Decode CBOR
        attestation_object = cbor_decode(attestation_object_bytes)
        
        if not isinstance(attestation_object, dict):
            raise WebAuthnCryptoError("Attestation object is not a CBOR map")
        
        # Extract required fields
        fmt = attestation_object.get("fmt")
        auth_data = attestation_object.get("authData")
        att_stmt = attestation_object.get("attStmt", {})
        
        if not fmt:
            raise WebAuthnCryptoError("Missing 'fmt' field in attestation object")
        if not auth_data:
            raise WebAuthnCryptoError("Missing 'authData' field in attestation object")
        
        logger.debug("Attestation format: %s", fmt)
        
        # Parse authenticator data
        parsed_auth_data = parse_authenticator_data(auth_data)
        
        result = {
            "fmt": fmt,
            "authData": parsed_auth_data,
            "attStmt": att_stmt,
            "raw_attestation_object": attestation_object
        }
        
        logger.info("Successfully parsed attestation object (format: %s)", fmt)
        return result
        
    except Exception as e:
        logger.error("Failed to parse attestation object: %s", e)
        log_error_with_context(
            e,
            context={"attestation_object_length": len(attestation_object_b64)},
            operation="parse_attestation_object"
        )
        raise WebAuthnCryptoError(f"Attestation object parsing failed: {str(e)}") from e


@log_performance("parse_authenticator_data")
def parse_authenticator_data(auth_data: bytes) -> Dict[str, Any]:
    """
    Parse WebAuthn authenticator data structure.
    
    Args:
        auth_data (bytes): Raw authenticator data
        
    Returns:
        Dict[str, Any]: Parsed authenticator data
        
    Raises:
        WebAuthnCryptoError: If parsing fails
    """
    logger.debug("Parsing authenticator data (%d bytes)", len(auth_data))
    
    try:
        if len(auth_data) < 37:  # Minimum length for authenticator data
            raise WebAuthnCryptoError("Authenticator data too short")
        
        offset = 0
        
        # RP ID hash (32 bytes)
        rp_id_hash = auth_data[offset:offset+32]
        offset += 32
        
        # Flags (1 byte)
        flags_byte = auth_data[offset]
        offset += 1
        
        # Parse flags
        flags = {
            "user_present": bool(flags_byte & 0x01),
            "user_verified": bool(flags_byte & 0x04),
            "attested_credential_data": bool(flags_byte & 0x40),
            "extension_data": bool(flags_byte & 0x80)
        }
        
        # Signature counter (4 bytes)
        sign_count = struct.unpack(">I", auth_data[offset:offset+4])[0]
        offset += 4
        
        result = {
            "rp_id_hash": rp_id_hash,
            "flags": flags,
            "sign_count": sign_count,
            "raw_auth_data": auth_data
        }
        
        # Parse attested credential data if present
        if flags["attested_credential_data"]:
            if len(auth_data) < offset + 18:  # Minimum for AAGUID + credential ID length
                raise WebAuthnCryptoError("Insufficient data for attested credential data")
            
            # AAGUID (16 bytes)
            aaguid = auth_data[offset:offset+16]
            offset += 16
            
            # Credential ID length (2 bytes)
            cred_id_len = struct.unpack(">H", auth_data[offset:offset+2])[0]
            offset += 2
            
            if len(auth_data) < offset + cred_id_len:
                raise WebAuthnCryptoError("Insufficient data for credential ID")
            
            # Credential ID
            credential_id = auth_data[offset:offset+cred_id_len]
            offset += cred_id_len
            
            # Credential public key (CBOR encoded)
            if offset < len(auth_data):
                public_key_cbor = auth_data[offset:]
                try:
                    public_key = cbor_decode(public_key_cbor)
                    parsed_public_key = parse_cose_key(public_key)
                except Exception as e:
                    logger.warning("Failed to parse public key CBOR: %s", e)
                    parsed_public_key = None
            else:
                public_key_cbor = None
                parsed_public_key = None
            
            result["attested_credential_data"] = {
                "aaguid": aaguid,
                "credential_id": credential_id,
                "public_key_cbor": public_key_cbor,
                "public_key": parsed_public_key
            }
        
        logger.debug("Successfully parsed authenticator data")
        return result
        
    except Exception as e:
        logger.error("Failed to parse authenticator data: %s", e)
        log_error_with_context(
            e,
            context={"auth_data_length": len(auth_data)},
            operation="parse_authenticator_data"
        )
        raise WebAuthnCryptoError(f"Authenticator data parsing failed: {str(e)}") from e


@log_performance("parse_cose_key")
def parse_cose_key(cose_key: Dict[int, Any]) -> Dict[str, Any]:
    """
    Parse COSE key structure from WebAuthn credential.
    
    Args:
        cose_key (Dict[int, Any]): COSE key map
        
    Returns:
        Dict[str, Any]: Parsed key information
        
    Raises:
        WebAuthnCryptoError: If parsing fails
    """
    logger.debug("Parsing COSE key")
    
    try:
        if not isinstance(cose_key, dict):
            raise WebAuthnCryptoError("COSE key is not a map")
        
        # Extract key type
        key_type = cose_key.get(COSE_KEY_PARAM_KTY)
        algorithm = cose_key.get(COSE_KEY_PARAM_ALG)
        
        if key_type is None:
            raise WebAuthnCryptoError("Missing key type in COSE key")
        
        result = {
            "key_type": key_type,
            "algorithm": algorithm,
            "raw_cose_key": cose_key
        }
        
        if key_type == COSE_KEY_TYPE_EC2:
            # Elliptic Curve key
            curve = cose_key.get(COSE_KEY_PARAM_CRV)
            x_coord = cose_key.get(COSE_KEY_PARAM_X)
            y_coord = cose_key.get(COSE_KEY_PARAM_Y)
            
            if curve is None or x_coord is None or y_coord is None:
                raise WebAuthnCryptoError("Missing EC2 key parameters")
            
            result.update({
                "curve": curve,
                "x": x_coord,
                "y": y_coord,
                "key_format": "EC2"
            })
            
        elif key_type == COSE_KEY_TYPE_RSA:
            # RSA key
            modulus = cose_key.get(COSE_KEY_PARAM_N)
            exponent = cose_key.get(COSE_KEY_PARAM_E)
            
            if modulus is None or exponent is None:
                raise WebAuthnCryptoError("Missing RSA key parameters")
            
            result.update({
                "modulus": modulus,
                "exponent": exponent,
                "key_format": "RSA"
            })
            
        else:
            logger.warning("Unsupported key type: %s", key_type)
            result["key_format"] = "UNKNOWN"
        
        logger.debug("Successfully parsed COSE key (type: %s, format: %s)", key_type, result["key_format"])
        return result
        
    except Exception as e:
        logger.error("Failed to parse COSE key: %s", e)
        log_error_with_context(
            e,
            context={"cose_key_keys": list(cose_key.keys()) if isinstance(cose_key, dict) else None},
            operation="parse_cose_key"
        )
        raise WebAuthnCryptoError(f"COSE key parsing failed: {str(e)}") from e


@log_performance("extract_public_key_from_attestation")
def extract_public_key_from_attestation(attestation_object_b64: str) -> Dict[str, Any]:
    """
    Extract public key information from WebAuthn attestation object.
    
    This is the main function used by the registration service to extract
    the public key from a credential creation response.
    
    Args:
        attestation_object_b64 (str): Base64url encoded attestation object
        
    Returns:
        Dict[str, Any]: Extracted public key information
        
    Raises:
        WebAuthnCryptoError: If extraction fails
    """
    logger.info("Extracting public key from attestation object")
    
    try:
        # Parse the attestation object
        parsed_attestation = parse_attestation_object(attestation_object_b64)
        
        # Extract authenticator data
        auth_data = parsed_attestation["authData"]
        
        # Check if attested credential data is present
        if "attested_credential_data" not in auth_data:
            raise WebAuthnCryptoError("No attested credential data found in authenticator data")
        
        attested_cred_data = auth_data["attested_credential_data"]
        
        # Extract public key
        public_key = attested_cred_data.get("public_key")
        if not public_key:
            raise WebAuthnCryptoError("No public key found in attested credential data")
        
        # Extract additional metadata
        result = {
            "public_key": public_key,
            "credential_id": base64.urlsafe_b64encode(attested_cred_data["credential_id"]).decode().rstrip('='),
            "aaguid": attested_cred_data["aaguid"].hex() if attested_cred_data["aaguid"] else None,
            "sign_count": auth_data["sign_count"],
            "user_verified": auth_data["flags"]["user_verified"],
            "user_present": auth_data["flags"]["user_present"],
            "attestation_format": parsed_attestation["fmt"]
        }
        
        logger.info("Successfully extracted public key (format: %s, algorithm: %s)", 
                   public_key.get("key_format"), public_key.get("algorithm"))
        
        return result
        
    except Exception as e:
        logger.error("Failed to extract public key from attestation: %s", e)
        log_error_with_context(
            e,
            context={"attestation_object_length": len(attestation_object_b64)},
            operation="extract_public_key_from_attestation"
        )
        raise WebAuthnCryptoError(f"Public key extraction failed: {str(e)}") from e


@log_performance("parse_client_data_json")
def parse_client_data_json(client_data_json_b64: str) -> Dict[str, Any]:
    """
    Parse WebAuthn client data JSON.
    
    Args:
        client_data_json_b64 (str): Base64url encoded client data JSON
        
    Returns:
        Dict[str, Any]: Parsed client data
        
    Raises:
        WebAuthnCryptoError: If parsing fails
    """
    logger.debug("Parsing client data JSON")
    
    try:
        # Decode base64url
        client_data_bytes = base64.urlsafe_b64decode(client_data_json_b64 + '==')
        
        # Parse JSON
        client_data = json.loads(client_data_bytes.decode('utf-8'))
        
        # Validate required fields
        required_fields = ["type", "challenge", "origin"]
        missing_fields = [field for field in required_fields if field not in client_data]
        
        if missing_fields:
            raise WebAuthnCryptoError(f"Missing required fields in client data: {missing_fields}")
        
        logger.debug("Successfully parsed client data JSON (type: %s)", client_data.get("type"))
        return client_data
        
    except json.JSONDecodeError as e:
        logger.error("Failed to parse client data JSON: %s", e)
        raise WebAuthnCryptoError(f"Invalid client data JSON: {str(e)}") from e
    except Exception as e:
        logger.error("Failed to parse client data JSON: %s", e)
        log_error_with_context(
            e,
            context={"client_data_length": len(client_data_json_b64)},
            operation="parse_client_data_json"
        )
        raise WebAuthnCryptoError(f"Client data parsing failed: {str(e)}") from e


@log_performance("verify_signature_placeholder")
def verify_signature_placeholder(
    signature: bytes,
    signed_data: bytes,
    public_key: Dict[str, Any]
) -> bool:
    """
    Placeholder for WebAuthn signature verification.
    
    This is a simplified implementation that always returns True for demonstration.
    In production, this should implement proper cryptographic signature verification
    using libraries like cryptography or pycryptodome.
    
    Args:
        signature (bytes): Signature to verify
        signed_data (bytes): Data that was signed
        public_key (Dict[str, Any]): Public key for verification
        
    Returns:
        bool: True if signature is valid (always True in this placeholder)
    """
    logger.info("Verifying WebAuthn signature (PLACEHOLDER IMPLEMENTATION)")
    
    # Log security event for signature verification attempt
    log_security_event(
        event_type="webauthn_signature_verification_placeholder",
        success=True,
        details={
            "signature_length": len(signature),
            "signed_data_length": len(signed_data),
            "key_format": public_key.get("key_format"),
            "algorithm": public_key.get("algorithm"),
            "note": "This is a placeholder implementation that always returns True"
        }
    )
    
    # TODO: Implement actual signature verification
    # This would involve:
    # 1. Extracting the public key in the correct format
    # 2. Using the appropriate cryptographic library (e.g., cryptography)
    # 3. Verifying the signature against the signed data
    # 4. Handling different key types (EC2, RSA) and algorithms
    
    logger.warning("Using placeholder signature verification - always returns True")
    return True


def create_signed_data_for_assertion(
    auth_data: bytes,
    client_data_hash: bytes
) -> bytes:
    """
    Create the signed data for WebAuthn assertion verification.
    
    Args:
        auth_data (bytes): Authenticator data
        client_data_hash (bytes): SHA-256 hash of client data JSON
        
    Returns:
        bytes: Concatenated data that should be signed
    """
    logger.debug("Creating signed data for assertion verification")
    return auth_data + client_data_hash


def hash_client_data_json(client_data_json: str) -> bytes:
    """
    Create SHA-256 hash of client data JSON.
    
    Args:
        client_data_json (str): Client data JSON string
        
    Returns:
        bytes: SHA-256 hash
    """
    logger.debug("Hashing client data JSON")
    return hashlib.sha256(client_data_json.encode('utf-8')).digest()


# Export main functions for use by other modules
__all__ = [
    "parse_attestation_object",
    "extract_public_key_from_attestation", 
    "parse_client_data_json",
    "verify_signature_placeholder",
    "create_signed_data_for_assertion",
    "hash_client_data_json",
    "WebAuthnCryptoError",
    "CBORDecodeError"
]