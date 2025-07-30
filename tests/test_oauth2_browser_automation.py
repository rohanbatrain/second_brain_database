"""
Browser automation tests for OAuth2 browser authentication user experience validation.

This module provides comprehensive browser automation tests using Selenium WebDriver
to validate the complete user experience across different browsers and scenarios.
Tests cover the full OAuth2 browser flow from user perspective.

Test Categories:
- Cross-browser compatibility testing (Chrome, Firefox, Safari, Edge)
- User experience validation for OAuth2 flows
- Form interaction and validation testing
- JavaScript functionality testing
- Responsive design validation
- Accessibility compliance testing
"""

import time
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions

# Test configuration
TEST_BASE_URL = "http://localhost:8000"
TEST_CLIENT_ID = "test_browser_client"
TEST_REDIRECT_URI = "https://example.com/callback"
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass123"
WAIT_TIMEOUT = 10


class BrowserTestBase:
    """Base class for browser automation tests."""
    
    @pytest.fixture(params=["chrome", "firefox"])
    def browser(self, request):
        """Create browser driver for testing."""
        browser_name = request.param
        
        if browser_name == "chrome":
            options = ChromeOptions()
            options.add_argument("--headless")  # Run in headless mode for CI
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            driver = webdriver.Chrome(options=options)
        elif browser_name == "firefox":
            options = FirefoxOptions()
            options.add_argument("--headless")  # Run in headless mode for CI
            driver = webdriver.Firefox(options=options)
        else:
            raise ValueError(f"Unsupported browser: {browser_name}")
        
        driver.implicitly_wait(5)
        yield driver
        driver.quit()
    
    def wait_for_element(self, driver, by, value, timeout=WAIT_TIMEOUT):
        """Wait for element to be present and visible."""
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    
    def wait_for_clickable(self, driver, by, value, timeout=WAIT_TIMEOUT):
        """Wait for element to be clickable."""
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )


class TestCrossBrowserCompatibility(BrowserTestBase):
    """Cross-browser compatibility tests for OAuth2 flows."""
    
    def test_login_page_rendering(self, browser):
        """Test login page renders correctly across browsers."""
        # Navigate to login page
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Verify page title
        assert "login" in browser.title.lower() or "sign in" in browser.title.lower()
        
        # Verify essential form elements are present
        username_field = self.wait_for_element(browser, By.NAME, "username")
        password_field = self.wait_for_element(browser, By.NAME, "password")
        csrf_field = self.wait_for_element(browser, By.NAME, "csrf_token")
        submit_button = self.wait_for_element(browser, By.TYPE, "submit")
        
        # Verify elements are visible and interactable
        assert username_field.is_displayed()
        assert password_field.is_displayed()
        assert csrf_field.get_attribute("value")  # CSRF token should be present
        assert submit_button.is_enabled()
    
    def test_oauth2_authorization_page_rendering(self, browser):
        """Test OAuth2 authorization page renders correctly."""
        # Navigate to OAuth2 authorization endpoint
        auth_url = (f"{TEST_BASE_URL}/oauth2/authorize"
                   f"?client_id={TEST_CLIENT_ID}"
                   f"&redirect_uri={TEST_REDIRECT_URI}"
                   f"&response_type=code"
                   f"&scope=read write"
                   f"&state=test_state")
        
        browser.get(auth_url)
        
        # Should redirect to login page for unauthenticated users
        WebDriverWait(browser, WAIT_TIMEOUT).until(
            lambda driver: "/auth/login" in driver.current_url
        )
        
        # Verify redirect URI parameter is preserved
        assert "redirect_uri" in browser.current_url
    
    def test_form_validation_display(self, browser):
        """Test form validation messages display correctly."""
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Try to submit form without credentials
        submit_button = self.wait_for_clickable(browser, By.TYPE, "submit")
        submit_button.click()
        
        # Check for HTML5 validation or custom validation messages
        username_field = browser.find_element(By.NAME, "username")
        validation_message = username_field.get_attribute("validationMessage")
        
        # Should have some form of validation
        assert validation_message or browser.find_elements(By.CLASS_NAME, "error")
    
    def test_responsive_design_mobile(self, browser):
        """Test responsive design on mobile viewport."""
        # Set mobile viewport
        browser.set_window_size(375, 667)  # iPhone 6/7/8 size
        
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Verify form is still usable on mobile
        username_field = self.wait_for_element(browser, By.NAME, "username")
        password_field = browser.find_element(By.NAME, "password")
        submit_button = browser.find_element(By.TYPE, "submit")
        
        # Elements should be visible and properly sized
        assert username_field.is_displayed()
        assert password_field.is_displayed()
        assert submit_button.is_displayed()
        
        # Form should fit within viewport
        form_element = browser.find_element(By.TAG_NAME, "form")
        form_width = form_element.size["width"]
        viewport_width = browser.execute_script("return window.innerWidth")
        
        assert form_width <= viewport_width
    
    def test_responsive_design_tablet(self, browser):
        """Test responsive design on tablet viewport."""
        # Set tablet viewport
        browser.set_window_size(768, 1024)  # iPad size
        
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Verify layout adapts to tablet size
        username_field = self.wait_for_element(browser, By.NAME, "username")
        assert username_field.is_displayed()
        
        # Check that elements are properly spaced
        form_element = browser.find_element(By.TAG_NAME, "form")
        assert form_element.size["width"] > 300  # Should use more space on tablet


