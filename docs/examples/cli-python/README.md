# Python CLI OAuth2 Integration Example

This example demonstrates how to create a command-line interface (CLI) tool that integrates with the Second Brain Database OAuth2 provider.

## Features

- OAuth2 authorization code flow with PKCE
- Device flow support for headless environments  
- Secure token storage using system keyring
- Interactive authentication with browser launch
- Command-line interface with multiple subcommands
- Automatic token refresh and management

## Prerequisites

- Python 3.8+ and pip
- Registered OAuth2 client in Second Brain Database (configured as "public" client type)
- Web browser for authentication (or device flow for headless)

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python sbd_cli.py --help
```

## Configuration

Create config file at `~/.sbd-cli/config.yaml`:

```yaml
oauth2:
  client_id: your_client_id_here
  redirect_uri: http://localhost:8080/callback
  authorization_url: https://your-sbd-instance.com/oauth2/authorize
  token_url: https://your-sbd-instance.com/oauth2/token
  api_base_url: https://your-sbd-instance.com

cli:
  default_format: json
  timeout: 30
  log_level: INFO
```

## Usage

### Authentication

```bash
# Login with browser
sbd_cli auth login

# Login with device flow
sbd_cli auth login --device

# Check status
sbd_cli auth status

# Logout
sbd_cli auth logout
```

### API Operations

```bash
# Get user profile
sbd_cli profile show

# List data
sbd_cli data list

# Create data
sbd_cli data create --title "My Document" --content "Content"

# Get data
sbd_cli data get <data_id>

# Update data
sbd_cli data update <data_id> --title "Updated Title"

# Delete data
sbd_cli data delete <data_id>
```

## Security Features

### Secure Token Storage

```python
import keyring
import json

class SecureTokenStorage:
    def store_tokens(self, tokens: dict) -> None:
        token_json = json.dumps(tokens)
        keyring.set_password('sbd-cli', 'oauth2_tokens', token_json)
    
    def get_tokens(self) -> dict:
        token_json = keyring.get_password('sbd-cli', 'oauth2_tokens')
        return json.loads(token_json) if token_json else None
```

### PKCE Implementation

```python
import secrets
import hashlib
import base64

def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode('utf-8').rstrip('=')
    
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge
```

## Installation and Distribution

```python
# setup.py
from setuptools import setup, find_packages

setup(
    name='sbd-cli',
    version='1.0.0',
    description='Second Brain Database CLI Tool',
    packages=find_packages(),
    install_requires=[
        'click>=8.0.0',
        'requests>=2.25.0',
        'keyring>=23.0.0',
        'rich>=12.0.0',
        'pyyaml>=6.0',
        'cryptography>=3.4.0'
    ],
    entry_points={
        'console_scripts': [
            'sbd-cli=sbd_cli:cli',
        ],
    },
    python_requires='>=3.8',
)
```

## Troubleshooting

### Common Issues

1. **Keyring access denied**
   - Ensure system keyring is configured
   - On Linux, install `python3-keyring` package

2. **Browser doesn't open**
   - Use device flow with `--device` flag
   - Check `DISPLAY` environment variable (Linux)

3. **Callback server fails**
   - Check if port 8080 is available
   - Configure different port in redirect URI

### Debug Mode

```bash
sbd-cli --verbose auth login
```

## Support

For additional help:
- Check the [OAuth2 Integration Guide](../../OAUTH2_INTEGRATION.md)
- Review the [API Reference](../../OAUTH2_API_REFERENCE.md)
- See other examples in the [examples directory](../)