# MCP Integration Test Suite

This directory contains comprehensive tests for the FastMCP gateway integration, covering unit tests, integration tests, and end-to-end workflows.

## Test Structure

### Unit Tests
- `test_mcp_security_wrappers.py` - Tests for MCP security decorators and wrappers
- `test_mcp_basic_validation.py` - Basic validation tests for MCP components

### Integration Tests  
- `test_mcp_tools_integration.py` - Integration tests for MCP tools with existing managers

### End-to-End Tests
- `test_mcp_end_to_end.py` - Complete workflow tests from authentication to audit

### Configuration
- `conftest.py` - Pytest configuration and fixtures for MCP tests

## Running Tests

### Prerequisites
Ensure you have the required dependencies installed:
```bash
uv sync --extra dev
```

### Running All MCP Tests
```bash
# Run all MCP tests
python -m pytest tests/test_mcp_*.py -v

# Run with coverage
python -m pytest tests/test_mcp_*.py --cov=src/second_brain_database/integrations/mcp --cov-report=html

# Run specific test categories
python -m pytest tests/test_mcp_*.py -m unit -v
python -m pytest tests/test_mcp_*.py -m integration -v
python -m pytest tests/test_mcp_*.py -m e2e -v
```

### Running Individual Test Files
```bash
# Security wrapper tests
python -m pytest tests/test_mcp_security_wrappers.py -v

# Integration tests
python -m pytest tests/test_mcp_tools_integration.py -v

# End-to-end tests
python -m pytest tests/test_mcp_end_to_end.py -v

# Basic validation (minimal dependencies)
python tests/test_mcp_basic_validation.py
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
- Test individual MCP components in isolation
- Mock all external dependencies
- Fast execution, no external services required
- Focus on security wrappers, context management, and error handling

### Integration Tests (`@pytest.mark.integration`)
- Test MCP tools integration with existing managers
- Test database and Redis integration
- Test authentication and authorization flows
- Verify proper dependency injection

### End-to-End Tests (`@pytest.mark.e2e`)
- Test complete MCP workflows
- Test concurrent operations
- Test error recovery and resilience
- Test performance under load

### Slow Tests (`@pytest.mark.slow`)
- Performance and load tests
- Long-running workflow tests
- Can be skipped for quick test runs: `pytest -m "not slow"`

## Test Coverage

The test suite covers:

### Security Components
- Authentication and authorization decorators
- Rate limiting functionality
- Audit logging and security events
- Permission validation
- Context management

### Tool Integration
- Family management tools
- Authentication tools
- Profile management tools
- Shop and asset tools
- Workspace tools
- Admin tools

### Server Management
- MCP server lifecycle
- Health checks and monitoring
- Error recovery and alerting
- Configuration validation

### Workflows
- Complete user workflows
- Multi-step operations
- Concurrent user scenarios
- Error handling and recovery
- Performance under load

## Mocking Strategy

Tests use comprehensive mocking to isolate components:

- **Settings**: Mock configuration values
- **Database**: Mock MongoDB operations
- **Redis**: Mock caching and rate limiting
- **Security Manager**: Mock authentication and authorization
- **Logging**: Mock audit and security logging
- **External Services**: Mock FastMCP and other dependencies

## Test Data

Tests use realistic but safe test data:

- Test user IDs with clear prefixes (`test_user_`, `e2e_user_`)
- Mock family and workspace data
- Sanitized parameters for security testing
- Performance test scenarios with controlled load

## Debugging Tests

### Verbose Output
```bash
python -m pytest tests/test_mcp_*.py -v -s
```

### Specific Test Method
```bash
python -m pytest tests/test_mcp_security_wrappers.py::TestMCPSecurityWrappers::test_secure_mcp_tool_with_valid_user -v
```

### Debug Mode
```bash
python -m pytest tests/test_mcp_*.py --pdb
```

### Test Coverage Report
```bash
python -m pytest tests/test_mcp_*.py --cov=src/second_brain_database/integrations/mcp --cov-report=term-missing
```

## Continuous Integration

Tests are designed to run in CI environments:

- No external service dependencies
- Comprehensive mocking
- Deterministic test data
- Reasonable execution time
- Clear pass/fail criteria

## Adding New Tests

When adding new MCP functionality:

1. Add unit tests for individual components
2. Add integration tests for manager interactions
3. Add end-to-end tests for complete workflows
4. Update this documentation
5. Ensure proper test categorization with markers

### Test Naming Convention
- `test_mcp_*` for MCP-specific tests
- `test_<component>_<functionality>` for specific features
- `test_<workflow>_workflow` for end-to-end scenarios

### Fixture Usage
Use provided fixtures for consistent test setup:
- `mock_settings` for configuration
- `sample_fastapi_user` for user context
- `mock_*_manager` for service mocking
- `event_loop` for async test support