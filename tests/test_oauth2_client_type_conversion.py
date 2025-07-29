"""
Unit tests for OAuth2 client type conversion utility.

This module tests the get_client_type_string function to ensure it properly handles
type conversion between ClientType enum objects and string values, with appropriate
error handling for invalid inputs.
"""

import logging
import pytest
from unittest.mock import patch

from second_brain_database.routes.oauth2.models import ClientType
from second_brain_database.routes.oauth2.utils import get_client_type_string


class TestGetClientTypeString:
    """Test cases for the get_client_type_string utility function."""

    def test_convert_confidential_enum_to_string(self):
        """Test conversion of ClientType.CONFIDENTIAL enum to string."""
        result = get_client_type_string(ClientType.CONFIDENTIAL)
        assert result == "confidential"
        assert isinstance(result, str)

    def test_convert_public_enum_to_string(self):
        """Test conversion of ClientType.PUBLIC enum to string."""
        result = get_client_type_string(ClientType.PUBLIC)
        assert result == "public"
        assert isinstance(result, str)

    def test_passthrough_valid_confidential_string(self):
        """Test passthrough of valid 'confidential' string value."""
        result = get_client_type_string("confidential")
        assert result == "confidential"
        assert isinstance(result, str)

    def test_passthrough_valid_public_string(self):
        """Test passthrough of valid 'public' string value."""
        result = get_client_type_string("public")
        assert result == "public"
        assert isinstance(result, str)

    def test_error_handling_invalid_string_values(self):
        """Test error handling for invalid string values."""
        invalid_strings = [
            "invalid",
            "CONFIDENTIAL",  # Wrong case
            "PUBLIC",        # Wrong case
            "private",       # Wrong value
            "client",        # Wrong value
            "",              # Empty string
            " confidential", # Leading space
            "confidential ", # Trailing space
            "conf idential", # Space in middle
        ]
        
        for invalid_string in invalid_strings:
            with pytest.raises(ValueError) as exc_info:
                get_client_type_string(invalid_string)
            
            # Verify error message contains expected information
            error_msg = str(exc_info.value)
            assert "Invalid client_type value" in error_msg
            assert invalid_string in error_msg
            assert "confidential" in error_msg
            assert "public" in error_msg

    def test_error_handling_none_input(self):
        """Test error handling for None input."""
        with pytest.raises(ValueError) as exc_info:
            get_client_type_string(None)
        
        error_msg = str(exc_info.value)
        assert "client_type cannot be None" in error_msg

    def test_error_handling_non_string_non_enum_inputs(self):
        """Test error handling for non-string/non-enum inputs."""
        invalid_inputs = [
            123,           # Integer
            12.34,         # Float
            True,          # Boolean
            False,         # Boolean
            [],            # List
            {},            # Dict
            set(),         # Set
            object(),      # Generic object
        ]
        
        for invalid_input in invalid_inputs:
            with pytest.raises(TypeError) as exc_info:
                get_client_type_string(invalid_input)
            
            # Verify error message contains expected information
            error_msg = str(exc_info.value)
            assert "client_type must be a ClientType enum or string" in error_msg
            assert str(type(invalid_input)) in error_msg

    def test_function_is_type_safe(self):
        """Test that function maintains type safety and returns consistent types."""
        # Test with enum inputs
        confidential_result = get_client_type_string(ClientType.CONFIDENTIAL)
        public_result = get_client_type_string(ClientType.PUBLIC)
        
        assert isinstance(confidential_result, str)
        assert isinstance(public_result, str)
        
        # Test with string inputs
        confidential_str_result = get_client_type_string("confidential")
        public_str_result = get_client_type_string("public")
        
        assert isinstance(confidential_str_result, str)
        assert isinstance(public_str_result, str)
        
        # Verify consistency between enum and string inputs
        assert confidential_result == confidential_str_result
        assert public_result == public_str_result

    def test_function_handles_all_enum_values(self):
        """Test that function handles all defined ClientType enum values."""
        # Get all enum values dynamically to ensure test stays current
        for client_type in ClientType:
            result = get_client_type_string(client_type)
            assert result == client_type.value
            assert isinstance(result, str)
            
            # Also test the string equivalent
            string_result = get_client_type_string(client_type.value)
            assert string_result == client_type.value
            assert result == string_result

    def test_error_message_format_for_invalid_strings(self):
        """Test that error messages for invalid strings are properly formatted."""
        with pytest.raises(ValueError) as exc_info:
            get_client_type_string("invalid_value")
        
        error_msg = str(exc_info.value)
        
        # Check that error message includes all required information
        assert "Invalid client_type value: 'invalid_value'" in error_msg
        assert "Must be one of:" in error_msg
        assert "'confidential'" in error_msg
        assert "'public'" in error_msg

    def test_error_message_format_for_type_errors(self):
        """Test that error messages for type errors are properly formatted."""
        with pytest.raises(TypeError) as exc_info:
            get_client_type_string(42)
        
        error_msg = str(exc_info.value)
        
        # Check that error message includes type information
        assert "client_type must be a ClientType enum or string" in error_msg
        assert "got <class 'int'>" in error_msg


