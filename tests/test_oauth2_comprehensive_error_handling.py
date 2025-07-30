"""
Comprehensive tests for OAuth2 browser error handling (Task 8).

This test suite verifies:
- Browser-friendly error responses for OAuth2 errors
- Error page templates for common OAuth2 error scenarios
- Error logging for browser-based OAuth2 flows
- User guidance in error messages
- Proper error codes and descriptions
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# Import the components we're testing
from src.second_brain_database.routes.oauth2.error_handler import (
    OAuth2ErrorHandler,
    OAuth2ErrorCode,
    OAuth2ErrorSeverity,
    oauth2_error_handler,
    invalid_request_error,
    invalid_client_error
)
from src.second_brain_database.routes.oauth2.browser_error_logger import (
    BrowserErrorLogger,
    browser_error_logger
)
from src.second_brain_database.routes.oauth2.templates import (
    render_generic_oauth2_error,
    render_authorization_failed_error,
    render_oauth2_authorization_error,
    render_session_expired_error
)


class TestOAuth2ErrorHandler:
    """Test OAuth2 error handler functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = OAuth2ErrorHandler()
        self.mock_request = Mock(spec=Request)
        self.mock_request.method = "GET"
        self.mock_request.url = Mock()
        self.mock_request.url.path = "/oauth2/authorize"
        self.mock_request.url.__str__ = Mock(return_value="https://example.com/oauth2/authorize")
        self.mock_request.client = Mock()
        self.mock_request.client.host = "192.168.1.1"
        self.mock_request.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        self.mock_request.query_params = {}
    
    def test_browser_error_response(self):
        """Test browser-friendly error response generation."""
        response = self.error_handler.browser_error(
            error_code=OAuth2ErrorCode.INVALID_REQUEST,
            error_description="Missing required parameter: client_id",
            client_id="test_client",
            client_name="Test Application",
            request=self.mock_request,
            severity=OAuth2ErrorSeverity.LOW
        )
        
        assert isinstance(response, HTMLResponse)
        assert response.status_code == 400
        assert "Invalid Authorization Request" in response.body.decode()
        assert "Test Application" in response.body.decode()
        assert "🔒 Secure" in response.body.decode()
    
    def test_authorization_error_with_redirect(self):
        """Test authorization error with redirect URI."""
        response = self.error_handler.authorization_error(
            error_code=OAuth2ErrorCode.ACCESS_DENIED,
            error_description="User denied access",
            redirect_uri="https://client.example.com/callback",
            state="test_state",
            client_id="test_client",
            request=self.mock_request
        )
        
        assert isinstance(response, RedirectResponse)
        assert response.status_code == 302
        assert "error=access_denied" in response.headers["location"]
        assert "state=test_state" in response.headers["location"]
    
    def test_authorization_error_browser_fallback(self):
        """Test authorization error falls back to browser page when no redirect URI."""
        response = self.error_handler.authorization_error(
            error_code=OAuth2ErrorCode.INVALID_CLIENT,
            error_description="Client not found",
            redirect_uri=None,
            client_id="test_client",
            client_name="Test App",
            request=self.mock_request,
            is_browser_request=True
        )
        
        assert isinstance(response, HTMLResponse)
        assert "Application Not Found" in response.body.decode()
        assert "Test App" in response.body.decode()
    
    def test_token_error_response(self):
        """Test token endpoint error response."""
        response = self.error_handler.token_error(
            error_code=OAuth2ErrorCode.INVALID_GRANT,
            error_description="Authorization code has expired",
            client_id="test_client",
            request=self.mock_request
        )
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
        content = response.body.decode()
        assert "invalid_grant" in content
        assert "Authorization code has expired" in content
    
    def test_security_error_enhanced_logging(self):
        """Test security error with enhanced logging."""
        with patch('src.second_brain_database.routes.oauth2.error_handler.logger') as mock_logger:
            response = self.error_handler.security_error(
                error_code=OAuth2ErrorCode.INVALID_CLIENT,
                error_description="Suspicious client behavior detected",
                client_id="malicious_client",
                request=self.mock_request,
                security_event_type="client_abuse"
            )
            
            assert isinstance(response, JSONResponse)
            assert response.status_code == 400
            
            # Verify enhanced logging was called
            mock_logger.error.assert_called()
            call_args = mock_logger.error.call_args
            assert "security_event" in str(call_args)
    
    def test_user_friendly_messages(self):
        """Test user-friendly error message generation."""
        # Test with client name
        message = self.error_handler._get_user_friendly_message(
            OAuth2ErrorCode.INVALID_CLIENT, 
            "My Test App"
        )
        assert "My Test App" in message
        assert "not properly configured" in message
        
        # Test without client name
        message = self.error_handler._get_user_friendly_message(
            OAuth2ErrorCode.RATE_LIMIT_EXCEEDED
        )
        assert "Too many authorization attempts" in message
    
    def test_error_severity_mapping(self):
        """Test HTTP status code mapping for different error codes."""
        assert self.error_handler._get_http_status_code(OAuth2ErrorCode.INVALID_REQUEST) == 400
        assert self.error_handler._get_http_status_code(OAuth2ErrorCode.ACCESS_DENIED) == 403
        assert self.error_handler._get_http_status_code(OAuth2ErrorCode.RATE_LIMIT_EXCEEDED) == 429
        assert self.error_handler._get_http_status_code(OAuth2ErrorCode.SERVER_ERROR) == 500
    
    def test_troubleshooting_info_generation(self):
        """Test troubleshooting information generation."""
        info = self.error_handler._get_troubleshooting_info(OAuth2ErrorCode.INVALID_REQUEST)
        assert "Troubleshooting:" in info
        assert "correct authorization link" in info
        
        info = self.error_handler._get_troubleshooting_info(OAuth2ErrorCode.RATE_LIMIT_EXCEEDED)
        assert "Wait 5-10 minutes" in info


