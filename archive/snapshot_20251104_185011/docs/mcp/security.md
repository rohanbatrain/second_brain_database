# MCP Security Guide

## Overview

The FastMCP Gateway Integration implements a comprehensive security model designed for enterprise environments. This guide covers security architecture, configuration, best practices, and threat mitigation strategies.

## Security Architecture

### Multi-Layer Security Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Network Security (TLS, Firewall, Rate Limiting)         │
├─────────────────────────────────────────────────────────────┤
│ 2. Authentication (JWT, Permanent Tokens, WebAuthn)        │
├─────────────────────────────────────────────────────────────┤
│ 3. Authorization (RBAC, Permissions, Scopes)               │
├─────────────────────────────────────────────────────────────┤
│ 4. Input Validation (Pydantic, Sanitization)               │
├─────────────────────────────────────────────────────────────┤
│ 5. Audit & Monitoring (Logging, Alerting, Anomaly)         │
└─────────────────────────────────────────────────────────────┘
```

### Security Components

#### 1. Security Wrappers
- **Purpose**: Enforce authentication and authorization for all MCP tools
- **Implementation**: Decorator pattern integrating with existing auth systems
- **Features**: Rate limiting, input validation, audit logging

#### 2. Permission System
- **Model**: Role-based access control (RBAC) with fine-grained permissions
- **Scopes**: Tool-specific permission requirements
- **Inheritance**: Role-based permission inheritance

#### 3. Audit System
- **Coverage**: All MCP tool invocations and security events
- **Storage**: Structured logging with MongoDB audit collection
- **Retention**: Configurable retention policies for compliance

## Authentication Methods

### JWT Token Authentication

**Configuration:**
```bash
# JWT settings
JWT_SECRET_KEY=your-secure-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Usage in MCP Tools:**
```python
# Automatic JWT validation in security wrapper
@authenticated_tool(
    name="get_family_info",
    permissions=["family:read"]
)
async def get_family_info(family_id: str):
    # JWT automatically validated by security wrapper
    current_user = get_current_mcp_user()
    # Tool implementation...
```

**Security Features:**
- Automatic token expiration and refresh
- Secure token storage and transmission
- Token revocation support
- Audience and issuer validation

### Permanent Token Authentication

**Configuration:**
```bash
# Permanent token settings
PERMANENT_TOKEN_ENABLED=true
PERMANENT_TOKEN_PREFIX=sbd_
PERMANENT_TOKEN_LENGTH=32
```

**Usage:**
```python
# Permanent tokens for API integrations
headers = {
    "Authorization": "Bearer sbd_your_permanent_token_here"
}
```

**Security Features:**
- Long-lived tokens for service integrations
- Scoped permissions per token
- Token rotation and revocation
- Usage tracking and monitoring

### WebAuthn Support

**Configuration:**
```bash
# WebAuthn settings
WEBAUTHN_ENABLED=true
WEBAUTHN_RP_ID=yourdomain.com
WEBAUTHN_RP_NAME="Second Brain Database"
WEBAUTHN_REQUIRE_RESIDENT_KEY=false
```

**Security Features:**
- Passwordless authentication
- Hardware security key support
- Biometric authentication
- Phishing-resistant authentication

## Authorization Model

### Permission System

#### Core Permissions

```python
# Family permissions
FAMILY_PERMISSIONS = [
    "family:read",      # View family information
    "family:write",     # Modify family settings
    "family:admin",     # Administrative operations
    "family:create",    # Create new families
    "family:delete",    # Delete families
    "family:invite",    # Send invitations
    "family:token_request"  # Request SBD tokens
]

# User permissions
USER_PERMISSIONS = [
    "user:read",        # View user profiles
    "user:write",       # Modify user profiles
    "user:admin",       # User administration
    "user:security",    # Security settings
]

# Shop permissions
SHOP_PERMISSIONS = [
    "shop:browse",      # Browse shop items
    "shop:purchase",    # Make purchases
    "shop:refund",      # Process refunds
    "shop:admin",       # Shop administration
]

# System permissions
SYSTEM_PERMISSIONS = [
    "system:read",      # View system status
    "system:admin",     # System administration
    "system:monitor",   # Monitoring access
    "system:config",    # Configuration changes
]
```