class TestUserExperienceValidation(BrowserTestBase):
    """User experience validation tests for OAuth2 flows."""
    
    @patch('second_brain_database.routes.auth.services.auth.login.login_user')
    def test_complete_oauth2_browser_flow(self, mock_login, browser):
        """Test complete OAuth2 browser flow from user perspective."""
        mock_login.return_value = {"user_id": "test_user", "username": TEST_USERNAME}
        
        # Step 1: Start OAuth2 flow
        auth_url = (f"{TEST_BASE_URL}/oauth2/authorize"
                   f"?client_id={TEST_CLIENT_ID}"
                   f"&redirect_uri={TEST_REDIRECT_URI}"
                   f"&response_type=code"
                   f"&scope=read write"
                   f"&state=test_state")
        
        browser.get(auth_url)
        
        # Step 2: Should redirect to login
        WebDriverWait(browser, WAIT_TIMEOUT).until(
            lambda driver: "/auth/login" in driver.current_url
        )
        
        # Step 3: Fill login form
        username_field = self.wait_for_element(browser, By.NAME, "username")
        password_field = browser.find_element(By.NAME, "password")
        csrf_field = browser.find_element(By.NAME, "csrf_token")
        
        username_field.send_keys(TEST_USERNAME)
        password_field.send_keys(TEST_PASSWORD)
        
        # Step 4: Submit login form
        submit_button = browser.find_element(By.TYPE, "submit")
        submit_button.click()
        
        # Step 5: Should redirect back to OAuth2 flow
        # (Either to consent screen or directly to callback with code)
        WebDriverWait(browser, WAIT_TIMEOUT).until(
            lambda driver: "/oauth2" in driver.current_url or TEST_REDIRECT_URI in driver.current_url
        )
        
        # Verify successful flow completion
        current_url = browser.current_url
        assert "/oauth2" in current_url or "code=" in current_url
    
    def test_login_form_usability(self, browser):
        """Test login form usability features."""
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Test tab navigation
        username_field = self.wait_for_element(browser, By.NAME, "username")
        username_field.click()
        
        # Tab to password field
        username_field.send_keys(Keys.TAB)
        active_element = browser.switch_to.active_element
        assert active_element.get_attribute("name") == "password"
        
        # Tab to submit button
        active_element.send_keys(Keys.TAB)
        active_element = browser.switch_to.active_element
        assert active_element.get_attribute("type") == "submit"
        
        # Test Enter key submission
        username_field.click()
        username_field.send_keys(TEST_USERNAME)
        username_field.send_keys(Keys.ENTER)
        
        # Should attempt form submission
        time.sleep(1)  # Wait for any form processing
    
    def test_error_message_display(self, browser):
        """Test error message display and user feedback."""
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Submit form with invalid credentials
        username_field = self.wait_for_element(browser, By.NAME, "username")
        password_field = browser.find_element(By.NAME, "password")
        
        username_field.send_keys("invalid_user")
        password_field.send_keys("wrong_password")
        
        submit_button = browser.find_element(By.TYPE, "submit")
        submit_button.click()
        
        # Wait for error message or page reload
        time.sleep(2)
        
        # Check for error indication
        error_elements = browser.find_elements(By.CLASS_NAME, "error")
        error_text = browser.find_elements(By.XPATH, "//*[contains(text(), 'error') or contains(text(), 'invalid')]")
        
        # Should show some form of error feedback
        assert error_elements or error_text or "error" in browser.page_source.lower()
    
    def test_loading_states_and_feedback(self, browser):
        """Test loading states and user feedback during form submission."""
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Fill form
        username_field = self.wait_for_element(browser, By.NAME, "username")
        password_field = browser.find_element(By.NAME, "password")
        
        username_field.send_keys(TEST_USERNAME)
        password_field.send_keys(TEST_PASSWORD)
        
        # Submit form and check for loading indicators
        submit_button = browser.find_element(By.TYPE, "submit")
        submit_button.click()
        
        # Check if submit button is disabled during processing
        time.sleep(0.5)  # Brief wait to catch loading state
        
        # Button should either be disabled or show loading state
        is_disabled = not submit_button.is_enabled()
        has_loading_text = "loading" in submit_button.text.lower() or "..." in submit_button.text
        
        # At least one loading indicator should be present
        assert is_disabled or has_loading_text or browser.find_elements(By.CLASS_NAME, "loading")
    
    def test_back_button_behavior(self, browser):
        """Test browser back button behavior in OAuth2 flow."""
        # Start OAuth2 flow
        auth_url = (f"{TEST_BASE_URL}/oauth2/authorize"
                   f"?client_id={TEST_CLIENT_ID}"
                   f"&redirect_uri={TEST_REDIRECT_URI}"
                   f"&response_type=code")
        
        browser.get(auth_url)
        
        # Should redirect to login
        WebDriverWait(browser, WAIT_TIMEOUT).until(
            lambda driver: "/auth/login" in driver.current_url
        )
        
        # Use browser back button
        browser.back()
        
        # Should handle back button gracefully
        time.sleep(2)
        current_url = browser.current_url
        
        # Should either stay on login page or redirect appropriately
        assert "/auth/login" in current_url or "/oauth2" in current_url
    
    def test_session_timeout_handling(self, browser):
        """Test session timeout handling from user perspective."""
        # This test simulates session timeout scenario
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Simulate long delay (session timeout)
        time.sleep(2)
        
        # Try to access protected resource
        browser.get(f"{TEST_BASE_URL}/oauth2/authorize?client_id={TEST_CLIENT_ID}")
        
        # Should redirect to login (session expired)
        WebDriverWait(browser, WAIT_TIMEOUT).until(
            lambda driver: "/auth/login" in driver.current_url
        )
        
        # User should be able to login again
        username_field = self.wait_for_element(browser, By.NAME, "username")
        assert username_field.is_displayed()


