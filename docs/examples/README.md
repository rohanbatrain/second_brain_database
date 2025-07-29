# OAuth2 Integration Examples

This directory contains practical examples of integrating with the Second Brain Database OAuth2 provider for different types of client applications.

## Available Examples

### Web Applications
- [**Node.js Express Web App**](./web-app-nodejs/) - Complete server-side web application
- [**Python Flask Web App**](./web-app-python/) - Flask-based web application
- [**PHP Web Application**](./web-app-php/) - Traditional PHP web application (coming soon)

### Single Page Applications (SPA)
- [**React SPA**](./spa-react/) - React application with OAuth2 integration
- [**Vue.js SPA**](./spa-vue/) - Vue.js application example (coming soon)
- [**Vanilla JavaScript SPA**](./spa-vanilla/) - Pure JavaScript implementation (coming soon)

### Mobile Applications
- [**React Native App**](./mobile-react-native/) - Cross-platform mobile app
- [**Flutter App**](./mobile-flutter/) - Flutter mobile application (coming soon)
- [**iOS Swift App**](./mobile-ios/) - Native iOS application (coming soon)

### Server-to-Server
- [**Python API Client**](./server-python/) - Python service integration
- [**Node.js API Client**](./server-nodejs/) - Node.js service integration (coming soon)
- [**Go API Client**](./server-go/) - Go service integration (coming soon)

### Command Line Tools
- [**Python CLI Tool**](./cli-python/) - Command-line interface
- [**Node.js CLI Tool**](./cli-nodejs/) - Node.js CLI application (coming soon)

## Quick Start

Each example includes:
- Complete source code
- Configuration instructions
- Step-by-step setup guide
- Error handling examples
- Security best practices

## Common Patterns

All examples demonstrate:
- PKCE (Proof Key for Code Exchange) implementation
- Proper state parameter handling for CSRF protection
- Token refresh and rotation
- Error handling and retry logic
- Secure token storage
- Scope-based access control

## Prerequisites

Before running any example:

1. **Register your OAuth2 client** with the Second Brain Database
2. **Configure your redirect URIs** in the client registration
3. **Set up your environment** with client credentials
4. **Install dependencies** as specified in each example

## Security Notes

All examples follow OAuth2 security best practices:
- Always use HTTPS in production
- Implement PKCE for all client types
- Validate state parameters
- Store tokens securely
- Handle token expiration gracefully
- Use minimum required scopes

## Support

If you need help with any example:
1. Check the example's README file
2. Review the [OAuth2 Integration Guide](../OAUTH2_INTEGRATION.md)
3. Consult the [API Reference](../OAUTH2_API_REFERENCE.md)
4. Check the [Configuration Guide](../OAUTH2_CONFIGURATION.md)