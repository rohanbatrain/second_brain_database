"""
WebRTC Content Security

Security utilities for WebRTC content validation and sanitization:
- XSS prevention (HTML/script sanitization)
- File upload validation (type, size, malware detection)
- IP-based access control
- Content filtering

Protects against malicious content and abuse.
"""

import re
import hashlib
from typing import Optional, List, Set, Tuple
from pathlib import Path

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[WebRTC-Security]")


# Allowed file types for sharing
ALLOWED_FILE_EXTENSIONS = {
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".rtf", ".odt", ".ods", ".odp",
    
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
    
    # Archives
    ".zip", ".tar", ".gz", ".7z", ".rar",
    
    # Media
    ".mp3", ".mp4", ".wav", ".m4a", ".webm", ".ogg",
    
    # Code/Data
    ".json", ".xml", ".csv", ".yml", ".yaml",
}

# Maximum file sizes (in bytes)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50 MB

# Blocked file extensions (executable, scripts, etc.)
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".pif", ".scr",
    ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".msi", ".msp", ".dll", ".sh", ".bash", ".zsh",
    ".app", ".deb", ".rpm", ".dmg", ".pkg",
}

# Suspicious file patterns (potential malware indicators)
SUSPICIOUS_PATTERNS = [
    b"<script",
    b"javascript:",
    b"eval(",
    b"document.cookie",
    b"<iframe",
    b"onerror=",
    b"onload=",
]

# IP blocklist (could be loaded from database/config)
IP_BLOCKLIST: Set[str] = set()

# Rate limit by IP
IP_RATE_LIMITS: dict = {}


class ContentSecurityError(Exception):
    """Base exception for content security violations."""
    pass


class FileValidationError(ContentSecurityError):
    """File validation failed."""
    pass


class MaliciousContentError(ContentSecurityError):
    """Malicious content detected."""
    pass


class IPBlockedError(ContentSecurityError):
    """IP address is blocked."""
    pass


def sanitize_text(text: str, max_length: int = 10000) -> str:
    """
    Sanitize text content to prevent XSS attacks.
    
    Args:
        text: Input text
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
        
    Raises:
        ContentSecurityError: If text contains malicious content
    """
    if not text:
        return ""
    
    # Enforce length limit
    if len(text) > max_length:
        text = text[:max_length]
    
    # Remove HTML tags (basic sanitization)
    # For production, use a library like bleach for comprehensive HTML sanitization
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove javascript: protocols
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    # Remove event handlers
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    # Check for suspicious patterns
    text_lower = text.lower()
    if any(pattern in text_lower for pattern in ['<script', 'javascript:', 'onerror=', 'onload=']):
        logger.warning(f"Suspicious content detected and sanitized")
    
    return text.strip()


def sanitize_html(html: str, max_length: int = 50000) -> str:
    """
    Sanitize HTML content (for rich text chat, etc.).
    
    For production, integrate bleach library:
    import bleach
    allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'a', 'p', 'br']
    allowed_attrs = {'a': ['href', 'title']}
    return bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs, strip=True)
    
    Args:
        html: Input HTML
        max_length: Maximum allowed length
        
    Returns:
        Sanitized HTML
    """
    if not html:
        return ""
    
    # Enforce length limit
    if len(html) > max_length:
        html = html[:max_length]
    
    # For now, strip all HTML (conservative approach)
    # In production, use bleach with whitelist of safe tags
    return sanitize_text(html, max_length)