#### Role-Based Access Control

```python
# Default roles and permissions
ROLES = {
    "member": [
        "family:read",
        "user:read", "user:write",
        "shop:browse", "shop:purchase"
    ],
    "admin": [
        "family:read", "family:write", "family:admin",
        "user:read", "user:write", "user:admin",
        "shop:browse", "shop:purchase", "shop:refund"
    ],
    "super_user": [
        "*"  # All permissions
    ]
}
```

### Permission Validation

```python
# Security wrapper implementation
async def validate_permissions(user_id: str, required_permissions: List[str]) -> bool:
    """Validate user has required permissions"""
    user_permissions = await get_user_permissions(user_id)
    
    for permission in required_permissions:
        if permission not in user_permissions and "*" not in user_permissions:
            return False
    
    return True

# Usage in tools
@authenticated_tool(
    name="delete_family",
    permissions=["family:delete", "family:admin"]
)
async def delete_family(family_id: str):
    # Permissions automatically validated
    pass
```

## Input Validation and Sanitization

### Pydantic Schema Validation

```python
# Input validation models
class FamilyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, regex=r'^[a-zA-Z0-9\s\-_]+$')
    description: Optional[str] = Field(None, max_length=500)
    
    @validator('name')
    def validate_name(cls, v):
        # Additional validation logic
        if any(word in v.lower() for word in PROHIBITED_WORDS):
            raise ValueError('Name contains prohibited content')
        return v.strip()

class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=30, regex=r'^[a-zA-Z0-9_]+$')
    email: Optional[EmailStr] = None
    
    @validator('username')
    def validate_username(cls, v):
        if v and is_username_taken(v):
            raise ValueError('Username already taken')
        return v
```

### SQL Injection Prevention

```python
# Safe database queries using parameterized queries
async def get_family_by_id(family_id: str) -> Optional[Family]:
    """Safe database query with parameter validation"""
    # Validate ObjectId format
    if not ObjectId.is_valid(family_id):
        raise ValueError("Invalid family ID format")
    
    # Use parameterized query
    family_doc = await db_manager.get_collection("families").find_one({
        "_id": ObjectId(family_id)
    })
    
    return Family(**family_doc) if family_doc else None
```

### XSS Prevention

```python
# HTML sanitization for user inputs
import bleach

def sanitize_html_input(text: str) -> str:
    """Sanitize HTML content to prevent XSS"""
    allowed_tags = ['b', 'i', 'u', 'em', 'strong']
    allowed_attributes = {}
    
    return bleach.clean(text, tags=allowed_tags, attributes=allowed_attributes)

# Usage in tools
@authenticated_tool(name="update_family_description")
async def update_family_description(family_id: str, description: str):
    # Sanitize input
    safe_description = sanitize_html_input(description)
    # Update family...
```

## Rate Limiting

### Configuration

```bash
# Rate limiting settings
MCP_RATE_LIMIT_ENABLED=true
MCP_RATE_LIMIT_REQUESTS=100
MCP_RATE_LIMIT_PERIOD=60

# Tool-specific rate limits
MCP_FAMILY_RATE_LIMIT=50
MCP_AUTH_RATE_LIMIT=20
MCP_SHOP_RATE_LIMIT=30
MCP_ADMIN_RATE_LIMIT=10
```

### Implementation

```python
# Rate limiting by action and user
RATE_LIMITS = {
    "family_read": {"requests": 100, "period": 60},
    "family_write": {"requests": 20, "period": 60},
    "family_admin": {"requests": 10, "period": 60},
    "auth_login": {"requests": 5, "period": 300},
    "password_reset": {"requests": 3, "period": 3600},
    "shop_purchase": {"requests": 10, "period": 60},
}

async def check_rate_limit(user_id: str, action: str) -> bool:
    """Check if user is within rate limits for action"""
    limit_config = RATE_LIMITS.get(action, {"requests": 60, "period": 60})
    
    # Use existing SecurityManager rate limiting
    return await security_manager.check_rate_limit(
        request=current_request,
        action=action,
        rate_limit_requests=limit_config["requests"],
        rate_limit_period=limit_config["period"]
    )
```

