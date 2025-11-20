"""
Validation utilities for IPAM (IP Address Management) system.

This module provides validation functions for IP addresses, octets, tags,
and other IPAM-specific data formats.
"""

import ipaddress
import re
from typing import Dict, List, Optional, Tuple


class IPAMValidation:
    """Centralized IPAM validation utilities."""

    # Validation patterns
    TAG_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
    TAG_VALUE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\s\.]+$")

    # IP address ranges
    PRIVATE_10_NETWORK = ipaddress.ip_network("10.0.0.0/8")

    @staticmethod
    def validate_ip_format(ip_address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate IP address is in 10.0.0.0/8 private address space.

        Args:
            ip_address: IP address string to validate

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
                - is_valid: True if valid, False otherwise
                - error_message: Error description if invalid, None if valid

        Examples:
            >>> validate_ip_format("10.5.23.45")
            (True, None)
            >>> validate_ip_format("192.168.1.1")
            (False, "IP address must be in 10.0.0.0/8 private address space")
            >>> validate_ip_format("invalid")
            (False, "Invalid IP address format")
        """
        try:
            # Parse IP address
            ip = ipaddress.ip_address(ip_address)

            # Check if it's in 10.0.0.0/8 range
            if ip not in IPAMValidation.PRIVATE_10_NETWORK:
                return False, "IP address must be in 10.0.0.0/8 private address space"

            # Verify first octet is 10
            octets = ip_address.split(".")
            if len(octets) != 4 or octets[0] != "10":
                return False, "IP address must start with 10"

            return True, None

        except ValueError:
            return False, "Invalid IP address format"

    @staticmethod
    def validate_octet_range(octet_value: int, octet_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate octet value is within valid range for its type.

        Args:
            octet_value: Integer value of the octet
            octet_type: Type of octet - "X", "Y", or "Z"

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
                - is_valid: True if valid, False otherwise
                - error_message: Error description if invalid, None if valid

        Validation Rules:
            - X octet: 0-255 (country level)
            - Y octet: 0-255 (region level)
            - Z octet: 1-254 (host level, excluding 0 and 255)

        Examples:
            >>> validate_octet_range(5, "X")
            (True, None)
            >>> validate_octet_range(0, "Z")
            (False, "Z octet must be between 1 and 254 (excluding network and broadcast addresses)")
            >>> validate_octet_range(256, "Y")
            (False, "Y octet must be between 0 and 255")
        """
        octet_type = octet_type.upper()

        if octet_type not in ["X", "Y", "Z"]:
            return False, f"Invalid octet type: {octet_type}. Must be X, Y, or Z"

        # X and Y octets: 0-255
        if octet_type in ["X", "Y"]:
            if not isinstance(octet_value, int):
                return False, f"{octet_type} octet must be an integer"
            if octet_value < 0 or octet_value > 255:
                return False, f"{octet_type} octet must be between 0 and 255"
            return True, None

        # Z octet: 1-254 (excluding 0 and 255)
        if octet_type == "Z":
            if not isinstance(octet_value, int):
                return False, "Z octet must be an integer"
            if octet_value < 1 or octet_value > 254:
                return False, "Z octet must be between 1 and 254 (excluding network and broadcast addresses)"
            return True, None

        return False, "Unknown validation error"

    @staticmethod
    def validate_tag_format(tags: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate tag keys and values follow naming conventions.

        Args:
            tags: Dictionary of tag key-value pairs

        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
                - is_valid: True if all tags valid, False otherwise
                - error_messages: List of validation errors (empty if valid)

        Validation Rules:
            - Tag keys: alphanumeric, underscore, hyphen only
            - Tag values: alphanumeric, underscore, hyphen, space, dot
            - Max key length: 100 characters
            - Max value length: 500 characters
            - Max tags per resource: 50

        Examples:
            >>> validate_tag_format({"environment": "production", "tier": "1"})
            (True, [])
            >>> validate_tag_format({"env@prod": "value"})
            (False, ["Tag key 'env@prod' contains invalid characters..."])
        """
        errors = []

        if not isinstance(tags, dict):
            return False, ["Tags must be a dictionary"]

        if len(tags) > 50:
            errors.append("Maximum 50 tags allowed per resource")
            return False, errors

        for key, value in tags.items():
            # Validate key
            if not isinstance(key, str):
                errors.append(f"Tag key must be a string, got {type(key).__name__}")
                continue

            if not key:
                errors.append("Tag key cannot be empty")
                continue

            if len(key) > 100:
                errors.append(f"Tag key '{key}' exceeds maximum length of 100 characters")

            if not IPAMValidation.TAG_KEY_PATTERN.match(key):
                errors.append(
                    f"Tag key '{key}' contains invalid characters. "
                    "Only alphanumeric characters, underscores, and hyphens are allowed"
                )

            # Validate value
            if not isinstance(value, str):
                errors.append(f"Tag value for key '{key}' must be a string, got {type(value).__name__}")
                continue

            if len(value) > 500:
                errors.append(f"Tag value for key '{key}' exceeds maximum length of 500 characters")

            if not IPAMValidation.TAG_VALUE_PATTERN.match(value):
                errors.append(
                    f"Tag value for key '{key}' contains invalid characters. "
                    "Only alphanumeric characters, underscores, hyphens, spaces, and dots are allowed"
                )

        return len(errors) == 0, errors

    @staticmethod
    def validate_cidr_format(cidr: str) -> Tuple[bool, Optional[str]]:
        """
        Validate CIDR notation format.

        Args:
            cidr: CIDR notation string (e.g., "10.5.23.0/24")

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)

        Examples:
            >>> validate_cidr_format("10.5.23.0/24")
            (True, None)
            >>> validate_cidr_format("10.5.23.0/33")
            (False, "Invalid CIDR prefix length")
        """
        try:
            network = ipaddress.ip_network(cidr, strict=False)

            # Check if it's in 10.0.0.0/8 range
            if not network.subnet_of(IPAMValidation.PRIVATE_10_NETWORK):
                return False, "CIDR must be within 10.0.0.0/8 private address space"

            return True, None

        except ValueError as e:
            return False, f"Invalid CIDR format: {str(e)}"

    @staticmethod
    def parse_ip_octets(ip_address: str) -> Tuple[bool, Optional[Tuple[int, int, int, int]], Optional[str]]:
        """
        Parse IP address into individual octets.

        Args:
            ip_address: IP address string

        Returns:
            Tuple[bool, Optional[Tuple[int, int, int, int]], Optional[str]]:
                - is_valid: True if valid, False otherwise
                - octets: Tuple of (first, x, y, z) octets if valid, None otherwise
                - error_message: Error description if invalid, None if valid

        Examples:
            >>> parse_ip_octets("10.5.23.45")
            (True, (10, 5, 23, 45), None)
            >>> parse_ip_octets("192.168.1.1")
            (False, None, "IP address must be in 10.0.0.0/8 private address space")
        """
        # First validate the IP format
        is_valid, error = IPAMValidation.validate_ip_format(ip_address)
        if not is_valid:
            return False, None, error

        try:
            # Split into octets
            parts = ip_address.split(".")
            if len(parts) != 4:
                return False, None, "IP address must have exactly 4 octets"

            # Convert to integers
            octets = tuple(int(part) for part in parts)

            # Validate first octet is 10
            if octets[0] != 10:
                return False, None, "First octet must be 10"

            return True, octets, None

        except ValueError:
            return False, None, "Invalid octet values"

    @staticmethod
    def validate_hostname_format(hostname: str) -> Tuple[bool, Optional[str]]:
        """
        Validate hostname follows RFC 1123 conventions.

        Args:
            hostname: Hostname string to validate

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)

        Validation Rules:
            - Max length: 253 characters
            - Labels separated by dots
            - Each label: 1-63 characters
            - Alphanumeric and hyphens only
            - Cannot start or end with hyphen
            - Case-insensitive

        Examples:
            >>> validate_hostname_format("web-server-01")
            (True, None)
            >>> validate_hostname_format("-invalid")
            (False, "Hostname cannot start or end with a hyphen")
        """
        if not hostname:
            return False, "Hostname cannot be empty"

        if len(hostname) > 253:
            return False, "Hostname exceeds maximum length of 253 characters"

        # Split into labels
        labels = hostname.split(".")

        for label in labels:
            if not label:
                return False, "Hostname labels cannot be empty"

            if len(label) > 63:
                return False, f"Hostname label '{label}' exceeds maximum length of 63 characters"

            if label.startswith("-") or label.endswith("-"):
                return False, "Hostname labels cannot start or end with a hyphen"

            if not all(c.isalnum() or c == "-" for c in label):
                return False, f"Hostname label '{label}' contains invalid characters"

        return True, None


# Convenience functions for backward compatibility and ease of use
def validate_ip_format(ip_address: str) -> Tuple[bool, Optional[str]]:
    """Validate IP address is in 10.0.0.0/8 private address space."""
    return IPAMValidation.validate_ip_format(ip_address)


def validate_octet_range(octet_value: int, octet_type: str) -> Tuple[bool, Optional[str]]:
    """Validate octet value is within valid range for its type."""
    return IPAMValidation.validate_octet_range(octet_value, octet_type)


def validate_tag_format(tags: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Validate tag keys and values follow naming conventions."""
    return IPAMValidation.validate_tag_format(tags)


def validate_cidr_format(cidr: str) -> Tuple[bool, Optional[str]]:
    """Validate CIDR notation format."""
    return IPAMValidation.validate_cidr_format(cidr)


def parse_ip_octets(ip_address: str) -> Tuple[bool, Optional[Tuple[int, int, int, int]], Optional[str]]:
    """Parse IP address into individual octets."""
    return IPAMValidation.parse_ip_octets(ip_address)


def validate_hostname_format(hostname: str) -> Tuple[bool, Optional[str]]:
    """Validate hostname follows RFC 1123 conventions."""
    return IPAMValidation.validate_hostname_format(hostname)
