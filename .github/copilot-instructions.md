# GitHub Copilot Instructions for Second Brain Database

## Project Overview
This is a comprehensive Second Brain Database application built with FastAPI, MongoDB, Redis, and modern Python practices. The application provides a robust backend for managing personal and family knowledge bases with advanced features like AI integration, MCP (Model Context Protocol) server, and comprehensive security.

## Key Architecture Components

### Configuration System (.sbd files)
- **Configuration Priority**: Environment variable `SECOND_BRAIN_DATABASE_CONFIG_PATH` → `.sbd` file → `.env` file → environment variables only
- **File Format**: Standard key=value pairs (same as .env files)
- **Security**: Never hardcode secrets; must be set via .sbd or environment variables
- **Validation**: Pydantic models enforce required fields at startup

### Core Technologies
- **Backend**: FastAPI with automatic OpenAPI documentation
- **Database**: MongoDB with Motor async driver
- **Cache/Queue**: Redis for caching, sessions, and background tasks
- **AI Integration**: Ollama for local LLM processing
- **Security**: JWT authentication, Fernet encryption, Cloudflare Turnstile
- **MCP Server**: FastMCP 2.x for AI agent integration

## Development Guidelines

### Code Quality Standards
- **Type Hints**: Use full type annotations for all functions and methods
- **Documentation**: Comprehensive docstrings following PEP 257
- **Error Handling**: Proper exception handling with meaningful error messages
- **Logging**: Use structured logging with appropriate log levels
- **Testing**: Write unit tests for all new functionality

### Configuration Management
- **Environment Variables**: Use the Settings class from `src.second_brain_database.config`
- **Secrets**: Never commit secrets; use .sbd files or environment variables
- **Validation**: All configuration is validated at startup with helpful error messages

### Database Operations
- **Async Operations**: Use Motor for all MongoDB operations
- **Connection Management**: Proper connection pooling and error handling
- **Indexing**: Ensure proper indexes for query performance
- **Migrations**: Handle schema changes carefully

### API Design
- **RESTful**: Follow REST principles with consistent URL patterns
- **Response Models**: Use Pydantic models for all API responses
- **Error Responses**: Consistent error response format
- **Documentation**: Auto-generated OpenAPI docs with examples

## Common Patterns

### Configuration Access
```python
from src.second_brain_database.config import settings

# Access configuration
mongodb_url = settings.MONGODB_URL
debug_mode = settings.DEBUG
```

### Database Operations
```python
from src.second_brain_database.managers.mongodb_manager import mongodb_manager

# Get collection
users_collection = mongodb_manager.get_collection("users")

# Async operations
user = await users_collection.find_one({"email": email})
```

### Error Handling
```python
from fastapi import HTTPException

try:
    # Operation that might fail
    result = await some_async_operation()
except SomeSpecificException as e:
    raise HTTPException(status_code=400, detail=str(e))
```

### Logging
```python
from src.second_brain_database.managers.logging_manager import logger

logger.info("Operation completed", extra={"user_id": user_id, "operation": "create"})
```

## Security Considerations
- **Input Validation**: Validate all user inputs
- **Rate Limiting**: Implement appropriate rate limits
- **Authentication**: Use JWT tokens with proper expiration
- **Authorization**: Check permissions for all operations
- **Secrets Management**: Never expose secrets in logs or responses

## Testing Strategy
- **Unit Tests**: Test individual functions and methods
- **Integration Tests**: Test API endpoints and database operations
- **Configuration Tests**: Test configuration loading and validation
- **Security Tests**: Test authentication and authorization

## Deployment Considerations
- **Environment Variables**: Use environment variables for deployment-specific config
- **Health Checks**: Implement proper health check endpoints
- **Monitoring**: Comprehensive logging and metrics
- **Scaling**: Design for horizontal scaling with Redis and MongoDB

## AI Integration Guidelines
- **Ollama Integration**: Use configured Ollama host and models
- **MCP Server**: Implement MCP tools following the FastMCP 2.x specification
- **Model Selection**: Support multiple models with automatic selection
- **Performance**: Implement caching and rate limiting for AI operations

## File Organization
- `src/second_brain_database/`: Main application code
- `tests/`: Test files
- `scripts/`: Maintenance and utility scripts
- `docs/`: Documentation
- `config-templates/`: Configuration file templates
- `.sbd`: Configuration file (not committed to git)

Remember: This codebase follows modern Python practices with emphasis on security, performance, and maintainability. Always prioritize security and code quality in all changes.