class TestBrowserErrorLogger:
    """Test browser-specific error logging functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.browser_logger = BrowserErrorLogger()
        self.mock_request = Mock(spec=Request)
        self.mock_request.method = "GET"
        self.mock_request.url = Mock()
        self.mock_request.url.path = "/oauth2/authorize"
        self.mock_request.url.scheme = "https"
        self.mock_request.url.__str__ = Mock(return_value="https://example.com/oauth2/authorize?client_id=test")
        self.mock_request.client = Mock()
        self.mock_request.client.host = "192.168.1.1"
        self.mock_request.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "origin": "https://client.example.com",
            "referer": "https://client.example.com/login",
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "navigate",
            "upgrade-insecure-requests": "1"
        }
        self.mock_request.query_params = {
            "client_id": "test_client",
            "response_type": "code",
            "redirect_uri": "https://client.example.com/callback"
        }
    
    @patch('src.second_brain_database.routes.oauth2.browser_error_logger.logger')
    def test_browser_oauth2_error_logging(self, mock_logger):
        """Test comprehensive browser OAuth2 error logging."""
        self.browser_logger.log_browser_oauth2_error(
            error_code=OAuth2ErrorCode.INVALID_REQUEST,
            error_description="Missing required parameter",
            request=self.mock_request,
            client_id="test_client",
            client_name="Test Application",
            user_id="user123",
            severity=OAuth2ErrorSeverity.MEDIUM
        )
        
        # Verify logging was called with appropriate level
        mock_logger.warning.assert_called_once()
        
        # Check log context
        call_args = mock_logger.warning.call_args
        log_message = call_args[0][0]
        log_context = call_args[1]["extra"]["browser_oauth2_context"]
        
        assert "Browser OAuth2 Error" in log_message
        assert "invalid_request" in log_message
        assert log_context["error_code"] == "invalid_request"
        assert log_context["client_id"] == "test_client"
        assert log_context["user_id"] == "user123"
        assert log_context["severity"] == "medium"
        assert "request_url" in log_context
        assert "user_agent" in log_context
    
    def test_browser_context_extraction(self):
        """Test browser context extraction from request."""
        context = self.browser_logger._extract_browser_context(self.mock_request)
        
        assert context["request_method"] == "GET"
        assert context["client_ip"] == "192.168.1.1"
        assert "Chrome" in context["user_agent"]
        assert context["origin"] == "https://client.example.com"
        assert context["sec_fetch_site"] == "cross-site"
        assert context["is_https"] == True
        assert context["security_context"]["cross_origin"] == True
    
    def test_user_agent_parsing(self):
        """Test user agent string parsing."""
        # Test Chrome
        chrome_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        parsed = self.browser_logger._parse_user_agent(chrome_ua)
        assert parsed["browser"] == "chrome"
        assert parsed["platform"] == "windows"
        assert parsed["mobile"] == False
        assert parsed["bot"] == False
        
        # Test mobile Safari
        mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        parsed = self.browser_logger._parse_user_agent(mobile_ua)
        assert parsed["browser"] == "safari"
        assert parsed["platform"] == "ios"
        assert parsed["mobile"] == True
        
        # Test bot
        bot_ua = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        parsed = self.browser_logger._parse_user_agent(bot_ua)
        assert parsed["bot"] == True
    
    def test_oauth2_flow_context_extraction(self):
        """Test OAuth2 flow context extraction."""
        context = self.browser_logger._extract_oauth2_flow_context(
            self.mock_request, None, "test_client", "Test App"
        )
        
        assert context["oauth2_flow_stage"] == "authorization"
        assert context["oauth2_parameters"]["client_id"] == "test_client"
        assert context["oauth2_parameters"]["response_type"] == "code"
        assert context["oauth2_client_context"]["client_name"] == "Test App"
    
    def test_client_type_determination(self):
        """Test OAuth2 client type determination."""
        # Test PKCE (public client)
        self.mock_request.query_params = {"code_challenge": "test_challenge"}
        client_type = self.browser_logger._determine_client_type(self.mock_request, {"code_challenge": "test_challenge"})
        assert client_type == "public_spa"
        
        # Test mobile
        self.mock_request.headers = {"user-agent": "MyApp/1.0 (iPhone; iOS 14.0)"}
        client_type = self.browser_logger._determine_client_type(self.mock_request, {})
        assert client_type == "mobile_app"
        
        # Test server-to-server
        self.mock_request.headers = {"accept": "application/json", "user-agent": "MyServer/1.0"}
        client_type = self.browser_logger._determine_client_type(self.mock_request, {})
        assert client_type == "server_to_server"
    
    @patch('src.second_brain_database.routes.oauth2.browser_error_logger.logger')
    def test_browser_oauth2_success_logging(self, mock_logger):
        """Test successful OAuth2 browser event logging."""
        self.browser_logger.log_browser_oauth2_success(
            event_type="authorization_granted",
            request=self.mock_request,
            client_id="test_client",
            user_id="user123",
            performance_metrics={"total_duration_ms": 1500}
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Browser OAuth2 Success: authorization_granted" in call_args[0][0]


class TestErrorTemplates:
    """Test OAuth2 error template rendering."""
    
    def test_generic_oauth2_error_template(self):
        """Test generic OAuth2 error template rendering."""
        html = render_generic_oauth2_error(
            title="Custom Error",
            message="This is a custom error message",
            icon="🚫",
            show_login_button=True,
            show_back_button=True,
            additional_info="<strong>Additional Info:</strong> Contact support"
        )
        
        assert "Custom Error" in html
        assert "This is a custom error message" in html
        assert "🚫" in html
        assert "Go Back" in html
        assert "Login" in html
        assert "Additional Info" in html
        assert "🔒 Secure" in html
    
    def test_authorization_failed_error_template(self):
        """Test authorization failed error template rendering."""
        html = render_authorization_failed_error(
            message="Authorization process failed",
            client_name="Test Application",
            error_details="Invalid client configuration",
            show_retry_button=True
        )
        
        assert "Authorization Failed" in html
        assert "Test Application" in html
        assert "Authorization process failed" in html
        assert "Invalid client configuration" in html
        assert "Retry" in html
        assert "Troubleshooting Steps" in html
    
    def test_oauth2_authorization_error_template(self):
        """Test OAuth2 authorization error template rendering."""
        html = render_oauth2_authorization_error(
            error_message="Client not found",
            error_details="The specified client ID does not exist",
            client_name="Unknown Client"
        )
        
        assert "OAuth2 Authorization Error" in html
        assert "Client not found" in html
        assert "Unknown Client" in html
        assert "The specified client ID does not exist" in html
        assert "What can you do?" in html
    
    def test_session_expired_error_template(self):
        """Test session expired error template rendering."""
        html = render_session_expired_error(
            message="Your session has expired",
            show_login_button=True
        )
        
        assert "Session Expired" in html
        assert "Your session has expired" in html
        assert "Login Again" in html


class TestConvenienceFunctions:
    """Test convenience functions for common error scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_request = Mock(spec=Request)
        self.mock_request.method = "GET"
        self.mock_request.url = Mock()
        self.mock_request.url.__str__ = Mock(return_value="https://example.com/oauth2/authorize")
        self.mock_request.client = Mock()
        self.mock_request.client.host = "192.168.1.1"
        self.mock_request.headers = {"user-agent": "Mozilla/5.0"}
    
    def test_invalid_request_error_with_redirect(self):
        """Test invalid_request_error with redirect URI."""
        response = invalid_request_error(
            description="Missing client_id parameter",
            redirect_uri="https://client.example.com/callback",
            state="test_state",
            request=self.mock_request
        )
        
        assert isinstance(response, RedirectResponse)
        assert "error=invalid_request" in response.headers["location"]
    
    def test_invalid_request_error_browser(self):
        """Test invalid_request_error for browser request."""
        response = invalid_request_error(
            description="Missing client_id parameter",
            is_browser_request=True,
            request=self.mock_request
        )
        
        assert isinstance(response, HTMLResponse)
        assert "Invalid Authorization Request" in response.body.decode()
    
    def test_invalid_client_error_browser(self):
        """Test invalid_client_error for browser request."""
        response = invalid_client_error(
            description="Client not found",
            is_browser_request=True,
            client_name="Test App",
            request=self.mock_request
        )
        
        assert isinstance(response, HTMLResponse)
        assert "Application Not Found" in response.body.decode()
        assert "Test App" in response.body.decode()


