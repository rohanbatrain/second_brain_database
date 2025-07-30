"""
Main application module for Second Brain Database API.

This module sets up the FastAPI application with proper lifespan management,
database connections, and routing configuration with comprehensive logging.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import time

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
import uvicorn

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.docs.config import docs_config
from second_brain_database.docs.middleware import configure_documentation_middleware
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes import auth_router, main_router
from second_brain_database.routes.auth.periodics.cleanup import (
    periodic_2fa_cleanup,
    periodic_admin_session_token_cleanup,
    periodic_avatar_rental_cleanup,
    periodic_banner_rental_cleanup,
    periodic_email_verification_token_cleanup,
    periodic_session_cleanup,
    periodic_trusted_ip_lockdown_code_cleanup,
)
from second_brain_database.routes.auth.periodics.redis_flag_sync import periodic_blocklist_whitelist_reconcile
from second_brain_database.routes.avatars.routes import router as avatars_router
from second_brain_database.routes.banners.routes import router as banners_router
from second_brain_database.routes.sbd_tokens.routes import router as sbd_tokens_router
from second_brain_database.routes.shop.routes import router as shop_router
from second_brain_database.routes.themes.routes import router as themes_router
from second_brain_database.utils.logging_utils import (
    RequestLoggingMiddleware,
    log_application_lifecycle,
    log_error_with_context,
    log_performance,
)

logger = get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Application lifespan manager with comprehensive logging.

    Manages application startup and shutdown with detailed logging
    of all lifecycle events, database connections, and background tasks.
    """
    startup_start_time = time.time()

    # Log application startup initiation
    log_application_lifecycle(
        "startup_initiated",
        {
            "app_name": "Second Brain Database API",
            "version": "1.0.0",
            "environment": "production" if settings.is_production else "development",
            "debug_mode": settings.DEBUG,
        },
    )

    try:
        # Database connection with performance logging
        db_connect_start = time.time()
        logger.info("Initiating database connection...")

        await db_manager.connect()
        db_connect_duration = time.time() - db_connect_start

        log_application_lifecycle(
            "database_connected",
            {
                "connection_duration": f"{db_connect_duration:.3f}s",
                "database_name": settings.MONGODB_DATABASE,
                "connection_url": (
                    settings.MONGODB_URL.split("@")[-1] if "@" in settings.MONGODB_URL else settings.MONGODB_URL
                ),
            },
        )

        # Database indexes creation with performance logging
        indexes_start = time.time()
        logger.info("Creating/verifying database indexes...")

        await db_manager.create_indexes()
        indexes_duration = time.time() - indexes_start

        log_application_lifecycle("database_indexes_ready", {"indexes_duration": f"{indexes_duration:.3f}s"})

    except Exception as e:
        startup_duration = time.time() - startup_start_time
        log_application_lifecycle(
            "startup_failed",
            {"error": str(e), "error_type": type(e).__name__, "startup_duration": f"{startup_duration:.3f}s"},
        )
        log_error_with_context(e, {"operation": "application_startup", "phase": "database_connection"})
        raise HTTPException(status_code=503, detail="Service not ready: Database connection failed") from e

    # Start periodic cleanup tasks with logging
    background_tasks = {}
    task_start_time = time.time()

    try:
        logger.info("Starting background cleanup tasks...")

        background_tasks.update(
            {
                "2fa_cleanup": asyncio.create_task(periodic_2fa_cleanup()),
                "blocklist_reconcile": asyncio.create_task(periodic_blocklist_whitelist_reconcile()),
                "avatar_cleanup": asyncio.create_task(periodic_avatar_rental_cleanup()),
                "banner_cleanup": asyncio.create_task(periodic_banner_rental_cleanup()),
                "email_verification_cleanup": asyncio.create_task(periodic_email_verification_token_cleanup()),
                "session_cleanup": asyncio.create_task(periodic_session_cleanup()),
                "trusted_ip_cleanup": asyncio.create_task(periodic_trusted_ip_lockdown_code_cleanup()),
                "admin_session_cleanup": asyncio.create_task(periodic_admin_session_token_cleanup()),
            }
        )

        tasks_duration = time.time() - task_start_time
        log_application_lifecycle(
            "background_tasks_started",
            {
                "task_count": len(background_tasks),
                "tasks": list(background_tasks.keys()),
                "tasks_startup_duration": f"{tasks_duration:.3f}s",
            },
        )

    except Exception as e:
        log_error_with_context(
            e, {"operation": "background_tasks_startup", "tasks_attempted": list(background_tasks.keys())}
        )
        # Continue startup even if some background tasks fail
        logger.warning("Some background tasks failed to start, continuing with application startup")

    # Log successful startup completion
    total_startup_duration = time.time() - startup_start_time
    log_application_lifecycle(
        "startup_completed",
        {
            "total_startup_duration": f"{total_startup_duration:.3f}s",
            "database_ready": True,
            "background_tasks_count": len(background_tasks),
        },
    )

    logger.info(f"FastAPI application startup completed in {total_startup_duration:.3f}s")

    yield

    # Shutdown process with comprehensive logging
    shutdown_start_time = time.time()
    log_application_lifecycle("shutdown_initiated", {"active_background_tasks": len(background_tasks)})

    # Cancel and cleanup background tasks
    cancelled_tasks = []
    failed_cleanups = []

    logger.info("Cancelling background tasks...")
    for task_name, task in background_tasks.items():
        try:
            task.cancel()
            cancelled_tasks.append(task_name)
            logger.info(f"Cancelled background task: {task_name}")
        except Exception as e:
            failed_cleanups.append({"task": task_name, "error": str(e)})
            logger.error(f"Failed to cancel background task {task_name}: {e}")

    # Wait for task cancellations with timeout
    cleanup_start = time.time()
    for task_name, task in background_tasks.items():
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.CancelledError:
            logger.info(f"Background task {task_name} cancelled successfully")
        except asyncio.TimeoutError:
            logger.warning(f"Background task {task_name} cancellation timed out")
            failed_cleanups.append({"task": task_name, "error": "cancellation_timeout"})
        except Exception as e:
            logger.error(f"Error during {task_name} cleanup: {e}")
            failed_cleanups.append({"task": task_name, "error": str(e)})

    cleanup_duration = time.time() - cleanup_start

    # Database disconnection with logging
    db_disconnect_start = time.time()
    try:
        logger.info("Disconnecting from database...")
        await db_manager.disconnect()
        db_disconnect_duration = time.time() - db_disconnect_start

        log_application_lifecycle("database_disconnected", {"disconnect_duration": f"{db_disconnect_duration:.3f}s"})

    except Exception as e:
        log_error_with_context(e, {"operation": "database_disconnection"})

    # Log shutdown completion
    total_shutdown_duration = time.time() - shutdown_start_time
    log_application_lifecycle(
        "shutdown_completed",
        {
            "total_shutdown_duration": f"{total_shutdown_duration:.3f}s",
            "tasks_cleanup_duration": f"{cleanup_duration:.3f}s",
            "cancelled_tasks": cancelled_tasks,
            "failed_cleanups": failed_cleanups,
            "cleanup_success_rate": (
                f"{(len(cancelled_tasks) / len(background_tasks) * 100):.1f}%" if background_tasks else "100%"
            ),
        },
    )

    logger.info(f"FastAPI application shutdown completed in {total_shutdown_duration:.3f}s")


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
        {"name": "Authentication", "description": "User authentication, registration, and session management"},
        {"name": "Permanent Tokens", "description": "Long-lived API tokens for integrations and automation"},
        {"name": "Knowledge Base", "description": "Core knowledge management functionality"},
        {"name": "User Profile", "description": "User profile management including avatars and banners"},
        {"name": "Themes", "description": "Theme and customization management"},
        {"name": "Shop", "description": "Digital asset and purchase management"},
        {"name": "System", "description": "System health and monitoring endpoints"},
    ],
)


