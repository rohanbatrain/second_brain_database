# Python Server-to-Server OAuth2 Integration Example

This example demonstrates how to integrate a Python server application with the Second Brain Database OAuth2 provider using the client credentials flow for server-to-server authentication.

## Features

- OAuth2 client credentials flow for server-to-server authentication
- Automatic token refresh and caching
- Robust error handling and retry logic
- Connection pooling and performance optimization
- Comprehensive logging and monitoring
- Rate limiting and backoff strategies
- Secure credential management
- API client with automatic token injection

## Prerequisites

- Python 3.8+ and pip
- Registered OAuth2 client in Second Brain Database (configured as "confidential" client type)
- Server environment with secure credential storage

## Installation

1. Clone or download this example
2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure your environment (see Configuration section)
5. Run the example:

```bash
python main.py
```

## Configuration

Create a `.env` file in the project root:

```env
# OAuth2 Configuration
OAUTH2_CLIENT_ID=your_client_id_here
OAUTH2_CLIENT_SECRET=your_client_secret_here
OAUTH2_TOKEN_URL=https://your-sbd-instance.com/oauth2/token
OAUTH2_API_BASE_URL=https://your-sbd-instance.com

# Application Configuration
LOG_LEVEL=INFO
CACHE_TTL=3600
MAX_RETRIES=3
REQUEST_TIMEOUT=30

# Security Configuration
VERIFY_SSL=True
```

## Project Structure

```
server-python/
├── requirements.txt
├── .env.example
├── README.md
├── main.py                   # Example usage
├── config.py                 # Configuration management
├── oauth2/
│   ├── __init__.py
│   ├── client.py            # OAuth2 client implementation
│   ├── token_manager.py     # Token management with caching
│   └── exceptions.py        # Custom exceptions
├── api/
│   ├── __init__.py
│   ├── client.py            # API client with OAuth2 integration
│   └── endpoints.py         # API endpoint definitions
├── utils/
│   ├── __init__.py
│   ├── logging.py           # Logging configuration
│   ├── retry.py             # Retry logic utilities
│   └── cache.py             # Caching utilities
└── tests/
    ├── __init__.py
    ├── test_oauth2.py       # OAuth2 tests
    ├── test_api.py          # API client tests
    └── conftest.py          # Test configuration
```

## Usage

### Basic Usage

```python
from oauth2.client import OAuth2Client
from api.client import APIClient

# Initialize OAuth2 client
oauth2_client = OAuth2Client(
    client_id="your_client_id",
    client_secret="your_client_secret",
    token_url="https://sbd-instance.com/oauth2/token"
)

# Initialize API client
api_client = APIClient(
    base_url="https://sbd-instance.com",
    oauth2_client=oauth2_client
)

# Make authenticated API calls
try:
    # Get user data
    users = api_client.get("/api/users")
    print(f"Retrieved {len(users)} users")
    
    # Create new data
    new_data = api_client.post("/api/data", {
        "title": "Test Data",
        "content": "This is test content"
    })
    print(f"Created data with ID: {new_data['id']}")
    
except Exception as e:
    print(f"API call failed: {e}")
```

For additional help:
- Check the [OAuth2 Integration Guide](../../OAUTH2_INTEGRATION.md)
- Review the [API Reference](../../OAUTH2_API_REFERENCE.md)
- See other examples in the [examples directory](../)