import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	IDataObject,
} from 'n8n-workflow';
import { NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';

export class SecondBrainDatabase implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Second Brain Database',
		name: 'secondBrainDatabase',
		icon: { light: 'file:second-brain-database.svg', dark: 'file:second-brain-database.dark.svg' },
		group: ['input'],
		version: 1,
		subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
		description: 'Access and manage your Second Brain Database - Family Financial Management System',
		defaults: {
			name: 'Second Brain Database',
		},
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [
			{
				name: 'secondBrainDatabaseApi',
				required: true,
			},
		],
		requestDefaults: {
			baseURL: '={{$credentials.baseUrl}}',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				'User-Agent': 'n8n-SecondBrainDatabase-Node/1.0.0',
			},
		},
		properties: [
			// Resource Selection
			{
				displayName: 'Resource',
				name: 'resource',
				type: 'options',
				noDataExpression: true,
				options: [
					{
						name: 'AI',
						value: 'ai',
					},
					{
						name: 'Audit & Compliance',
						value: 'audit',
					},
					{
						name: 'Authentication',
						value: 'auth',
					},
					{
						name: 'Family',
						value: 'family',
					},
					{
						name: 'SBD Token',
						value: 'sbdTokens',
					},
					{
						name: 'Shop',
						value: 'shop',
					},
					{
						name: 'System Health',
						value: 'health',
					},
					{
						name: 'Workspace',
						value: 'workspaces',
					},
				],
				default: 'family',
			},

			// Authentication Operations
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['auth'],
					},
				},
				options: [
					{
						name: 'Create Permanent Token',
						value: 'createPermanentToken',
						description: 'Create a permanent API token for automation',
						action: 'Create permanent token an auth',
					},
					{
						name: 'List Permanent Tokens',
						value: 'listPermanentTokens',
						description: 'List all permanent tokens for the user',
						action: 'List permanent tokens an auth',
					},
					{
						name: 'Login',
						value: 'login',
						description: 'Authenticate user and get JWT token',
						action: 'Login an auth',
					},
					{
						name: 'Refresh Token',
						value: 'refreshToken',
						description: 'Refresh JWT token before expiration',
						action: 'Refresh token an auth',
					},
					{
						name: 'Revoke Permanent Token',
						value: 'revokePermanentToken',
						description: 'Revoke a permanent token by ID',
						action: 'Revoke permanent token an auth',
					},
					{
						name: 'Setup 2FA',
						value: 'setup2FA',
						description: 'Setup two-factor authentication',
						action: 'Setup 2FA an auth',
					},
					{
						name: 'Validate Token',
						value: 'validateToken',
						description: 'Validate JWT token and get user info',
						action: 'Validate token an auth',
					},
					{
						name: 'Verify 2FA',
						value: 'verify2FA',
						description: 'Verify 2FA code',
						action: 'Verify 2FA an auth',
					},
				],
				default: 'login',
			},

			// Family Operations
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['family'],
					},
				},
				options: [
					{
						name: 'Accept Invitation',
						value: 'acceptInvitation',
						description: 'Accept family invitation',
						action: 'Accept invitation a family',
					},
					{
						name: 'Create Family',
						value: 'createFamily',
						description: 'Create a new family account',
						action: 'Create family a family',
					},
					{
						name: 'Emergency Access',
						value: 'emergencyAccess',
						description: 'Request emergency access to frozen account',
						action: 'Emergency access a family',
					},
					{
						name: 'Freeze Account',
						value: 'freezeAccount',
						description: 'Freeze family account for security',
						action: 'Freeze account a family',
					},
					{
						name: 'Get Family',
						value: 'getFamily',
						description: 'Get family details by ID',
						action: 'Get family a family',
					},
					{
						name: 'Invite Member',
						value: 'inviteMember',
						description: 'Invite a new member to the family',
						action: 'Invite member a family',
					},
					{
						name: 'List Families',
						value: 'listFamilies',
						description: 'List all families for the user',
						action: 'List families a family',
					},
					{
						name: 'Remove Member',
						value: 'removeMember',
						description: 'Remove a member from the family',
						action: 'Remove member a family',
					},
					{
						name: 'Set Spending Permissions',
						value: 'setSpendingPermissions',
						description: 'Set spending limits and permissions',
						action: 'Set spending permissions a family',
					},
					{
						name: 'Unfreeze Account',
						value: 'unfreezeAccount',
						description: 'Unfreeze family account',
						action: 'Unfreeze account a family',
					},
					{
						name: 'Update Family',
						value: 'updateFamily',
						description: 'Update family information',
						action: 'Update family a family',
					},
					{
						name: 'Update Member Role',
						value: 'updateMemberRole',
						description: 'Update member role and permissions',
						action: 'Update member role a family',
					},
				],
				default: 'getFamily',
			},

			// SBD Token Operations
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['sbdTokens'],
					},
				},
				options: [
					{
						name: 'Approve Request',
						value: 'approveRequest',
						description: 'Approve pending token request',
						action: 'Approve request a sbd tokens',
					},
					{
						name: 'Get Balance',
						value: 'getBalance',
						description: 'Get token balance for family account',
						action: 'Get balance a sbd tokens',
					},
					{
						name: 'Get Transaction History',
						value: 'getTransactionHistory',
						description: 'Get transaction history for account',
						action: 'Get transaction history a sbd tokens',
					},
					{
						name: 'List Pending Requests',
						value: 'listPendingRequests',
						description: 'List pending token transfer requests',
						action: 'List pending requests a sbd tokens',
					},
					{
						name: 'Reject Request',
						value: 'rejectRequest',
						description: 'Reject pending token request',
						action: 'Reject request a sbd tokens',
					},
					{
						name: 'Request Tokens',
						value: 'requestTokens',
						description: 'Request token transfer approval',
						action: 'Request tokens a sbd tokens',
					},
					{
						name: 'Transfer Tokens',
						value: 'transferTokens',
						description: 'Transfer SBD tokens between family accounts',
						action: 'Transfer tokens a sbd tokens',
					},
				],
				default: 'getBalance',
			},

			// Shop Operations
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['shop'],
					},
				},
				options: [
					{
						name: 'Add to Cart',
						value: 'addToCart',
						description: 'Add item to shopping cart',
						action: 'Add to cart a shop',
					},
					{
						name: 'Buy Avatar',
						value: 'buyAvatar',
						description: 'Purchase an avatar with SBD tokens',
						action: 'Buy avatar a shop',
					},
					{
						name: 'Buy Banner',
						value: 'buyBanner',
						description: 'Purchase a banner with SBD tokens',
						action: 'Buy banner a shop',
					},
					{
						name: 'Buy Bundle',
						value: 'buyBundle',
						description: 'Purchase a bundle with SBD tokens',
						action: 'Buy bundle a shop',
					},
					{
						name: 'Buy Theme',
						value: 'buyTheme',
						description: 'Purchase a theme with SBD tokens',
						action: 'Buy theme a shop',
					},
					{
						name: 'Checkout Cart',
						value: 'checkoutCart',
						description: 'Checkout shopping cart with payment',
						action: 'Checkout cart a shop',
					},
					{
						name: 'Clear Cart',
						value: 'clearCart',
						description: 'Clear all items from shopping cart',
						action: 'Clear cart a shop',
					},
					{
						name: 'Get Owned Avatars',
						value: 'getOwnedAvatars',
						description: 'Get user\'s owned avatars',
						action: 'Get owned avatars a shop',
					},
					{
						name: 'Get Owned Banners',
						value: 'getOwnedBanners',
						description: 'Get user\'s owned banners',
						action: 'Get owned banners a shop',
					},
					{
						name: 'Get Owned Bundles',
						value: 'getOwnedBundles',
						description: 'Get user\'s owned bundles',
						action: 'Get owned bundles a shop',
					},
					{
						name: 'Get Owned Themes',
						value: 'getOwnedThemes',
						description: 'Get user\'s owned themes',
						action: 'Get owned themes a shop',
					},
					{
						name: 'Get Payment Options',
						value: 'getPaymentOptions',
						description: 'Get available payment options',
						action: 'Get payment options a shop',
					},
					{
						name: 'Get Rented Avatars',
						value: 'getRentedAvatars',
						description: 'Get user\'s rented avatars',
						action: 'Get rented avatars a shop',
					},
					{
						name: 'Get Rented Banners',
						value: 'getRentedBanners',
						description: 'Get user\'s rented banners',
						action: 'Get rented banners a shop',
					},
					{
						name: 'Get Rented Themes',
						value: 'getRentedThemes',
						description: 'Get user\'s rented themes',
						action: 'Get rented themes a shop',
					},
					{
						name: 'Get Shop Cart',
						value: 'getShopCart',
						description: 'Get user\'s shopping cart',
						action: 'Get shop cart a shop',
					},
					{
						name: 'Remove From Cart',
						value: 'removeFromCart',
						description: 'Remove item from shopping cart',
						action: 'Remove from cart a shop',
					},
				],
				default: 'getPaymentOptions',
			},

			// AI Operations
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['ai'],
					},
				},
				options: [
					{
						name: 'AI Health Check',
						value: 'healthCheck',
						description: 'Check AI orchestration system health',
						action: 'Health check an ai',
					},
					{
						name: 'Create Session',
						value: 'createSession',
						description: 'Create a new AI conversation session',
						action: 'Create session an ai',
					},
					{
						name: 'End Session',
						value: 'endSession',
						description: 'End an AI session and clean up resources',
						action: 'End session an ai',
					},
					{
						name: 'Get AI Stats',
						value: 'getStats',
						description: 'Get AI usage statistics',
						action: 'Get stats an ai',
					},
					{
						name: 'Get Detailed Health Check',
						value: 'getDetailedHealthCheck',
						description: 'Get detailed health check for AI components',
						action: 'Get detailed health check an ai',
					},
					{
						name: 'Get Model Warmup Status',
						value: 'getModelWarmupStatus',
						description: 'Get model warmup status and performance',
						action: 'Get model warmup status an ai',
					},
					{
						name: 'Get Performance Metrics',
						value: 'getPerformanceMetrics',
						description: 'Get AI system performance metrics',
						action: 'Get performance metrics an ai',
					},
					{
						name: 'Get Session',
						value: 'getSession',
						description: 'Get details of a specific AI session',
						action: 'Get session an ai',
					},
					{
						name: 'Get Session Performance',
						value: 'getSessionPerformance',
						description: 'Get performance information about AI sessions',
						action: 'Get session performance an ai',
					},
					{
						name: 'Get Voice Token',
						value: 'getVoiceToken',
						description: 'Get LiveKit token for voice communication',
						action: 'Get voice token an ai',
					},
					{
						name: 'Invalidate Caches',
						value: 'invalidateCaches',
						description: 'Invalidate AI system caches',
						action: 'Invalidate caches an ai',
					},
					{
						name: 'List Sessions',
						value: 'listSessions',
						description: 'List AI sessions for the user',
						action: 'List sessions an ai',
					},
					{
						name: 'Process Voice Input',
						value: 'processVoiceInput',
						description: 'Process voice input for an AI session',
						action: 'Process voice input an ai',
					},
					{
						name: 'Send Message',
						value: 'sendMessage',
						description: 'Send a message to an AI agent',
						action: 'Send message an ai',
					},
					{
						name: 'Setup Voice Session',
						value: 'setupVoiceSession',
						description: 'Set up voice capabilities for an AI session',
						action: 'Setup voice session an ai',
					},
					{
						name: 'Trigger Cleanup',
						value: 'triggerCleanup',
						description: 'Trigger manual cleanup of AI resources',
						action: 'Trigger cleanup an ai',
					},
					{
						name: 'Warmup Model',
						value: 'warmupModel',
						description: 'Manually warm up a specific model',
						action: 'Warmup model an ai',
					},
				],
				default: 'createSession',
			},

			// Workspace Operations
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['workspaces'],
					},
				},
				options: [
					{
						name: 'Create Workspace',
						value: 'createWorkspace',
						description: 'Create a new workspace',
						action: 'Create workspace a workspaces',
					},
					{
						name: 'Delete Workspace',
						value: 'deleteWorkspace',
						description: 'Delete a workspace',
						action: 'Delete workspace a workspaces',
					},
					{
						name: 'Get Workspace',
						value: 'getWorkspace',
						description: 'Get workspace details',
						action: 'Get workspace a workspaces',
					},
					{
						name: 'List Workspaces',
						value: 'listWorkspaces',
						description: 'List all workspaces',
						action: 'List workspaces a workspaces',
					},
					{
						name: 'Update Workspace',
						value: 'updateWorkspace',
						description: 'Update workspace information',
						action: 'Update workspace a workspaces',
					},
				],
				default: 'listWorkspaces',
			},

			// Audit Operations
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['audit'],
					},
				},
				options: [
					{
						name: 'Get Audit Logs',
						value: 'getAuditLogs',
						description: 'Get audit logs for compliance',
						action: 'Get audit logs an audit',
					},
					{
						name: 'Get Compliance Report',
						value: 'getComplianceReport',
						description: 'Generate compliance report',
						action: 'Get compliance report an audit',
					},
					{
						name: 'Export Audit Data',
						value: 'exportAuditData',
						description: 'Export audit data for external review',
						action: 'Export audit data an audit',
					},
				],
				default: 'getAuditLogs',
			},

			// Health Operations
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: {
					show: {
						resource: ['health'],
					},
				},
				options: [
					{
						name: 'Health Check',
						value: 'healthCheck',
						description: 'Check system health status',
						action: 'Health check a health',
					},
					{
						name: 'Database Stats',
						value: 'databaseStats',
						description: 'Get database statistics',
						action: 'Database stats a health',
					},
					{
						name: 'Rate Limit Status',
						value: 'rateLimitStatus',
						description: 'Check current rate limit status',
						action: 'Rate limit status a health',
					},
				],
				default: 'healthCheck',
			},

			// Common Parameters
			{
				displayName: 'Family ID',
				name: 'familyId',
				type: 'string',
				typeOptions: {
					password: true,
				},
				default: '',
				placeholder: 'family_1234567890abcdef (optional for SBD tokens)',
				description: 'The family ID for operations (required for family operations, optional for SBD token operations)',
				displayOptions: {
					show: {
						resource: ['family', 'sbdTokens'],
					},
				},
			},

			{
				displayName: 'Token ID',
				name: 'tokenId',
				type: 'string',
				typeOptions: { password: true },
				default: '',
				placeholder: 'pt_1234567890abcdef',
				description: 'The permanent token ID for revocation',
				displayOptions: {
					show: {
						resource: ['auth'],
						operation: ['revokePermanentToken'],
					},
				},
				required: true,
			},

			{
				displayName: 'Workspace ID',
				name: 'workspaceId',
				type: 'string',
				default: '',
				placeholder: 'ws_1234567890abcdef',
				description: 'The workspace ID for operations',
				displayOptions: {
					show: {
						resource: ['workspaces'],
						operation: ['getWorkspace', 'updateWorkspace', 'deleteWorkspace'],
					},
				},
				required: true,
			},

			// Additional Parameters for specific operations
			{
				displayName: 'Additional Fields',
				name: 'additionalFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				displayOptions: {
					show: {
						resource: ['auth'],
						operation: ['login', 'createPermanentToken', 'verify2FA'],
					},
				},
				options: [
					{
						displayName: '2FA Code',
						name: 'twoFaCode',
						type: 'string',
						default: '',
						placeholder: '123456',
						description: 'Two-factor authentication code',
					},
					{
						displayName: '2FA Method',
						name: 'twoFaMethod',
						type: 'options',
						options: [
							{ name: 'TOTP', value: 'totp' },
							{ name: 'Backup Code', value: 'backup' },
						],
						default: 'totp',
						description: 'Two-factor authentication method',
					},
					{
						displayName: 'Description',
						name: 'description',
						type: 'string',
						default: '',
						placeholder: 'Token for automation',
						description: 'Token description',
					},
					{
						displayName: 'Email',
						name: 'email',
						type: 'string',
						default: '',
						placeholder: 'john@example.com',
						description: 'Email for login (alternative to username)',
					},
					{
						displayName: 'Expires At',
						name: 'expiresAt',
						type: 'dateTime',
						default: '',
						description: 'Token expiration date (optional)',
					},
					{
						displayName: 'IP Restrictions',
						name: 'ipRestrictions',
						type: 'string',
						default: '',
						placeholder: '192.168.1.0/24',
						description: 'IP address restrictions (optional)',
					},
					{
						displayName: 'Password',
						name: 'password',
						type: 'string',
						typeOptions: {
							password: true,
						},
						default: '',
						description: 'User password',
					},
					{
						displayName: 'Username',
						name: 'username',
						type: 'string',
						default: '',
						placeholder: 'john_doe',
						description: 'Username for login (alternative to email)',
					},
				],
			},

			{
				displayName: 'Additional Fields',
				name: 'additionalFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				displayOptions: {
					show: {
						resource: ['family'],
						operation: ['createFamily', 'updateFamily', 'inviteMember', 'acceptInvitation', 'removeMember', 'updateMemberRole', 'setSpendingPermissions', 'emergencyAccess'],
					},
				},
				options: [
					{
						displayName: 'Allowed Categories',
						name: 'allowedCategories',
						type: 'string',
						default: '',
						placeholder: 'groceries,utilities',
						description: 'Comma-separated allowed spending categories',
					},
					{
						displayName: 'Blocked Categories',
						name: 'blockedCategories',
						type: 'string',
						default: '',
						placeholder: 'entertainment,gaming',
						description: 'Comma-separated blocked spending categories',
					},
					{
						displayName: 'Daily Limit',
						name: 'dailyLimit',
						type: 'number',
						default: 0,
						description: 'Daily spending limit',
					},
					{
						displayName: 'Description',
						name: 'description',
						type: 'string',
						default: '',
						placeholder: 'Family description',
						description: 'Family description',
					},
					{
						displayName: 'Email',
						name: 'email',
						type: 'string',
						default: '',
						placeholder: 'member@example.com',
						description: 'Member email for invitation',
					},
					{
						displayName: 'Invitation Token',
						name: 'invitationToken',
						type: 'string',
						typeOptions: {
							password: true,
						},
						default: '',
						placeholder: 'inv_1234567890abcdef',
					},
					{
						displayName: 'Member ID',
						name: 'memberId',
						type: 'string',
						default: '',
						placeholder: 'user_1234567890abcdef',
						description: 'Member user ID',
					},
					{
						displayName: 'Message',
						name: 'message',
						type: 'string',
						default: '',
						placeholder: 'Welcome to our family!',
						description: 'Invitation message',
					},
					{
						displayName: 'Monthly Limit',
						name: 'monthlyLimit',
						type: 'number',
						default: 0,
						description: 'Monthly spending limit',
					},
					{
						displayName: 'Name',
						name: 'name',
						type: 'string',
						default: '',
						placeholder: 'My Family',
						description: 'Family name',
					},
					{
						displayName: 'Reason',
						name: 'reason',
						type: 'string',
						default: '',
						placeholder: 'Lost access to account',
						description: 'Reason for emergency access',
					},
					{
						displayName: 'Role',
						name: 'role',
						type: 'options',
						options: [
							{ name: 'Member', value: 'member' },
							{ name: 'Admin', value: 'admin' },
							{ name: 'Parent', value: 'parent' },
						],
						default: 'member',
						description: 'Member role',
					},
					{
						displayName: 'Settings',
						name: 'settings',
						type: 'json',
						default: '',
						description: 'Family settings as JSON',
					},
				],
			},

			{
				displayName: 'Additional Fields',
				name: 'additionalFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				displayOptions: {
					show: {
						resource: ['workspaces'],
						operation: ['createWorkspace', 'updateWorkspace'],
					},
				},
				options: [
					{
						displayName: 'Name',
						name: 'name',
						type: 'string',
						default: '',
						placeholder: 'My Workspace',
						description: 'Workspace name',
					},
					{
						displayName: 'Description',
						name: 'description',
						type: 'string',
						default: '',
						placeholder: 'Workspace description',
						description: 'Workspace description',
					},
					{
						displayName: 'Settings',
						name: 'settings',
						type: 'json',
						default: '',
						description: 'Workspace settings as JSON',
					},
				],
			},

			{
				displayName: 'Shop Item Details',
				name: 'shopItemDetails',
				type: 'collection',
				placeholder: 'Add Shop Item Field',
				default: {},
				displayOptions: {
					show: {
						resource: ['shop'],
						operation: ['buyTheme', 'buyAvatar', 'buyBanner', 'buyBundle', 'addToCart', 'removeFromCart'],
					},
				},
				options: [
					{
						displayName: 'Avatar ID',
						name: 'avatarId',
						type: 'string',
						default: '',
						placeholder: 'emotion_tracker-static-avatar-cat-1',
						description: 'Avatar ID to purchase',
					},
					{
						displayName: 'Banner ID',
						name: 'bannerId',
						type: 'string',
						default: '',
						placeholder: 'emotion_tracker-static-banner-earth-1',
						description: 'Banner ID to purchase',
					},
					{
						displayName: 'Bundle ID',
						name: 'bundleId',
						type: 'string',
						default: '',
						placeholder: 'emotion_tracker-avatars-cat-bundle',
						description: 'Bundle ID to purchase',
					},
					{
						displayName: 'Item ID',
						name: 'itemId',
						type: 'string',
						default: '',
						placeholder: 'emotion_tracker-serenityGreen',
						description: 'Generic item ID for cart operations',
					},
					{
						displayName: 'Item Type',
						name: 'itemType',
						type: 'options',
						options: [
							{ name: 'Theme', value: 'theme' },
							{ name: 'Avatar', value: 'avatar' },
							{ name: 'Banner', value: 'banner' },
							{ name: 'Bundle', value: 'bundle' },
						],
						default: 'theme',
						description: 'Type of item',
					},
					{
						displayName: 'Theme ID',
						name: 'themeId',
						type: 'string',
						default: '',
						placeholder: 'emotion_tracker-serenityGreen',
						description: 'Theme ID to purchase',
					},
				],
			},

			{
				displayName: 'Payment Method',
				name: 'paymentMethod',
				type: 'collection',
				placeholder: 'Add Payment Field',
				default: {},
				displayOptions: {
					show: {
						resource: ['shop'],
						operation: ['buyTheme', 'buyAvatar', 'buyBanner', 'buyBundle', 'checkoutCart'],
					},
				},
				options: [
					{
						displayName: 'Payment Type',
						name: 'type',
						type: 'options',
						options: [
							{ name: 'Personal Tokens', value: 'personal' },
							{ name: 'Family Tokens', value: 'family' },
						],
						default: 'personal',
						description: 'Payment method type',
					},
					{
						displayName: 'Family ID',
						name: 'familyId',
						type: 'string',
						default: '',
						placeholder: 'family_1234567890abcdef',
						description: 'Family ID (required for family token payments)',
					},
				],
			},

			{
				displayName: 'Session ID',
				name: 'sessionId',
				type: 'string',
				default: '',
				placeholder: 'session_1234567890abcdef',
				description: 'The AI session ID for operations',
				displayOptions: {
					show: {
						resource: ['ai'],
						operation: ['getSession', 'sendMessage', 'endSession', 'setupVoiceSession', 'processVoiceInput', 'getVoiceToken'],
					},
				},
				required: true,
			},

			{
				displayName: 'Additional Fields',
				name: 'additionalFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				displayOptions: {
					show: {
						resource: ['ai'],
						operation: ['createSession', 'sendMessage', 'listSessions', 'processVoiceInput', 'invalidateCaches', 'warmupModel'],
					},
				},
				options: [
					{
						displayName: 'Agent Type',
						name: 'agentType',
						type: 'options',
						options: [
							{ name: 'Code Assistant', value: 'code' },
							{ name: 'Creative Writer', value: 'creative' },
							{ name: 'Data Analyst', value: 'data' },
							{ name: 'General Assistant', value: 'general' },
							{ name: 'Research Assistant', value: 'research' },
						],
						default: 'general',
						description: 'Type of AI agent for the session',
					},
					{
						displayName: 'Cache Pattern',
						name: 'cachePattern',
						type: 'string',
						default: '*',
						placeholder: 'model_*',
						description: 'Pattern for cache invalidation (supports wildcards)',
					},
					{
						displayName: 'Content',
						name: 'content',
						type: 'string',
						default: '',
						placeholder: 'Hello, how can I help you?',
						description: 'Message content to send to AI',
					},
					{
						displayName: 'Expiration Hours',
						name: 'expirationHours',
						type: 'number',
						default: 24,
						description: 'Session expiration time in hours',
					},
					{
						displayName: 'Message Type',
						name: 'messageType',
						type: 'options',
						options: [
							{ name: 'Text', value: 'text' },
							{ name: 'Voice', value: 'voice' },
							{ name: 'Image', value: 'image' },
						],
						default: 'text',
						description: 'Type of message content',
					},
					{
						displayName: 'Model Name',
						name: 'modelName',
						type: 'string',
						default: '',
						placeholder: 'gpt-4',
						description: 'Name of the model to warm up',
					},
					{
						displayName: 'Preferences',
						name: 'preferences',
						type: 'json',
						default: '',
						description: 'User preferences as JSON',
					},
					{
						displayName: 'Settings',
						name: 'settings',
						type: 'json',
						default: '',
						description: 'Session settings as JSON',
					},
					{
						displayName: 'Status',
						name: 'status',
						type: 'options',
						options: [
							{ name: 'Active', value: 'active' },
							{ name: 'Completed', value: 'completed' },
							{ name: 'Expired', value: 'expired' },
						],
						default: 'active',
						description: 'Filter sessions by status',
					},
					{
						displayName: 'Switch to Agent',
						name: 'switchToAgent',
						type: 'options',
						options: [
							{ name: 'Code Assistant', value: 'code' },
							{ name: 'Creative Writer', value: 'creative' },
							{ name: 'Data Analyst', value: 'data' },
							{ name: 'General Assistant', value: 'general' },
							{ name: 'Research Assistant', value: 'research' },
						],
						default: 'general',
						description: 'Switch to a different agent type during conversation',
					},
					{
						displayName: 'Voice Audio Data',
						name: 'voiceAudioData',
						type: 'string',
						default: '',
						placeholder: 'base64-encoded-audio-data',
						description: 'Base64 encoded voice audio data',
					},
					{
						displayName: 'Voice Enabled',
						name: 'voiceEnabled',
						type: 'boolean',
						default: false,
						description: 'Whether to enable voice capabilities for the session',
					},
				],
			},

			{
				displayName: 'Query Parameters',
				name: 'queryParameters',
				type: 'collection',
				placeholder: 'Add Query Parameter',
				default: {},
				displayOptions: {
					show: {
						resource: ['ai'],
						operation: ['listSessions'],
					},
				},
				options: [
					{
						displayName: 'Agent Type',
						name: 'agentType',
						type: 'options',
						options: [
							{ name: 'Code Assistant', value: 'code' },
							{ name: 'Creative Writer', value: 'creative' },
							{ name: 'Data Analyst', value: 'data' },
							{ name: 'General Assistant', value: 'general' },
							{ name: 'Research Assistant', value: 'research' },
						],
						default: 'general',
						description: 'Filter by agent type',
					},
					{
						displayName: 'Limit',
						name: 'limit',
						type: 'number',
						typeOptions: {},
						default: 50,
						description: 'Max number of results to return',
					},
					{
						displayName: 'Offset',
						name: 'offset',
						type: 'number',
						default: 0,
						description: 'Number of sessions to skip',
					},
					{
						displayName: 'Status',
						name: 'status',
						type: 'options',
						options: [
							{ name: 'Active', value: 'active' },
							{ name: 'Completed', value: 'completed' },
							{ name: 'Expired', value: 'expired' },
						],
						default: 'active',
						description: 'Filter by session status',
					},
				],
			},

			{
				displayName: 'Transfer Details',
				name: 'transferDetails',
				type: 'collection',
				placeholder: 'Add Transfer Field',
				default: {},
				displayOptions: {
					show: {
						resource: ['sbdTokens'],
						operation: ['transferTokens', 'requestTokens'],
					},
				},
				options: [
					{
						displayName: 'To Family ID',
						name: 'toFamilyId',
						type: 'string',
						default: '',
						placeholder: 'family_1234567890abcdef',
						description: 'Recipient family ID',
					},
					{
						displayName: 'Amount',
						name: 'amount',
						type: 'number',
						default: 0,
						description: 'Amount of tokens to transfer',
					},
					{
						displayName: 'Description',
						name: 'description',
						type: 'string',
						default: '',
						placeholder: 'Payment for groceries',
						description: 'Transfer description',
					},
					{
						displayName: 'Requires Approval',
						name: 'requiresApproval',
						type: 'boolean',
						default: false,
						description: 'Whether this transfer requires approval',
					},
				],
			},

			{
				displayName: 'Request ID',
				name: 'requestId',
				type: 'string',
				default: '',
				placeholder: 'req_1234567890abcdef',
				description: 'The request ID for approval/rejection',
				displayOptions: {
					show: {
						resource: ['sbdTokens'],
						operation: ['approveRequest', 'rejectRequest'],
					},
				},
				required: true,
			},

			{
				displayName: 'Query Parameters',
				name: 'queryParameters',
				type: 'collection',
				placeholder: 'Add Query Parameter',
				default: {},
				displayOptions: {
					show: {
						resource: ['family', 'sbdTokens', 'audit'],
						operation: ['listFamilies', 'getTransactionHistory', 'listPendingRequests', 'getAuditLogs'],
					},
				},
				options: [
					{
						displayName: 'Limit',
						name: 'limit',
						type: 'number',
						typeOptions: {},
						default: 50,
						description: 'Max number of results to return',
					},
					{
						displayName: 'Offset',
						name: 'offset',
						type: 'number',
						default: 0,
						description: 'Number of results to skip',
					},
					{
						displayName: 'From Date',
						name: 'fromDate',
						type: 'dateTime',
						default: '',
						description: 'Filter results from this date',
					},
					{
						displayName: 'To Date',
						name: 'toDate',
						type: 'dateTime',
						default: '',
						description: 'Filter results to this date',
					},
				],
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const resource = this.getNodeParameter('resource', 0) as string;
		const operation = this.getNodeParameter('operation', 0) as string;

		for (let itemIndex = 0; itemIndex < items.length; itemIndex++) {
			try {
				let responseData: IDataObject = {};

				switch (resource) {
					case 'auth':
						switch (operation) {
							case 'login': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const body: IDataObject = {
									password: additionalFields.password,
								};
								if (additionalFields.username) {
									body.username = additionalFields.username;
								} else if (additionalFields.email) {
									body.email = additionalFields.email;
								} else {
									throw new NodeOperationError(this.getNode(), 'Either username or email must be provided for login');
								}
								if (additionalFields.twoFaCode) {
									body.two_fa_code = additionalFields.twoFaCode;
									body.two_fa_method = additionalFields.twoFaMethod || 'totp';
								}
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/auth/login',
									body,
									json: true,
								});
								break;
							}
							case 'validateToken':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/auth/validate-token',
									json: true,
								});
								break;
							case 'refreshToken':
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/auth/refresh',
									json: true,
								});
								break;
							case 'createPermanentToken': {
								const tokenFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const tokenBody: IDataObject = {};
								if (tokenFields.description) {
									tokenBody.description = tokenFields.description;
								}
								if (tokenFields.ipRestrictions) {
									tokenBody.ip_restrictions = tokenFields.ipRestrictions;
								}
								if (tokenFields.expiresAt) {
									tokenBody.expires_at = tokenFields.expiresAt;
								}
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/auth/permanent-tokens',
									body: tokenBody,
									json: true,
								});
								break;
							}
							case 'listPermanentTokens':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/auth/permanent-tokens',
									json: true,
								});
								break;
							case 'revokePermanentToken': {
								const tokenId = this.getNodeParameter('tokenId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'DELETE',
									url: `/auth/permanent-tokens/${tokenId}`,
									json: true,
								});
								break;
							}
							case 'setup2FA':
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/auth/setup-2fa',
									json: true,
								});
								break;
							case 'verify2FA': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const body: IDataObject = {
									code: additionalFields.twoFaCode,
								};
								if (additionalFields.twoFaMethod) {
									body.method = additionalFields.twoFaMethod;
								}
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/auth/verify-2fa',
									body,
									json: true,
								});
								break;
							}
							default:
								throw new NodeOperationError(this.getNode(), `Unknown auth operation: ${operation}`);
						}
						break;
					case 'family': {
						const familyId = this.getNodeParameter('familyId', itemIndex) as string;
						if (!familyId) {
							throw new NodeOperationError(this.getNode(), 'Family ID is required for family operations');
						}
						switch (operation) {
							case 'createFamily': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const familyBody: IDataObject = {};
								if (additionalFields.name) familyBody.name = additionalFields.name;
								if (additionalFields.description) familyBody.description = additionalFields.description;
								if (additionalFields.settings) familyBody.settings = additionalFields.settings;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/family',
									body: familyBody,
									json: true,
								});
								break;
							}
							case 'getFamily':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: `/family/${familyId}`,
									json: true,
								});
								break;
							case 'updateFamily': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const familyBody: IDataObject = {};
								if (additionalFields.name) familyBody.name = additionalFields.name;
								if (additionalFields.description) familyBody.description = additionalFields.description;
								if (additionalFields.settings) familyBody.settings = additionalFields.settings;
								responseData = await this.helpers.httpRequest({
									method: 'PUT',
									url: `/family/${familyId}`,
									body: familyBody,
									json: true,
								});
								break;
							}
							case 'listFamilies': {
								const queryParameters = this.getNodeParameter('queryParameters', itemIndex, {}) as IDataObject;
								const qs: IDataObject = {};
								if (queryParameters.limit) qs.limit = queryParameters.limit;
								if (queryParameters.offset) qs.offset = queryParameters.offset;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/family',
									qs,
									json: true,
								});
								break;
							}
							case 'inviteMember': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const inviteBody: IDataObject = {
									email: additionalFields.email,
									role: additionalFields.role || 'member',
								};
								if (additionalFields.message) inviteBody.message = additionalFields.message;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/family/${familyId}/invite`,
									body: inviteBody,
									json: true,
								});
								break;
							}
							case 'acceptInvitation': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const acceptBody: IDataObject = {
									token: additionalFields.invitationToken,
								};
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/family/${familyId}/accept-invitation`,
									body: acceptBody,
									json: true,
								});
								break;
							}
							case 'removeMember': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								responseData = await this.helpers.httpRequest({
									method: 'DELETE',
									url: `/family/${familyId}/members/${additionalFields.memberId}`,
									json: true,
								});
								break;
							}
							case 'updateMemberRole': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const roleBody: IDataObject = {
									role: additionalFields.role,
								};
								responseData = await this.helpers.httpRequest({
									method: 'PUT',
									url: `/family/${familyId}/members/${additionalFields.memberId}/role`,
									body: roleBody,
									json: true,
								});
								break;
							}
							case 'setSpendingPermissions': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const permissionsBody: IDataObject = {};
								if (additionalFields.dailyLimit) permissionsBody.daily_limit = additionalFields.dailyLimit;
								if (additionalFields.monthlyLimit) permissionsBody.monthly_limit = additionalFields.monthlyLimit;
								if (additionalFields.allowedCategories) permissionsBody.allowed_categories = additionalFields.allowedCategories;
								if (additionalFields.blockedCategories) permissionsBody.blocked_categories = additionalFields.blockedCategories;
								responseData = await this.helpers.httpRequest({
									method: 'PUT',
									url: `/family/${familyId}/spending-permissions`,
									body: permissionsBody,
									json: true,
								});
								break;
							}
							case 'freezeAccount':
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/family/${familyId}/freeze`,
									json: true,
								});
								break;
							case 'unfreezeAccount':
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/family/${familyId}/unfreeze`,
									json: true,
								});
								break;
							case 'emergencyAccess': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const emergencyBody: IDataObject = {
									reason: additionalFields.reason,
								};
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/family/${familyId}/emergency-access`,
									body: emergencyBody,
									json: true,
								});
								break;
							}
							case 'getBalance':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: `/family/${familyId}/tokens/balance`,
									json: true,
								});
								break;
							case 'transferTokens': {
								const transferDetails = this.getNodeParameter('transferDetails', itemIndex, {}) as IDataObject;
								const transferBody: IDataObject = {
									to_family_id: transferDetails.toFamilyId,
									amount: transferDetails.amount,
								};
								if (transferDetails.description) transferBody.description = transferDetails.description;
								if (transferDetails.requiresApproval !== undefined) transferBody.requires_approval = transferDetails.requiresApproval;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/family/${familyId}/tokens/transfer`,
									body: transferBody,
									json: true,
								});
								break;
							}
							default:
								throw new NodeOperationError(this.getNode(), `Unknown family operation: ${operation}`);
						}
						break;
					}
					case 'sbdTokens': {
						const familyId = this.getNodeParameter('familyId', itemIndex, '') as string;
						switch (operation) {
							case 'transferTokens': {
								const transferDetails = this.getNodeParameter('transferDetails', itemIndex, {}) as IDataObject;
								const transferBody: IDataObject = {
									to_family_id: transferDetails.toFamilyId,
									amount: transferDetails.amount,
								};
								if (transferDetails.description) transferBody.description = transferDetails.description;
								if (transferDetails.requiresApproval !== undefined) transferBody.requires_approval = transferDetails.requiresApproval;

								// Use family-specific endpoint if familyId provided, otherwise use global endpoint
								const url = familyId
									? `/family/${familyId}/tokens/transfer`
									: '/tokens/transfer';

								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url,
									body: transferBody,
									json: true,
								});
								break;
							}
							case 'getBalance': {
								// Use family-specific endpoint if familyId provided, otherwise use global endpoint
								const url = familyId
									? `/family/${familyId}/tokens/balance`
									: '/tokens/balance';

								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url,
									json: true,
								});
								break;
							}
							case 'getTransactionHistory': {
								const queryParameters = this.getNodeParameter('queryParameters', itemIndex, {}) as IDataObject;
								const qs: IDataObject = {};
								if (queryParameters.limit) qs.limit = queryParameters.limit;
								if (queryParameters.offset) qs.offset = queryParameters.offset;
								if (queryParameters.fromDate) qs.from_date = queryParameters.fromDate;
								if (queryParameters.toDate) qs.to_date = queryParameters.toDate;

								// Use family-specific endpoint if familyId provided, otherwise use global endpoint
								const url = familyId
									? `/family/${familyId}/tokens/transactions`
									: '/tokens/transactions';

								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url,
									qs,
									json: true,
								});
								break;
							}
							case 'requestTokens': {
								const transferDetails = this.getNodeParameter('transferDetails', itemIndex, {}) as IDataObject;
								const requestBody: IDataObject = {
									to_family_id: transferDetails.toFamilyId,
									amount: transferDetails.amount,
								};
								if (transferDetails.description) requestBody.description = transferDetails.description;

								// Use family-specific endpoint if familyId provided, otherwise use global endpoint
								const url = familyId
									? `/family/${familyId}/tokens/request`
									: '/tokens/request';

								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url,
									body: requestBody,
									json: true,
								});
								break;
							}
							case 'approveRequest': {
								const requestId = this.getNodeParameter('requestId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/tokens/requests/${requestId}/approve`,
									json: true,
								});
								break;
							}
							case 'rejectRequest': {
								const requestId = this.getNodeParameter('requestId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/tokens/requests/${requestId}/reject`,
									json: true,
								});
								break;
							}
							case 'listPendingRequests': {
								const queryParameters = this.getNodeParameter('queryParameters', itemIndex, {}) as IDataObject;
								const qs: IDataObject = {};
								if (queryParameters.limit) qs.limit = queryParameters.limit;
								if (queryParameters.offset) qs.offset = queryParameters.offset;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/tokens/requests',
									qs,
									json: true,
								});
								break;
							}
							default:
								throw new NodeOperationError(this.getNode(), `Unknown token operation: ${operation}`);
						}
						break;
					}
					case 'health':
						switch (operation) {
							case 'healthCheck':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/health',
									json: true,
								});
								break;
							case 'databaseStats':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/health/database',
									json: true,
								});
								break;
							case 'rateLimitStatus':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/health/rate-limit',
									json: true,
								});
								break;
							default:
								throw new NodeOperationError(this.getNode(), `Unknown health operation: ${operation}`);
						}
						break;
					case 'workspaces':
						switch (operation) {
							case 'createWorkspace': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const workspaceBody: IDataObject = {};
								if (additionalFields.name) workspaceBody.name = additionalFields.name;
								if (additionalFields.description) workspaceBody.description = additionalFields.description;
								if (additionalFields.settings) workspaceBody.settings = additionalFields.settings;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/workspaces',
									body: workspaceBody,
									json: true,
								});
								break;
							}
							case 'getWorkspace': {
								const workspaceId = this.getNodeParameter('workspaceId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: `/workspaces/${workspaceId}`,
									json: true,
								});
								break;
							}
							case 'updateWorkspace': {
								const workspaceId = this.getNodeParameter('workspaceId', itemIndex) as string;
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const workspaceBody: IDataObject = {};
								if (additionalFields.name) workspaceBody.name = additionalFields.name;
								if (additionalFields.description) workspaceBody.description = additionalFields.description;
								if (additionalFields.settings) workspaceBody.settings = additionalFields.settings;
								responseData = await this.helpers.httpRequest({
									method: 'PUT',
									url: `/workspaces/${workspaceId}`,
									body: workspaceBody,
									json: true,
								});
								break;
							}
							case 'listWorkspaces': {
								const queryParameters = this.getNodeParameter('queryParameters', itemIndex, {}) as IDataObject;
								const qs: IDataObject = {};
								if (queryParameters.limit) qs.limit = queryParameters.limit;
								if (queryParameters.offset) qs.offset = queryParameters.offset;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/workspaces',
									qs,
									json: true,
								});
								break;
							}
							case 'deleteWorkspace': {
								const workspaceId = this.getNodeParameter('workspaceId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'DELETE',
									url: `/workspaces/${workspaceId}`,
									json: true,
								});
								break;
							}
							default:
								throw new NodeOperationError(this.getNode(), `Unknown workspace operation: ${operation}`);
						}
						break;
					case 'audit':
						switch (operation) {
							case 'getAuditLogs': {
								const queryParameters = this.getNodeParameter('queryParameters', itemIndex, {}) as IDataObject;
								const qs: IDataObject = {};
								if (queryParameters.limit) qs.limit = queryParameters.limit;
								if (queryParameters.offset) qs.offset = queryParameters.offset;
								if (queryParameters.fromDate) qs.from_date = queryParameters.fromDate;
								if (queryParameters.toDate) qs.to_date = queryParameters.toDate;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/audit/logs',
									qs,
									json: true,
								});
								break;
							}
							case 'getComplianceReport': {
								const queryParameters = this.getNodeParameter('queryParameters', itemIndex, {}) as IDataObject;
								const qs: IDataObject = {};
								if (queryParameters.fromDate) qs.from_date = queryParameters.fromDate;
								if (queryParameters.toDate) qs.to_date = queryParameters.toDate;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/audit/compliance-report',
									qs,
									json: true,
								});
								break;
							}
							case 'exportAuditData': {
								const queryParameters = this.getNodeParameter('queryParameters', itemIndex, {}) as IDataObject;
								const qs: IDataObject = {};
								if (queryParameters.fromDate) qs.from_date = queryParameters.fromDate;
								if (queryParameters.toDate) qs.to_date = queryParameters.toDate;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/audit/export',
									qs,
									json: true,
								});
								break;
							}
							default:
								throw new NodeOperationError(this.getNode(), `Unknown audit operation: ${operation}`);
						}
						break;
					case 'shop':
						switch (operation) {
							case 'getPaymentOptions':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/shop/payment-options',
									json: true,
								});
								break;
							case 'buyTheme': {
								const shopItemDetails = this.getNodeParameter('shopItemDetails', itemIndex, {}) as IDataObject;
								const paymentMethod = this.getNodeParameter('paymentMethod', itemIndex, {}) as IDataObject;
								const body: IDataObject = {
									theme_id: shopItemDetails.themeId,
								};
								if (paymentMethod.type && paymentMethod.type !== 'personal') {
									body.payment_method = {
										type: paymentMethod.type,
										family_id: paymentMethod.familyId,
									};
								}
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/shop/themes/buy',
									body,
									json: true,
								});
								break;
							}
							case 'buyAvatar': {
								const shopItemDetails = this.getNodeParameter('shopItemDetails', itemIndex, {}) as IDataObject;
								const paymentMethod = this.getNodeParameter('paymentMethod', itemIndex, {}) as IDataObject;
								const body: IDataObject = {
									avatar_id: shopItemDetails.avatarId,
								};
								if (paymentMethod.type && paymentMethod.type !== 'personal') {
									body.payment_method = {
										type: paymentMethod.type,
										family_id: paymentMethod.familyId,
									};
								}
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/shop/avatars/buy',
									body,
									json: true,
								});
								break;
							}
							case 'buyBanner': {
								const shopItemDetails = this.getNodeParameter('shopItemDetails', itemIndex, {}) as IDataObject;
								const paymentMethod = this.getNodeParameter('paymentMethod', itemIndex, {}) as IDataObject;
								const body: IDataObject = {
									banner_id: shopItemDetails.bannerId,
								};
								if (paymentMethod.type && paymentMethod.type !== 'personal') {
									body.payment_method = {
										type: paymentMethod.type,
										family_id: paymentMethod.familyId,
									};
								}
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/shop/banners/buy',
									body,
									json: true,
								});
								break;
							}
							case 'buyBundle': {
								const shopItemDetails = this.getNodeParameter('shopItemDetails', itemIndex, {}) as IDataObject;
								const paymentMethod = this.getNodeParameter('paymentMethod', itemIndex, {}) as IDataObject;
								const body: IDataObject = {
									bundle_id: shopItemDetails.bundleId,
								};
								if (paymentMethod.type && paymentMethod.type !== 'personal') {
									body.payment_method = {
										type: paymentMethod.type,
										family_id: paymentMethod.familyId,
									};
								}
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/shop/bundles/buy',
									body,
									json: true,
								});
								break;
							}
							case 'getOwnedThemes':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/shop/themes/owned',
									json: true,
								});
								break;
							case 'getOwnedAvatars':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/shop/avatars/owned',
									json: true,
								});
								break;
							case 'getOwnedBanners':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/shop/banners/owned',
									json: true,
								});
								break;
							case 'getOwnedBundles':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/shop/bundles/owned',
									json: true,
								});
								break;
							case 'getRentedThemes':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/shop/themes/rented',
									json: true,
								});
								break;
							case 'getRentedAvatars':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/shop/avatars/rented',
									json: true,
								});
								break;
							case 'getRentedBanners':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/shop/banners/rented',
									json: true,
								});
								break;
							case 'getShopCart':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/shop/cart',
									json: true,
								});
								break;
							case 'addToCart': {
								const shopItemDetails = this.getNodeParameter('shopItemDetails', itemIndex, {}) as IDataObject;
								const body: IDataObject = {
									item_id: shopItemDetails.itemId,
									item_type: shopItemDetails.itemType,
								};
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/shop/cart/add',
									body,
									json: true,
								});
								break;
							}
							case 'removeFromCart': {
								const shopItemDetails = this.getNodeParameter('shopItemDetails', itemIndex, {}) as IDataObject;
								const body: IDataObject = {
									item_id: shopItemDetails.itemId,
									item_type: shopItemDetails.itemType,
								};
								responseData = await this.helpers.httpRequest({
									method: 'DELETE',
									url: '/shop/cart/remove',
									body,
									json: true,
								});
								break;
							}
							case 'clearCart':
								responseData = await this.helpers.httpRequest({
									method: 'DELETE',
									url: '/shop/cart/clear',
									json: true,
								});
								break;
							case 'checkoutCart': {
								const paymentMethod = this.getNodeParameter('paymentMethod', itemIndex, {}) as IDataObject;
								const body: IDataObject = {};
								if (paymentMethod.type && paymentMethod.type !== 'personal') {
									body.payment_method = {
										type: paymentMethod.type,
										family_id: paymentMethod.familyId,
									};
								}
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/shop/cart/checkout',
									body,
									json: true,
								});
								break;
							}
							default:
								throw new NodeOperationError(this.getNode(), `Unknown shop operation: ${operation}`);
						}
						break;
					case 'ai':
						switch (operation) {
							case 'createSession': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const body: IDataObject = {};
								if (additionalFields.agentType) body.agent_type = additionalFields.agentType;
								if (additionalFields.expirationHours) body.expiration_hours = additionalFields.expirationHours;
								if (additionalFields.preferences) body.preferences = JSON.parse(additionalFields.preferences as string);
								if (additionalFields.settings) body.settings = JSON.parse(additionalFields.settings as string);
								if (additionalFields.voiceEnabled) body.voice_enabled = additionalFields.voiceEnabled;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/ai/sessions',
									body,
									json: true,
								});
								break;
							}
							case 'getSession': {
								const sessionId = this.getNodeParameter('sessionId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: `/ai/sessions/${sessionId}`,
									json: true,
								});
								break;
							}
							case 'listSessions': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const queryParameters = this.getNodeParameter('queryParameters', itemIndex, {}) as IDataObject;
								const qs: IDataObject = {};
								if (queryParameters.agentType) qs.agent_type = queryParameters.agentType;
								if (queryParameters.limit) qs.limit = queryParameters.limit;
								if (queryParameters.offset) qs.offset = queryParameters.offset;
								if (queryParameters.status) qs.status = queryParameters.status;
								if (additionalFields.status) qs.status = additionalFields.status;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/ai/sessions',
									qs,
									json: true,
								});
								break;
							}
							case 'sendMessage': {
								const sessionId = this.getNodeParameter('sessionId', itemIndex) as string;
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const body: IDataObject = {};
								if (additionalFields.content) body.content = additionalFields.content;
								if (additionalFields.messageType) body.message_type = additionalFields.messageType;
								if (additionalFields.switchToAgent) body.switch_to_agent = additionalFields.switchToAgent;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/ai/sessions/${sessionId}/messages`,
									body,
									json: true,
								});
								break;
							}
							case 'endSession': {
								const sessionId = this.getNodeParameter('sessionId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/ai/sessions/${sessionId}/end`,
									json: true,
								});
								break;
							}
							case 'setupVoiceSession': {
								const sessionId = this.getNodeParameter('sessionId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/ai/sessions/${sessionId}/voice/setup`,
									json: true,
								});
								break;
							}
							case 'processVoiceInput': {
								const sessionId = this.getNodeParameter('sessionId', itemIndex) as string;
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const body: IDataObject = {};
								if (additionalFields.voiceAudioData) body.audio_data = additionalFields.voiceAudioData;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: `/ai/sessions/${sessionId}/voice/process`,
									body,
									json: true,
								});
								break;
							}
							case 'getVoiceToken': {
								const sessionId = this.getNodeParameter('sessionId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: `/ai/sessions/${sessionId}/voice/token`,
									json: true,
								});
								break;
							}
							case 'getSessionPerformance': {
								const sessionId = this.getNodeParameter('sessionId', itemIndex) as string;
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: `/ai/sessions/${sessionId}/performance`,
									json: true,
								});
								break;
							}
							case 'getPerformanceMetrics':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/ai/performance/metrics',
									json: true,
								});
								break;
							case 'getStats':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/ai/stats',
									json: true,
								});
								break;
							case 'getDetailedHealthCheck':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/ai/health/detailed',
									json: true,
								});
								break;
							case 'getModelWarmupStatus':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/ai/models/warmup/status',
									json: true,
								});
								break;
							case 'warmupModel': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const body: IDataObject = {};
								if (additionalFields.modelName) body.model_name = additionalFields.modelName;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/ai/models/warmup',
									body,
									json: true,
								});
								break;
							}
							case 'invalidateCaches': {
								const additionalFields = this.getNodeParameter('additionalFields', itemIndex, {}) as IDataObject;
								const body: IDataObject = {};
								if (additionalFields.cachePattern) body.pattern = additionalFields.cachePattern;
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/ai/cache/invalidate',
									body,
									json: true,
								});
								break;
							}
							case 'triggerCleanup':
								responseData = await this.helpers.httpRequest({
									method: 'POST',
									url: '/ai/cleanup',
									json: true,
								});
								break;
							case 'healthCheck':
								responseData = await this.helpers.httpRequest({
									method: 'GET',
									url: '/ai/health',
									json: true,
								});
								break;
							default:
								throw new NodeOperationError(this.getNode(), `Unknown AI operation: ${operation}`);
						}
						break;
					default:
						throw new NodeOperationError(this.getNode(), `Unknown resource: ${resource}`);
				}

				returnData.push({
					json: responseData,
					pairedItem: {
						item: itemIndex,
					},
				});

			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: error.message },
						error,
						pairedItem: {
							item: itemIndex,
						},
					});
					continue;
				}

				throw new NodeOperationError(this.getNode(), error, {
					itemIndex,
				});
			}
		}

		return [returnData];
	}
}