# Add comprehensive security schemes to OpenAPI
@log_performance("openapi_schema_generation")
def custom_openapi():
    """
    Custom OpenAPI schema generation with enhanced security documentation and comprehensive logging.

    This function generates a comprehensive OpenAPI schema with detailed security
    documentation, enhanced metadata, and environment-aware configurations.
    All operations are logged for monitoring and debugging purposes.
    """
    if app.openapi_schema:
        logger.debug("Returning cached OpenAPI schema")
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    schema_generation_start = time.time()
    logger.info("Generating custom OpenAPI schema...")

    try:
        # Generate base OpenAPI schema
        logger.debug("Creating base OpenAPI schema with FastAPI utils")
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=app.servers,
            terms_of_service=getattr(app, "terms_of_service", None),
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
                """,
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
                """,
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
                """,
            },
        }

        # Add global security requirements
        openapi_schema["security"] = [{"JWTBearer": []}, {"PermanentToken": []}, {"AdminAPIKey": []}]

        # Enhanced info section with additional metadata
        openapi_schema["info"].update(
            {
                "x-logo": {
                    "url": "https://github.com/rohanbatrain/second_brain_database/raw/main/logo.png",
                    "altText": "Second Brain Database Logo",
                },
                "x-api-id": "second-brain-database-api",
                "x-audience": "developers",
                "x-category": "knowledge-management",
            }
        )

        # Add external documentation
        openapi_schema["externalDocs"] = {
            "description": "GitHub Repository & Full Documentation",
            "url": "https://github.com/rohanbatrain/second_brain_database",
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
                    "url": "https://github.com/rohanbatrain/second_brain_database#authentication",
                },
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
                    "url": "https://github.com/rohanbatrain/second_brain_database#permanent-tokens",
                },
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
                """,
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
                """,
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
                """,
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
                """,
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
                """,
            },
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


