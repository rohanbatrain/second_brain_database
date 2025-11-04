# Second Brain Database n8n Node

A comprehensive n8n community node for integrating with the Second Brain Database - a Family Financial Management System.

## Features

- **Complete API Coverage**: Access all 29+ API operations across 6 resource categories
- **Family Financial Management**: Handle family accounts, token transfers, spending permissions, and member management
- **Authentication Support**: JWT tokens, permanent tokens, and 2FA authentication
- **Audit & Compliance**: Full audit logging and compliance reporting
- **System Health Monitoring**: Database stats, rate limiting, and health checks
- **Workspace Management**: Create and manage isolated workspaces
- **Production Ready**: Comprehensive error handling, rate limiting awareness, and TypeScript support
- **Client-Side Encryption**: Optional encryption support with conditional secret key

## Installation

### Option 1: Install from npm (Recommended)

```bash
npm install n8n-nodes-second-brain-database
```

### Option 2: Manual Installation

1. Clone or download this repository
2. Navigate to the project directory
3. Install dependencies:
   ```bash
   npm install
   ```
4. Build the node:
   ```bash
   npm run build
   ```
5. Copy the built files to your n8n custom nodes directory

## Setup

### 1. Configure Credentials

Create a new credential of type "Second Brain Database API":

- **Base URL**: Your Second Brain Database API endpoint (e.g., `https://api.secondbrain.com`)
- **Permanent Token**: Your permanent API token for authentication
- **Client-Side Encryption**: Enable if your API uses client-side encryption
- **Secret Key**: Required only if client-side encryption is enabled

### 2. Add Node to Workflow

Search for "Second Brain Database" in the n8n node palette and add it to your workflow.

## Resources and Operations

### Authentication
- **Create Permanent Token**: Create a permanent API token for automation
- **List Permanent Tokens**: List all permanent tokens for the user
- **Login**: Authenticate user and get JWT token
- **Refresh Token**: Refresh JWT token before expiration
- **Revoke Permanent Token**: Revoke a permanent token by ID
- **Setup 2FA**: Setup two-factor authentication
- **Validate Token**: Validate JWT token and get user info
- **Verify 2FA**: Verify 2FA code

### Family Management
- **Accept Invitation**: Accept family invitation
- **Create Family**: Create a new family account
- **Emergency Access**: Request emergency access to frozen account
- **Freeze Account**: Freeze family account for security
- **Get Family**: Get family details by ID
- **Invite Member**: Invite a new member to the family
- **List Families**: List all families for the user
- **Remove Member**: Remove a member from the family
- **Set Spending Permissions**: Set spending limits and permissions
- **Unfreeze Account**: Unfreeze family account
- **Update Family**: Update family information
- **Update Member Role**: Update member role and permissions

### SBD Token Operations
- **Approve Request**: Approve pending token request
- **Get Balance**: Get token balance for family account
- **Get Transaction History**: Get transaction history for account
- **List Pending Requests**: List pending token transfer requests
- **Reject Request**: Reject pending token request
- **Request Tokens**: Request token transfer approval
- **Transfer Tokens**: Transfer SBD tokens between family accounts

### Workspace Management
- **Create Workspace**: Create a new workspace
- **Delete Workspace**: Delete a workspace
- **Get Workspace**: Get workspace details
- **List Workspaces**: List all workspaces
- **Update Workspace**: Update workspace information

### Audit & Compliance
- **Export Audit Data**: Export audit data for external review
- **Get Audit Logs**: Get audit logs for compliance
- **Get Compliance Report**: Generate compliance report

### System Health
- **Database Stats**: Get database statistics
- **Health Check**: Check system health status
- **Rate Limit Status**: Check current rate limit status

## Usage Examples

### Basic Authentication Flow

1. Add "Second Brain Database" node
2. Select Resource: "Authentication"
3. Select Operation: "Login"
4. Configure login credentials (username/email + password)
5. Optional: Add 2FA code if enabled

### Token Transfer

1. Add "Second Brain Database" node
2. Select Resource: "SBD Token"
3. Select Operation: "Transfer Tokens"
4. Set Family ID (optional for some operations)
5. Configure transfer details:
   - To Family ID
   - Amount
   - Description (optional)
   - Requires Approval (optional)

### Family Management

1. Add "Second Brain Database" node
2. Select Resource: "Family"
3. Select Operation: "Invite Member"
4. Set Family ID
5. Configure invitation details

## Configuration Options

### Family ID Parameter
- **Optional for SBD Token Operations**: Can be left empty for operations that don't require a specific family context
- **Required for Family Operations**: Must be provided for all family management operations

### Query Parameters
Available for list operations:
- **Limit**: Maximum number of results (default: 50)
- **Offset**: Number of results to skip (default: 0)
- **Date Filters**: From/To date ranges for transaction and audit queries

### Transfer Details
For token operations:
- **To Family ID**: Recipient family account
- **Amount**: Number of tokens to transfer
- **Description**: Optional transfer description
- **Requires Approval**: Whether transfer needs approval

## Error Handling

The node includes comprehensive error handling for:
- Authentication failures
- Rate limiting (automatic retry with backoff)
- Invalid parameters
- Network connectivity issues
- API-specific errors

## Rate Limiting

The node is aware of API rate limits and includes:
- Automatic retry with exponential backoff
- Rate limit status checking
- Proper error messages for rate limit violations

## Development

### Building

```bash
npm run build
```

### Testing

```bash
npm run test
```

### Linting

```bash
npm run lint
```

## API Documentation

For detailed API documentation, see the Second Brain Database API documentation at:
- `/docs/family_api_endpoints_summary.md`
- `/docs/auth_workflows_n8n.md`
- `/docs/token_operations_n8n.md`
- And other documentation files in the `/docs` directory

## Support

For issues and feature requests, please check the main Second Brain Database repository.

## License

This n8n node package follows the same license as the Second Brain Database project.
