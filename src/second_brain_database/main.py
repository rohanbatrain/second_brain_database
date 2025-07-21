"""
Main application module for Second Brain Database API.

This module sets up the FastAPI application with proper lifespan management,
database connections, and routing configuration.
"""
from contextlib import asynccontextmanager
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.docs.config import docs_config
from second_brain_database.docs.middleware import configure_documentation_middleware
from second_brain_database.routes import auth_router, main_router
from second_brain_database.routes.auth.periodics.cleanup import (
    periodic_2fa_cleanup,
    periodic_avatar_rental_cleanup,
    periodic_banner_rental_cleanup,
    periodic_email_verification_token_cleanup,
    periodic_session_cleanup,
    periodic_trusted_ip_lockdown_code_cleanup,
    periodic_admin_session_token_cleanup,
)
from second_brain_database.routes.auth.periodics.redis_flag_sync import periodic_blocklist_whitelist_reconcile
from second_brain_database.routes.sbd_tokens.routes import router as sbd_tokens_router
from second_brain_database.routes.themes.routes import router as themes_router
from second_brain_database.routes.shop.routes import router as shop_router
from second_brain_database.routes.avatars.routes import router as avatars_router
from second_brain_database.routes.banners.routes import router as banners_router

logger = get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting up FastAPI application...")
    try:
        await db_manager.connect()
        logger.info("Database connection established")
        
        # Create database indexes
        await db_manager.create_indexes()
        logger.info("Database indexes created/verified")
    except Exception as e:
        logger.error("Failed to connect to database: %s", e)
        raise HTTPException(
            status_code=503,
            detail='Service not ready: Database connection failed'
        ) from e

    # Start periodic cleanup tasks
    cleanup_task = asyncio.create_task(periodic_2fa_cleanup())
    reconcile_task = asyncio.create_task(periodic_blocklist_whitelist_reconcile())
    avatar_cleanup_task = asyncio.create_task(periodic_avatar_rental_cleanup())
    banner_cleanup_task = asyncio.create_task(periodic_banner_rental_cleanup())
    email_verif_cleanup_task = asyncio.create_task(periodic_email_verification_token_cleanup())
    session_cleanup_task = asyncio.create_task(periodic_session_cleanup())
    trusted_ip_cleanup_task = asyncio.create_task(periodic_trusted_ip_lockdown_code_cleanup())
    admin_session_cleanup_task = asyncio.create_task(periodic_admin_session_token_cleanup())

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application...")
    cleanup_task.cancel()
    reconcile_task.cancel()
    avatar_cleanup_task.cancel()
    banner_cleanup_task.cancel()
    email_verif_cleanup_task.cancel()
    session_cleanup_task.cancel()
    trusted_ip_cleanup_task.cancel()
    admin_session_cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await reconcile_task
    except asyncio.CancelledError:
        pass
    try:
        await avatar_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await banner_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await email_verif_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await session_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await trusted_ip_cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await admin_session_cleanup_task
    except asyncio.CancelledError:
        pass
    await db_manager.disconnect()
    logger.info("Database connection closed")

# Create FastAPI app with comprehensive documentation configuration
app = FastAPI(
    title="Second Brain Database API",
    description="""
    ## Second Brain Database API

    A comprehensive FastAPI application for managing your second brain database - 
    a knowledge management system designed to store, organize, and retrieve information efficiently.

    ### Features
    - **User Authentication & Authorization**: Secure JWT-based authentication with 2FA support
    - **Permanent API Tokens**: Long-lived tokens for API access and integrations
    - **Knowledge Management**: Store and organize your personal knowledge base
    - **Themes & Customization**: Personalize your experience with custom themes
    - **Shop Integration**: Manage digital assets and purchases
    - **Avatar & Banner Management**: Customize your profile appearance

    ### Security
    - JWT token authentication
    - Rate limiting and abuse protection
    - Redis-based session management
    - Comprehensive audit logging

    ### Getting Started
    1. Register for an account or authenticate with existing credentials
    2. Obtain an access token or create permanent API tokens
    3. Start managing your knowledge base through the API endpoints

    For more information, visit our [GitHub repository](https://github.com/rohanbatrain/second_brain_database).
    """,
    version="1.0.0",
    contact=docs_config.contact_info,
    license_info=docs_config.license_info,
    servers=docs_config.servers,
    docs_url=docs_config.docs_url,
    redoc_url=docs_config.redoc_url,
    openapi_url=docs_config.openapi_url,
    lifespan=lifespan,
    # Additional OpenAPI configuration
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User authentication, registration, and session management"
        },
        {
            "name": "Permanent Tokens",
            "description": "Long-lived API tokens for integrations and automation"
        },
        {
            "name": "Knowledge Base",
            "description": "Core knowledge management functionality"
        },
        {
            "name": "User Profile",
            "description": "User profile management including avatars and banners"
        },
        {
            "name": "Themes",
            "description": "Theme and customization management"
        },
        {
            "name": "Shop",
            "description": "Digital asset and purchase management"
        },
        {
            "name": "System",
            "description": "System health and monitoring endpoints"
        }
    ]
)