### Rate Limit Headers

```python
# Rate limit information in responses
{
    "X-RateLimit-Limit": "100",
    "X-RateLimit-Remaining": "95",
    "X-RateLimit-Reset": "1640995200",
    "X-RateLimit-Window": "60"
}
```

## Audit Logging

### Audit Event Types

```python
# Comprehensive audit event types
AUDIT_EVENTS = {
    # Authentication events
    "auth_success": "Successful authentication",
    "auth_failure": "Failed authentication attempt",
    "token_created": "New token created",
    "token_revoked": "Token revoked",
    
    # Authorization events
    "permission_granted": "Permission granted",
    "permission_denied": "Permission denied",
    "role_changed": "User role changed",
    
    # Tool execution events
    "tool_executed": "MCP tool executed",
    "tool_failed": "MCP tool execution failed",
    
    # Security events
    "rate_limit_exceeded": "Rate limit exceeded",
    "suspicious_activity": "Suspicious activity detected",
    "security_violation": "Security policy violation",
    
    # Administrative events
    "config_changed": "Configuration changed",
    "user_suspended": "User account suspended",
    "emergency_access": "Emergency access granted"
}
```

### Audit Log Structure

```python
# Structured audit log entry
class AuditLogEntry(BaseModel):
    timestamp: datetime
    event_type: str
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: str
    user_agent: str
    tool_name: Optional[str]
    parameters: Optional[Dict[str, Any]]
    result: Optional[str]
    error_message: Optional[str]
    security_context: Dict[str, Any]
    risk_score: Optional[int]

# Audit logging implementation
async def log_audit_event(
    event_type: str,
    user_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    parameters: Optional[Dict] = None,
    result: Optional[str] = None,
    error_message: Optional[str] = None,
    risk_score: Optional[int] = None
):
    """Log audit event with comprehensive context"""
    
    audit_entry = AuditLogEntry(
        timestamp=datetime.utcnow(),
        event_type=event_type,
        user_id=user_id,
        session_id=get_session_id(),
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
        tool_name=tool_name,
        parameters=sanitize_parameters(parameters),
        result=result,
        error_message=error_message,
        security_context=get_security_context(),
        risk_score=risk_score
    )
    
    # Store in audit collection
    await db_manager.get_collection("audit_log").insert_one(
        audit_entry.dict()
    )
    
    # Send to external SIEM if configured
    if settings.SIEM_ENABLED:
        await send_to_siem(audit_entry)
```

### Audit Query Examples

```python
# Query audit logs for security analysis
async def get_failed_auth_attempts(hours: int = 24) -> List[AuditLogEntry]:
    """Get failed authentication attempts in last N hours"""
    since = datetime.utcnow() - timedelta(hours=hours)
    
    cursor = db_manager.get_collection("audit_log").find({
        "event_type": "auth_failure",
        "timestamp": {"$gte": since}
    }).sort("timestamp", -1)
    
    return [AuditLogEntry(**doc) async for doc in cursor]

async def get_user_activity(user_id: str, days: int = 7) -> List[AuditLogEntry]:
    """Get user activity for last N days"""
    since = datetime.utcnow() - timedelta(days=days)
    
    cursor = db_manager.get_collection("audit_log").find({
        "user_id": user_id,
        "timestamp": {"$gte": since}
    }).sort("timestamp", -1)
    
    return [AuditLogEntry(**doc) async for doc in cursor]
```

## Threat Detection and Response

### Anomaly Detection