# Set custom OpenAPI schema with logging
app.openapi = custom_openapi

# Add comprehensive request logging middleware
logger.info("Adding request logging middleware...")
app.add_middleware(RequestLoggingMiddleware)
log_application_lifecycle(
    "middleware_configured", {"middleware": ["RequestLoggingMiddleware", "DocumentationMiddleware"]}
)

# Configure documentation middleware
configure_documentation_middleware(app)

# Include routers with comprehensive logging
routers_config = [
    ("auth", auth_router, "Authentication and authorization endpoints"),
    ("main", main_router, "Main application endpoints and health checks"),
    ("sbd_tokens", sbd_tokens_router, "SBD tokens management endpoints"),
    ("themes", themes_router, "Theme management endpoints"),
    ("shop", shop_router, "Shop and purchase management endpoints"),
    ("avatars", avatars_router, "Avatar management endpoints"),
    ("banners", banners_router, "Banner management endpoints"),
]

logger.info("Including API routers...")
included_routers = []
for router_name, router, description in routers_config:
    try:
        app.include_router(router)
        included_routers.append({"name": router_name, "description": description})
        logger.info(f"Successfully included {router_name} router: {description}")
    except Exception as e:
        log_error_with_context(
            e, {"operation": "router_inclusion", "router_name": router_name, "description": description}
        )
        logger.error(f"Failed to include {router_name} router: {e}")

log_application_lifecycle(
    "routers_configured",
    {"total_routers": len(routers_config), "included_routers": len(included_routers), "routers": included_routers},
)

# Configure Prometheus metrics with comprehensive logging
logger.info("Setting up Prometheus metrics instrumentation...")
try:
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        should_instrument_requests_inprogress=True,
    )

    # Add and instrument the app
    instrumentator.add().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

    log_application_lifecycle(
        "prometheus_configured",
        {
            "metrics_endpoint": "/metrics",
            "group_status_codes": True,
            "ignore_untemplated": True,
            "track_requests_in_progress": True,
        },
    )

    logger.info("Prometheus metrics instrumentation configured successfully")

except Exception as e:
    log_error_with_context(e, {"operation": "prometheus_setup"})
    logger.error(f"Failed to configure Prometheus metrics: {e}")
    # Continue without metrics rather than failing startup

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG, log_level="info")