# Add comprehensive security schemes to OpenAPI
def custom_openapi():
    """
    Custom OpenAPI schema generation with enhanced security documentation.
    
    This function generates a comprehensive OpenAPI schema with detailed security
    documentation, enhanced metadata, and environment-aware configurations.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    try:
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=app.servers,
            terms_of_service=getattr(app, 'terms_of_service', None),
            contact=app.contact,
            license_info=app.license_info,
        )
        
        # Ensure components section exists
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        
        # Add comprehensive security schemes
        openapi_schema["components"]["securitySchemes"] = {
            "JWTBearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": """
                JWT Bearer token authentication for secure API access.
                
                **How to obtain a token:**
                1. Register a new account via `POST /auth/register`
                2. Login with your credentials via `POST /auth/login`
                3. Use the returned `access_token` in the Authorization header
                
                **Usage:**
                ```
                Authorization: Bearer <your_jwt_token>
                ```
                
                **Token Details:**
                - **Expiration:** 30 minutes by default
                - **Algorithm:** HS256
                - **Refresh:** Use `POST /auth/refresh` to get a new token
                - **Logout:** Use `POST /auth/logout` to invalidate the token
                
                **Example Response:**
                ```json
                {
                  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                  "token_type": "bearer",
                  "expires_at": 1640995200
                }
                ```
                """
            },
            "PermanentToken": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "Token",
                "description": """
                Permanent API token authentication for long-lived integrations and automation.
                
                **How to obtain a permanent token:**
                1. Authenticate with JWT token first
                2. Create a permanent token via `POST /auth/permanent-tokens`
                3. Use the returned token in the Authorization header
                
                **Usage:**
                ```
                Authorization: Bearer <your_permanent_token>
                ```
                
                **Benefits:**
                - **Long-lived:** No expiration (until manually revoked)
                - **Perfect for integrations:** Ideal for CI/CD, scripts, and third-party apps
                - **Individual control:** Can be revoked individually without affecting other tokens
                - **Usage analytics:** Detailed tracking of token usage and access patterns
                - **Security features:** IP restrictions, usage monitoring, and abuse detection
                
                **Management:**
                - List tokens: `GET /auth/permanent-tokens`
                - Revoke token: `DELETE /auth/permanent-tokens/{token_id}`
                - View analytics: Token usage statistics available in response
                """
            },
            "AdminAPIKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Admin-API-Key",
                "description": """
                Admin API key for administrative operations and system management.
                
                **Usage:**
                ```
                X-Admin-API-Key: <your_admin_api_key>
                ```
                
                **Access Level:**
                - Only available to users with admin role
                - Provides access to administrative endpoints
                - Used for system monitoring and management operations
                
                **Security:**
                - Separate from user authentication tokens
                - Additional layer of security for sensitive operations
                - Logged and monitored for security auditing
                """
            }
        }
        
        # Add global security requirements
        openapi_schema["security"] = [
            {"JWTBearer": []},
            {"PermanentToken": []},
            {"AdminAPIKey": []}
        ]
        
        # Enhanced info section with additional metadata
        openapi_schema["info"].update({
            "x-logo": {
                "url": "https://github.com/rohanbatrain/second_brain_database/raw/main/logo.png",
                "altText": "Second Brain Database Logo"
            },
            "x-api-id": "second-brain-database-api",
            "x-audience": "developers",
            "x-category": "knowledge-management"
        })
        
        # Add external documentation
        openapi_schema["externalDocs"] = {
            "description": "GitHub Repository & Full Documentation",
            "url": "https://github.com/rohanbatrain/second_brain_database"
        }
        
        # Add comprehensive tag descriptions with enhanced metadata
        if "tags" not in openapi_schema:
            openapi_schema["tags"] = []
        
        # Update existing tags with more detailed descriptions
        enhanced_tags = [
            {
                "name": "Authentication",
                "description": """
                **User Authentication & Session Management**
                
                Complete authentication system including:
                - User registration and email verification
                - Secure login with optional 2FA support
                - JWT token management and refresh
                - Password reset and change functionality
                - Session management and logout
                
                **Security Features:**
                - Rate limiting on all auth endpoints
                - Abuse detection for password resets
                - CAPTCHA integration for suspicious activity
                - Comprehensive audit logging
                """,
                "externalDocs": {
                    "description": "Authentication Guide",
                    "url": "https://github.com/rohanbatrain/second_brain_database#authentication"
                }
            },
            {
                "name": "Permanent Tokens", 
                "description": """
                **Long-lived API Tokens for Integrations**
                
                Permanent tokens provide secure, long-term API access for:
                - CI/CD pipelines and automation scripts
                - Third-party application integrations
                - Server-to-server communication
                - Background job processing
                
                **Features:**
                - No expiration (until manually revoked)
                - Individual token management and revocation
                - Usage analytics and monitoring
                - IP-based access restrictions
                - Abuse detection and alerting
                """,
                "externalDocs": {
                    "description": "Permanent Tokens Guide", 
                    "url": "https://github.com/rohanbatrain/second_brain_database#permanent-tokens"
                }
            },
            {
                "name": "Knowledge Base",
                "description": """
                **Core Knowledge Management System**
                
                Central functionality for managing your second brain:
                - Document storage and organization
                - Search and retrieval capabilities
                - Tagging and categorization
                - Version control and history
                
                **Coming Soon:** Enhanced knowledge management features
                """
            },
            {
                "name": "User Profile",
                "description": """
                **User Profile & Customization Management**
                
                Comprehensive user profile system including:
                - Avatar management and customization
                - Banner selection and rental system
                - Profile settings and preferences
                - Account information management
                
                **Features:**
                - Asset ownership and rental tracking
                - Multi-application avatar/banner support
                - User preference synchronization
                """
            },
            {
                "name": "Themes",
                "description": """
                **Theme & Visual Customization System**
                
                Personalization features for user experience:
                - Theme selection and management
                - Custom color schemes
                - Visual preference settings
                - Theme rental and ownership system
                """
            },
            {
                "name": "Shop",
                "description": """
                **Digital Asset & Purchase Management**
                
                E-commerce functionality for digital assets:
                - Avatar and banner purchases
                - Theme and customization purchases
                - Shopping cart management
                - Purchase history and receipts
                - Asset ownership tracking
                """
            },
            {
                "name": "System",
                "description": """
                **System Health & Monitoring**
                
                System status and monitoring endpoints:
                - Health checks and status monitoring
                - Performance metrics and analytics
                - System information and diagnostics
                - Administrative tools and utilities
                """
            }
        ]
        
        # Replace existing tags with enhanced versions
        openapi_schema["tags"] = enhanced_tags
        
        # Add environment-specific information
        if settings.is_production:
            openapi_schema["info"]["x-environment"] = "production"
        else:
            openapi_schema["info"]["x-environment"] = "development"
            openapi_schema["info"]["x-debug"] = True
        
        logger.info("Custom OpenAPI schema generated successfully")
        
    except Exception as e:
        logger.error("Error generating custom OpenAPI schema: %s", e)
        # Fallback to default schema generation
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Set custom OpenAPI schema
app.openapi = custom_openapi

# Configure documentation middleware
configure_documentation_middleware(app)

# Include routers
app.include_router(auth_router)
app.include_router(main_router)
app.include_router(sbd_tokens_router)
app.include_router(themes_router)
app.include_router(shop_router)
app.include_router(avatars_router)
app.include_router(banners_router)

# Instrumentator for Prometheus metrics
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
).add().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