```python
# Behavioral anomaly detection
class AnomalyDetector:
    def __init__(self):
        self.baseline_metrics = {}
    
    async def detect_anomalies(self, user_id: str) -> List[str]:
        """Detect behavioral anomalies for user"""
        anomalies = []
        
        # Check request frequency
        recent_requests = await self.get_recent_requests(user_id, minutes=10)
        if len(recent_requests) > 100:  # Threshold
            anomalies.append("excessive_request_frequency")
        
        # Check geographic anomalies
        recent_ips = await self.get_recent_ips(user_id, hours=1)
        if len(set(recent_ips)) > 3:  # Multiple locations
            anomalies.append("geographic_anomaly")
        
        # Check tool usage patterns
        tool_usage = await self.get_tool_usage_pattern(user_id)
        if self.is_unusual_pattern(tool_usage):
            anomalies.append("unusual_tool_usage")
        
        return anomalies
    
    async def calculate_risk_score(self, user_id: str, context: Dict) -> int:
        """Calculate risk score for user action"""
        score = 0
        
        # Base score factors
        if context.get("new_ip"):
            score += 20
        if context.get("new_user_agent"):
            score += 15
        if context.get("admin_action"):
            score += 25
        if context.get("off_hours"):
            score += 10
        
        # Behavioral factors
        anomalies = await self.detect_anomalies(user_id)
        score += len(anomalies) * 15
        
        return min(score, 100)  # Cap at 100
```

### Automated Response

```python
# Automated security responses
class SecurityResponseManager:
    async def handle_security_event(self, event: AuditLogEntry):
        """Handle security events with automated responses"""
        
        if event.risk_score and event.risk_score > 80:
            await self.high_risk_response(event)
        elif event.risk_score and event.risk_score > 60:
            await self.medium_risk_response(event)
        
        # Specific event handling
        if event.event_type == "rate_limit_exceeded":
            await self.handle_rate_limit_violation(event)
        elif event.event_type == "auth_failure":
            await self.handle_auth_failure(event)
    
    async def high_risk_response(self, event: AuditLogEntry):
        """Response to high-risk events"""
        # Temporarily suspend user
        if event.user_id:
            await self.suspend_user_temporarily(event.user_id, minutes=30)
        
        # Block IP address
        await self.block_ip_temporarily(event.ip_address, minutes=60)
        
        # Send alert to security team
        await self.send_security_alert(event, severity="HIGH")
    
    async def medium_risk_response(self, event: AuditLogEntry):
        """Response to medium-risk events"""
        # Require additional authentication
        if event.user_id:
            await self.require_2fa_next_login(event.user_id)
        
        # Log for investigation
        await self.flag_for_investigation(event)
```

## Security Monitoring

### Real-time Monitoring

```python
# Security metrics collection
class SecurityMetrics:
    def __init__(self):
        self.metrics = {
            "auth_attempts": Counter(),
            "auth_failures": Counter(),
            "rate_limit_violations": Counter(),
            "permission_denials": Counter(),
            "high_risk_events": Counter()
        }
    
    async def record_auth_attempt(self, success: bool, user_id: str):
        """Record authentication attempt"""
        self.metrics["auth_attempts"].inc()
        if not success:
            self.metrics["auth_failures"].inc()
            
            # Check for brute force
            recent_failures = await self.get_recent_auth_failures(user_id)
            if len(recent_failures) > 5:
                await self.trigger_brute_force_alert(user_id)
    
    async def record_security_event(self, event_type: str, risk_score: int):
        """Record security event"""
        if risk_score > 70:
            self.metrics["high_risk_events"].inc()
        
        # Check thresholds
        await self.check_alert_thresholds()
```

### Alerting Configuration

```yaml
# alerting.yaml
alerts:
  - name: "High Authentication Failure Rate"
    condition: "auth_failure_rate > 0.1"
    window: "5m"
    severity: "warning"
    
  - name: "Excessive Rate Limit Violations"
    condition: "rate_limit_violations > 100"
    window: "1m"
    severity: "critical"
    
  - name: "High Risk Security Events"
    condition: "high_risk_events > 10"
    window: "10m"
    severity: "critical"
    
  - name: "Geographic Anomaly"
    condition: "geographic_anomaly_detected"
    severity: "warning"
```

## Security Best Practices

### Development Security