class TestClientTypeConversionLogging:
    """Test cases for logging functionality in client type conversion."""

    @patch('second_brain_database.routes.oauth2.utils.logger')
    def test_successful_enum_conversion_logging(self, mock_logger):
        """Test that successful enum to string conversion is logged at debug level."""
        result = get_client_type_string(ClientType.CONFIDENTIAL)
        
        # Verify the conversion worked
        assert result == "confidential"
        
        # Verify debug logging was called
        mock_logger.debug.assert_called_once()
        
        # Check the log message content
        call_args = mock_logger.debug.call_args
        log_message = call_args[0][0]
        log_extra = call_args[1]['extra']
        
        assert "Client type conversion successful: enum to string" in log_message
        assert log_extra['operation'] == 'client_type_conversion'
        assert log_extra['original_type'] == 'ClientType'
        assert log_extra['converted_value'] == 'confidential'
        assert log_extra['conversion_type'] == 'enum_to_string'
        assert log_extra['success'] is True

    @patch('second_brain_database.routes.oauth2.utils.logger')
    def test_successful_string_passthrough_logging(self, mock_logger):
        """Test that successful string passthrough is logged at debug level."""
        result = get_client_type_string("public")
        
        # Verify the conversion worked
        assert result == "public"
        
        # Verify debug logging was called
        mock_logger.debug.assert_called_once()
        
        # Check the log message content
        call_args = mock_logger.debug.call_args
        log_message = call_args[0][0]
        log_extra = call_args[1]['extra']
        
        assert "Client type conversion successful: string passthrough" in log_message
        assert log_extra['operation'] == 'client_type_conversion'
        assert log_extra['original_type'] == 'str'
        assert log_extra['converted_value'] == 'public'
        assert log_extra['conversion_type'] == 'string_passthrough'
        assert log_extra['success'] is True

    @patch('second_brain_database.routes.oauth2.utils.logger')
    def test_none_input_error_logging(self, mock_logger):
        """Test that None input errors are logged at error level."""
        with pytest.raises(ValueError):
            get_client_type_string(None)
        
        # Verify error logging was called
        mock_logger.error.assert_called_once()
        
        # Check the log message content
        call_args = mock_logger.error.call_args
        log_message = call_args[0][0]
        log_extra = call_args[1]['extra']
        
        assert "Client type conversion failed: client_type cannot be None" in log_message
        assert log_extra['operation'] == 'client_type_conversion'
        assert log_extra['original_value'] is None
        assert log_extra['original_type'] == 'NoneType'
        assert log_extra['error_type'] == 'ValueError'
        assert log_extra['security_relevant'] is True

    @patch('second_brain_database.routes.oauth2.utils.logger')
    def test_invalid_string_error_logging(self, mock_logger):
        """Test that invalid string values are logged at error level."""
        with pytest.raises(ValueError):
            get_client_type_string("invalid")
        
        # Verify error logging was called
        mock_logger.error.assert_called_once()
        
        # Check the log message content
        call_args = mock_logger.error.call_args
        log_message = call_args[0][0]
        log_extra = call_args[1]['extra']
        
        assert "Client type conversion failed: invalid string value 'invalid'" in log_message
        assert log_extra['operation'] == 'client_type_conversion'
        assert log_extra['original_value'] == 'invalid'
        assert log_extra['original_type'] == 'str'
        assert log_extra['valid_values'] == ['confidential', 'public']
        assert log_extra['error_type'] == 'ValueError'
        assert log_extra['security_relevant'] is True

    @patch('second_brain_database.routes.oauth2.utils.logger')
    def test_invalid_type_error_logging(self, mock_logger):
        """Test that invalid types are logged at error level."""
        with pytest.raises(TypeError):
            get_client_type_string(123)
        
        # Verify error logging was called
        mock_logger.error.assert_called_once()
        
        # Check the log message content
        call_args = mock_logger.error.call_args
        log_message = call_args[0][0]
        log_extra = call_args[1]['extra']
        
        assert "Client type conversion failed: invalid type int" in log_message
        assert log_extra['operation'] == 'client_type_conversion'
        assert log_extra['original_value'] == '123'
        assert log_extra['original_type'] == 'int'
        assert log_extra['expected_types'] == ['ClientType', 'str']
        assert log_extra['error_type'] == 'TypeError'
        assert log_extra['security_relevant'] is True

    @patch('second_brain_database.routes.oauth2.utils.logger')
    def test_logging_does_not_expose_sensitive_information(self, mock_logger):
        """Test that logging doesn't expose sensitive information."""
        # Test with various inputs to ensure no sensitive data is logged
        test_cases = [
            ClientType.CONFIDENTIAL,
            "public",
            "invalid_value"
        ]
        
        for test_input in test_cases:
            mock_logger.reset_mock()
            
            try:
                get_client_type_string(test_input)
            except (ValueError, TypeError):
                pass  # Expected for invalid inputs
            
            # Check all logging calls
            all_calls = mock_logger.debug.call_args_list + mock_logger.error.call_args_list
            
            for call in all_calls:
                if call:
                    log_message = call[0][0]
                    log_extra = call[1]['extra']
                    
                    # Ensure no sensitive patterns are logged
                    sensitive_patterns = [
                        'password', 'secret', 'token', 'key', 'credential',
                        'auth', 'session', 'cookie', 'jwt'
                    ]
                    
                    for pattern in sensitive_patterns:
                        assert pattern.lower() not in log_message.lower()
                        
                        # Check extra fields don't contain sensitive data
                        for key, value in log_extra.items():
                            if isinstance(value, str):
                                assert pattern.lower() not in value.lower()

    @patch('second_brain_database.routes.oauth2.utils.logger')
    def test_logging_structure_and_format(self, mock_logger):
        """Test that logging follows the correct structure and format."""
        # Test successful conversion
        get_client_type_string(ClientType.CONFIDENTIAL)
        
        # Verify debug logging was called with proper structure
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        
        # Verify log message is a string
        assert isinstance(call_args[0][0], str)
        
        # Verify extra data structure
        log_extra = call_args[1]['extra']
        required_fields = [
            'operation', 'original_value', 'original_type', 
            'converted_value', 'conversion_type', 'success'
        ]
        
        for field in required_fields:
            assert field in log_extra, f"Required field '{field}' missing from log extra data"
        
        # Verify field types and values
        assert log_extra['operation'] == 'client_type_conversion'
        assert isinstance(log_extra['success'], bool)
        assert log_extra['success'] is True