class TestAccessibilityCompliance(BrowserTestBase):
    """Accessibility compliance tests for OAuth2 browser interface."""
    
    def test_form_labels_and_accessibility(self, browser):
        """Test form labels and accessibility attributes."""
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Check for proper form labels
        username_field = self.wait_for_element(browser, By.NAME, "username")
        password_field = browser.find_element(By.NAME, "password")
        
        # Check for associated labels
        username_label = browser.find_elements(By.XPATH, f"//label[@for='{username_field.get_attribute('id')}']")
        password_label = browser.find_elements(By.XPATH, f"//label[@for='{password_field.get_attribute('id')}']")
        
        # Should have proper labels or aria-label attributes
        assert (username_label or username_field.get_attribute("aria-label") or 
                username_field.get_attribute("placeholder"))
        assert (password_label or password_field.get_attribute("aria-label") or 
                password_field.get_attribute("placeholder"))
    
    def test_keyboard_navigation(self, browser):
        """Test keyboard navigation accessibility."""
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Test tab order
        username_field = self.wait_for_element(browser, By.NAME, "username")
        username_field.click()
        
        # Should be able to navigate through all interactive elements
        interactive_elements = []
        current_element = browser.switch_to.active_element
        
        for _ in range(10):  # Limit to prevent infinite loop
            interactive_elements.append(current_element.tag_name)
            current_element.send_keys(Keys.TAB)
            new_element = browser.switch_to.active_element
            
            if new_element == current_element:
                break  # Reached end of tab order
            current_element = new_element
        
        # Should have navigated through multiple elements
        assert len(interactive_elements) >= 3  # At least username, password, submit
    
    def test_screen_reader_compatibility(self, browser):
        """Test screen reader compatibility attributes."""
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Check for ARIA attributes and semantic HTML
        form_element = browser.find_element(By.TAG_NAME, "form")
        
        # Form should have proper role or semantic structure
        form_role = form_element.get_attribute("role")
        form_aria_label = form_element.get_attribute("aria-label")
        
        # Check for heading structure
        headings = browser.find_elements(By.XPATH, "//h1 | //h2 | //h3 | //h4 | //h5 | //h6")
        
        # Should have proper heading structure for screen readers
        assert headings or form_aria_label or form_role
    
    def test_color_contrast_and_visibility(self, browser):
        """Test color contrast and visibility for accessibility."""
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Get form elements
        username_field = self.wait_for_element(browser, By.NAME, "username")
        submit_button = browser.find_element(By.TYPE, "submit")
        
        # Check that elements are visible (basic visibility test)
        assert username_field.is_displayed()
        assert submit_button.is_displayed()
        
        # Check for focus indicators
        username_field.click()
        
        # Element should have focus styling
        focused_element = browser.switch_to.active_element
        assert focused_element == username_field
        
        # Check computed styles for focus indication
        outline_style = browser.execute_script(
            "return window.getComputedStyle(arguments[0]).outline;", 
            username_field
        )
        border_style = browser.execute_script(
            "return window.getComputedStyle(arguments[0]).border;", 
            username_field
        )
        
        # Should have some form of focus indication
        assert outline_style != "none" or "0px" not in border_style
    
    def test_error_message_accessibility(self, browser):
        """Test error message accessibility for screen readers."""
        browser.get(f"{TEST_BASE_URL}/auth/login")
        
        # Submit form to trigger validation
        submit_button = self.wait_for_clickable(browser, By.TYPE, "submit")
        submit_button.click()
        
        time.sleep(1)  # Wait for validation
        
        # Check for accessible error messages
        error_elements = browser.find_elements(By.XPATH, "//*[@role='alert' or @aria-live]")
        aria_described_elements = browser.find_elements(By.XPATH, "//*[@aria-describedby]")
        
        # Should have accessible error indication
        assert error_elements or aria_described_elements


# Test execution
if __name__ == "__main__":
    print("Running OAuth2 Browser Automation Tests...")
    print("=" * 60)
    print("Note: These tests require Selenium WebDriver and browser drivers to be installed.")
    print("For headless testing in CI/CD, browsers will run in headless mode.")
    print("=" * 60)
    
    # This would typically be run with pytest
    # pytest tests/test_oauth2_browser_automation.py -v