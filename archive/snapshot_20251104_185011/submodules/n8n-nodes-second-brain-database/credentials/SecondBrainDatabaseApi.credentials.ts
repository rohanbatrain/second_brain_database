import type {
	IAuthenticateGeneric,
	Icon,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class SecondBrainDatabaseApi implements ICredentialType {
	name = 'secondBrainDatabaseApi';

	displayName = 'Second Brain Database API';

	icon: Icon = { light: 'file:../icons/github.svg', dark: 'file:../icons/github.dark.svg' };

	documentationUrl = 'https://github.com/rohanbatrain/second_brain_database';

	properties: INodeProperties[] = [
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'http://localhost:8000',
			placeholder: 'https://your-api-domain.com',
			description: 'The base URL of your Second Brain Database API',
			required: true,
		},
		{
			displayName: 'Authentication Method',
			name: 'authMethod',
			type: 'options',
			options: [
				{
					name: 'Permanent Token',
					value: 'permanentToken',
					description: 'Use a permanent API token (recommended for automation)',
				},
				{
					name: 'JWT Token',
					value: 'jwtToken',
					description: 'Use a temporary JWT token (expires after 30 minutes)',
				},
			],
			default: 'permanentToken',
			required: true,
		},
		{
			displayName: 'Permanent Token',
			name: 'permanentToken',
			type: 'string',
			typeOptions: {
				password: true,
			},
			default: '',
			description: 'Your permanent API token starting with "sbd_permanent_"',
			displayOptions: {
				show: {
					authMethod: ['permanentToken'],
				},
			},
			required: true,
		},
		{
			displayName: 'JWT Token',
			name: 'jwtToken',
			type: 'string',
			typeOptions: {
				password: true,
			},
			default: '',
			description: 'Your JWT access token (expires after 30 minutes)',
			displayOptions: {
				show: {
					authMethod: ['jwtToken'],
				},
			},
			required: true,
		},
		{
			displayName: 'Client Side Encryption',
			name: 'clientSideEncryption',
			type: 'boolean',
			default: false,
			description: 'Enable client-side encryption for sensitive data',
		},
		{
			displayName: 'Encryption Secret Key',
			name: 'encryptionSecretKey',
			type: 'string',
			typeOptions: {
				password: true,
			},
			default: '',
			description: 'Secret key for client-side encryption (required when encryption is enabled)',
			displayOptions: {
				show: {
					clientSideEncryption: [true],
				},
			},
			required: true,
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '={{$credentials.authMethod === "permanentToken" ? "Bearer " + $credentials.permanentToken : "Bearer " + $credentials.jwtToken}}',
				'X-Client-Side-Encryption': '={{$credentials.clientSideEncryption ? "true" : "false"}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '/health',
			method: 'GET',
		},
	};
}