1. **Secure Coding Practices**
   ```python
   # Always validate inputs
   @authenticated_tool(name="update_user")
   async def update_user(user_data: UserUpdateRequest):
       # Input automatically validated by Pydantic
       pass
   
   # Use parameterized queries
   await collection.find_one({"_id": ObjectId(user_id)})
   
   # Sanitize outputs
   return sanitize_response(user_data)
   ```

2. **Secret Management**
   ```bash
   # Use environment variables for secrets
   SECRET_KEY=${SECRET_KEY}
   
   # Rotate secrets regularly
   JWT_SECRET_KEY=${JWT_SECRET_KEY_$(date +%Y%m)}
   
   # Use secret management services
   SECRET_KEY=$(aws secretsmanager get-secret-value --secret-id prod/jwt-key --query SecretString --output text)
   ```

3. **Dependency Security**
   ```bash
   # Regular security updates
   uv sync --upgrade
   
   # Security scanning
   safety check
   bandit -r src/
   
   # Dependency auditing
   pip-audit
   ```

### Deployment Security

1. **Container Security**
   ```dockerfile
   # Use non-root user
   RUN adduser --disabled-password --gecos '' appuser
   USER appuser
   
   # Minimal base image
   FROM python:3.11-slim
   
   # Security scanning
   RUN apt-get update && apt-get upgrade -y
   ```

2. **Network Security**
   ```bash
   # Firewall configuration
   ufw allow 8000/tcp
   ufw allow 3001/tcp from 10.0.0.0/8
   ufw deny 3001/tcp
   
   # TLS configuration
   ssl_protocols TLSv1.2 TLSv1.3;
   ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512;
   ```

3. **Monitoring and Alerting**
   ```bash
   # Log monitoring
   tail -f /var/log/mcp/security.log | grep "HIGH_RISK"
   
   # Metric monitoring
   curl -s http://localhost:8000/metrics | grep mcp_security
   
   # Health monitoring
   curl -f http://localhost:8000/health/security
   ```

### Operational Security

1. **Access Control**
   - Implement least privilege access
   - Regular access reviews and audits
   - Multi-factor authentication for admin access
   - Separate development and production environments

2. **Incident Response**
   - Documented incident response procedures
   - Regular security drills and testing
   - Automated alerting and escalation
   - Forensic logging and evidence preservation

3. **Compliance**
   - Regular security assessments
   - Compliance with relevant standards (SOC 2, ISO 27001)
   - Data protection and privacy controls
   - Regular penetration testing

## Security Configuration Examples

### High-Security Environment

```bash
# Maximum security configuration
MCP_SECURITY_ENABLED=true
MCP_REQUIRE_AUTH=true
MCP_AUDIT_ENABLED=true
MCP_DEBUG_MODE=false

# Strict rate limiting
MCP_RATE_LIMIT_ENABLED=true
MCP_RATE_LIMIT_REQUESTS=50
MCP_RATE_LIMIT_PERIOD=60

# Enhanced security features
MCP_IP_LOCKDOWN_ENABLED=true
MCP_USER_AGENT_LOCKDOWN_ENABLED=true
MCP_REQUIRE_2FA_FOR_ADMIN=true

# Restricted tool access
MCP_ADMIN_TOOLS_ENABLED=false
MCP_SYSTEM_TOOLS_ENABLED=false

# Enhanced monitoring
MCP_ANOMALY_DETECTION_ENABLED=true
MCP_REAL_TIME_ALERTS_ENABLED=true
```

### Development Environment

```bash
# Development-friendly security
MCP_SECURITY_ENABLED=true
MCP_DEBUG_MODE=true
MCP_AUDIT_ENABLED=true

# Relaxed rate limiting
MCP_RATE_LIMIT_ENABLED=false

# Development features
MCP_ADMIN_TOOLS_ENABLED=true
MCP_SYSTEM_TOOLS_ENABLED=true

# Monitoring
MCP_ANOMALY_DETECTION_ENABLED=false
```

This comprehensive security guide ensures the FastMCP Gateway Integration maintains enterprise-grade security while providing flexible configuration for different deployment scenarios.