class TestErrorHandlerIntegration:
    """Test integration between error handler and browser logger."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_request = Mock(spec=Request)
        self.mock_request.method = "GET"
        self.mock_request.url = Mock()
        self.mock_request.url.path = "/oauth2/authorize"
        self.mock_request.url.__str__ = Mock(return_value="https://example.com/oauth2/authorize")
        self.mock_request.client = Mock()
        self.mock_request.client.host = "192.168.1.1"
        self.mock_request.headers = {"user-agent": "Mozilla/5.0"}
        self.mock_request.query_params = {}
    
    @patch('src.second_brain_database.routes.oauth2.error_handler.logger')
    def test_error_handler_logging_integration(self, mock_logger):
        """Test that error handler properly logs errors."""
        oauth2_error_handler.browser_error(
            error_code=OAuth2ErrorCode.INVALID_REQUEST,
            error_description="Test error",
            request=self.mock_request,
            severity=OAuth2ErrorSeverity.HIGH
        )
        
        # Verify logging was called
        mock_logger.error.assert_called_once()
        
        # Check that comprehensive context was logged
        call_args = mock_logger.error.call_args
        log_context = call_args[1]["extra"]["oauth2_context"]
        assert log_context["error_code"] == "invalid_request"
        assert log_context["severity"] == "high"
        assert "request_url" in log_context
    
    def test_global_instances_available(self):
        """Test that global instances are properly initialized."""
        assert oauth2_error_handler is not None
        assert browser_error_logger is not None
        assert isinstance(oauth2_error_handler, OAuth2ErrorHandler)
        assert isinstance(browser_error_logger, BrowserErrorLogger)


if __name__ == "__main__":
    # Run specific test for debugging
    import sys
    
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        pytest.main([f"-v", f"-k", test_name, __file__])
    else:
        pytest.main(["-v", __file__])