def validate_file_upload(
    filename: str,
    file_size: int,
    content: Optional[bytes] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate file upload for security.
    
    Args:
        filename: Original filename
        file_size: File size in bytes
        content: Optional file content for scanning
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check filename
        if not filename or len(filename) > 255:
            return False, "Invalid filename"
        
        # Get file extension
        file_ext = Path(filename).suffix.lower()
        
        # Check if extension is blocked
        if file_ext in BLOCKED_EXTENSIONS:
            logger.warning(f"Blocked file extension: {file_ext}")
            return False, f"File type not allowed: {file_ext}"
        
        # Check if extension is in allowlist
        if file_ext not in ALLOWED_FILE_EXTENSIONS:
            logger.warning(f"File extension not in allowlist: {file_ext}")
            return False, f"File type not supported: {file_ext}"
        
        # Check file size
        if file_size > MAX_FILE_SIZE:
            return False, f"File too large (max {MAX_FILE_SIZE // (1024*1024)}MB)"
        
        # Image size check
        if file_ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
            if file_size > MAX_IMAGE_SIZE:
                return False, f"Image too large (max {MAX_IMAGE_SIZE // (1024*1024)}MB)"
        
        # Document size check
        if file_ext in {".pdf", ".doc", ".docx", ".xls", ".xlsx"}:
            if file_size > MAX_DOCUMENT_SIZE:
                return False, f"Document too large (max {MAX_DOCUMENT_SIZE // (1024*1024)}MB)"
        
        # Scan content if provided
        if content:
            is_safe, scan_error = scan_file_content(content, file_ext)
            if not is_safe:
                return False, scan_error
        
        return True, None
        
    except Exception as e:
        logger.error(f"File validation error: {e}")
        return False, "File validation failed"


def scan_file_content(content: bytes, file_ext: str) -> Tuple[bool, Optional[str]]:
    """
    Scan file content for malicious patterns.
    
    This is a basic implementation. For production, integrate:
    - ClamAV for antivirus scanning
    - VirusTotal API for cloud scanning
    - Custom pattern matching for your use case
    
    Args:
        content: File content bytes
        file_ext: File extension
        
    Returns:
        Tuple of (is_safe, error_message)
    """
    try:
        # Check for suspicious patterns in content
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern in content:
                logger.warning(f"Suspicious pattern detected in file: {pattern}")
                return False, "Potentially malicious content detected"
        
        # Check for embedded executables (PE header signature)
        if content[:2] == b'MZ':  # DOS/Windows executable header
            logger.warning("Executable detected in uploaded file")
            return False, "Executable content not allowed"
        
        # Check for embedded scripts in images/PDFs
        if file_ext in {".jpg", ".jpeg", ".png", ".pdf"}:
            if b'<script' in content or b'javascript:' in content:
                logger.warning("Embedded script detected in file")
                return False, "Embedded scripts not allowed"
        
        # File size sanity check
        if len(content) == 0:
            return False, "Empty file not allowed"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Content scan error: {e}")
        return False, "Content scan failed"


def calculate_file_checksum(content: bytes) -> str:
    """
    Calculate SHA-256 checksum of file content.
    
    Args:
        content: File content bytes
        
    Returns:
        Hex digest of SHA-256 hash
    """
    return hashlib.sha256(content).hexdigest()


def validate_room_id(room_id: str) -> bool:
    """
    Validate room ID format.
    
    Args:
        room_id: Room identifier
        
    Returns:
        True if valid
    """
    if not room_id:
        return False
    
    # Room ID rules:
    # - Length: 3-64 characters
    # - Allowed: alphanumeric, hyphens, underscores
    # - No special characters to prevent injection
    
    if len(room_id) < 3 or len(room_id) > 64:
        return False
    
    # Only allow safe characters
    if not re.match(r'^[a-zA-Z0-9_-]+$', room_id):
        return False
    
    return True


def validate_username(username: str) -> bool:
    """
    Validate username format.
    
    Args:
        username: Username to validate
        
    Returns:
        True if valid
    """
    if not username:
        return False
    
    # Username rules:
    # - Length: 3-50 characters
    # - Allowed: alphanumeric, hyphens, underscores, dots
    # - Must start with alphanumeric
    
    if len(username) < 3 or len(username) > 50:
        return False
    
    # Check pattern
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', username):
        return False
    
    return True


def check_ip_blocked(ip_address: str) -> bool:
    """
    Check if IP address is blocked.
    
    Args:
        ip_address: IP address to check
        
    Returns:
        True if blocked
    """
    if not ip_address:
        return False
    
    # Check global blocklist
    if ip_address in IP_BLOCKLIST:
        logger.warning(f"Blocked IP attempted access: {ip_address}")
        return True
    
    # TODO: Check against database/external blocklists
    
    return False


def add_ip_to_blocklist(ip_address: str, reason: Optional[str] = None):
    """
    Add IP address to blocklist.
    
    Args:
        ip_address: IP address to block
        reason: Optional reason for blocking
    """
    IP_BLOCKLIST.add(ip_address)
    logger.warning(
        f"IP added to blocklist: {ip_address}",
        extra={"ip": ip_address, "reason": reason}
    )
    
    # TODO: Persist to database


def remove_ip_from_blocklist(ip_address: str):
    """
    Remove IP address from blocklist.
    
    Args:
        ip_address: IP address to unblock
    """
    IP_BLOCKLIST.discard(ip_address)
    logger.info(f"IP removed from blocklist: {ip_address}")
    
    # TODO: Update database


def get_client_ip(headers: dict, default: str = "unknown") -> str:
    """
    Extract client IP from request headers.
    
    Checks X-Forwarded-For, X-Real-IP, etc. for proxied requests.
    
    Args:
        headers: Request headers dict
        default: Default value if IP not found
        
    Returns:
        Client IP address
    """
    # Check common proxy headers
    for header in ['x-forwarded-for', 'x-real-ip', 'cf-connecting-ip']:
        if header in headers:
            ip = headers[header].split(',')[0].strip()
            if ip:
                return ip
    
    return default


# Security headers to add to responses
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
}


def get_security_headers() -> dict:
    """
    Get security headers to add to all responses.
    
    Returns:
        Dictionary of security headers
    """
    return SECURITY_HEADERS.copy()
