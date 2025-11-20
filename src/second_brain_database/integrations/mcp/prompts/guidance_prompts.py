"""
Comprehensive Guidance Prompts

Contextual guidance prompts for various operations including family management,
shop navigation, workspace operations, security setup, and troubleshooting.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ....config import settings
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail
from ..mcp_instance import get_mcp_server
from ..security import get_mcp_user_context

logger = get_logger(prefix="[MCP_GuidancePrompts]")

# Import manager instances
from ....database import db_manager

# Get the shared MCP server instance
mcp_server = get_mcp_server()

if mcp_server is not None:

    @mcp_server.prompt("family_management_guide")
    async def family_management_guidance_prompt() -> str:
        """
        Provide comprehensive family management guidance with user context.

        Offers personalized guidance for family operations based on the user's
        current family memberships, roles, and available actions.

        Returns:
            Contextual family management guidance prompt
        """
        try:
            user_context = get_mcp_user_context()

            # Get user's family information for context
            families_collection = db_manager.get_collection("families")
            user_families = await families_collection.find({"members.user_id": user_context.user_id}).to_list(
                length=None
            )

            # Determine user's roles and capabilities
            owned_families = [f for f in user_families if f.get("owner_id") == user_context.user_id]
            admin_families = [
                f
                for f in user_families
                if any(
                    m.get("user_id") == user_context.user_id and m.get("role") == "admin" for m in f.get("members", [])
                )
            ]

            # Create audit trail
            await create_mcp_audit_trail(
                operation="family_management_guidance_prompt",
                user_context=user_context,
                resource_type="prompt",
                resource_id="family_management_guide",
                metadata={"family_count": len(user_families)},
            )

            prompt = f"""
# Family Management Assistant

You are helping **{user_context.username}** manage family accounts in the Second Brain Database system.

## Current Family Status
- **Total Families**: {len(user_families)}
- **Owned Families**: {len(owned_families)}
- **Admin Families**: {len(admin_families)}
- **Member-only Families**: {len(user_families) - len(admin_families)}

## Available Operations

### Family Creation & Management
- **Create Family**: Set up new family accounts with automatic SBD wallet creation
- **Update Settings**: Modify family name, description, and configuration
- **Delete Family**: Permanently remove families (owner only)

### Member Management
- **Invite Members**: Send email invitations with role assignment (member/admin)
- **Remove Members**: Remove members from families (admin required)
- **Update Roles**: Promote/demote members between member and admin roles
- **Manage Relationships**: Set bidirectional family relationships

### SBD Token Management
- **View Balance**: Check family SBD account balance and transaction history
- **Token Requests**: Create and review SBD token requests
- **Spending Permissions**: Configure member spending permissions
- **Account Controls**: Freeze/unfreeze family accounts for security

### Administrative Functions
- **Audit Logs**: View comprehensive family activity logs
- **Statistics**: Access family usage and financial analytics
- **Backup Admins**: Designate backup administrators for continuity
- **Emergency Access**: Handle emergency administrative situations

## Security Guidelines
- **Always verify permissions** before performing administrative actions
- **Log all operations** for audit and compliance purposes
- **Respect family limits** and quotas to prevent abuse
- **Follow approval workflows** for financial transactions
- **Maintain member privacy** according to role-based access controls

## Best Practices
1. **Regular Reviews**: Periodically review family membership and permissions
2. **Clear Communication**: Use invitation messages to explain family purposes
3. **Financial Oversight**: Monitor SBD spending and approve requests promptly
4. **Security Monitoring**: Watch for unusual activity and investigate anomalies
5. **Backup Planning**: Ensure multiple admins for important families

## Common Workflows

### Adding New Family Members
1. Use `add_family_member` with email and desired role
2. Include personal message explaining family purpose
3. Set appropriate relationship type if applicable
4. Configure spending permissions based on trust level

### Managing SBD Requests
1. Review pending requests with `get_token_requests`
2. Evaluate request purpose and amount reasonableness
3. Approve or deny with clear reasoning
4. Monitor spending patterns for budget management

### Family Security Management
1. Regular audit log reviews for suspicious activity
2. Update member roles based on participation and trust
3. Use account freezing for emergency situations
4. Maintain backup admin assignments

## Error Handling
- **Permission Errors**: Ensure you have appropriate admin/owner role
- **Limit Exceeded**: Check family member limits and SBD quotas
- **Invalid Operations**: Verify family exists and user has access
- **Network Issues**: Retry operations and check system status

## Support Resources
- Use `get_family_info` for detailed family status
- Check `get_family_statistics` for usage analytics
- Review `get_admin_actions_log` for audit trails
- Access system status via health check endpoints

Remember: Family management requires careful balance of accessibility and security. Always prioritize member safety and financial responsibility.

---
*Generated at {datetime.now(timezone.utc).isoformat()} for user {user_context.username}*
"""

            logger.info("Provided family management guidance prompt to user %s", user_context.user_id)
            return prompt.strip()

        except Exception as e:
            logger.error("Failed to generate family management guidance prompt: %s", e)
            return f"Error generating family management guidance: {str(e)}"

    @mcp_server.prompt("shop_navigation_guide")
    async def shop_navigation_guidance_prompt() -> str:
        """
        Provide shop navigation and purchase assistance guidance.

        Offers guidance for browsing the digital shop, making purchases,
        and managing digital assets effectively.

        Returns:
            Shop navigation and purchase guidance prompt
        """
        try:
            user_context = get_mcp_user_context()

            # Get user's current SBD balance and assets for context
            users_collection = db_manager.get_collection("users")
            user_data = await users_collection.find_one(
                {"_id": user_context.user_id}, {"sbd_balance": 1, "sbd_stats": 1}
            )

            current_balance = user_data.get("sbd_balance", 0) if user_data else 0

            # Create audit trail
            await create_mcp_audit_trail(
                operation="shop_navigation_guidance_prompt",
                user_context=user_context,
                resource_type="prompt",
                resource_id="shop_navigation_guide",
                metadata={"user_balance": current_balance},
            )

            prompt = f"""
# Digital Shop Navigation Assistant

Welcome **{user_context.username}** to the Second Brain Database Digital Shop!

## Current Account Status
- **SBD Balance**: {current_balance} tokens
- **Spending Power**: {"Good" if current_balance > 100 else "Limited" if current_balance > 0 else "No balance"}

## Shop Categories

### Avatars
- **Profile Pictures**: Personalize your account appearance
- **Animated Avatars**: Dynamic profile representations
- **Seasonal Collections**: Limited-time themed avatars
- **Premium Designs**: High-quality artistic avatars

### Banners
- **Profile Banners**: Customize your profile header
- **Animated Banners**: Eye-catching motion graphics
- **Themed Collections**: Coordinated banner sets
- **Custom Designs**: Unique artistic banners

### Themes
- **Interface Themes**: Customize application appearance
- **Color Schemes**: Personalized color palettes
- **Layout Variations**: Different interface arrangements
- **Accessibility Themes**: High contrast and readable options

## Purchase Options

### Buying vs Renting
- **Purchase**: Permanent ownership, higher upfront cost, unlimited use
- **Rental**: Temporary access, lower cost, time-limited usage
- **Recommendation**: Rent first to try, then purchase favorites

### Smart Shopping Tips
1. **Browse Featured Items**: Often better value and quality
2. **Check New Arrivals**: Latest designs and seasonal items
3. **Compare Prices**: Evaluate purchase vs rental costs
4. **Read Descriptions**: Understand what you're getting
5. **Preview Assets**: Use preview URLs to see items before buying

## Available Operations

### Browsing & Discovery
- **List Items**: Browse all available shop items with filtering
- **Search**: Find specific items by name, type, or tags
- **Categories**: Browse by avatar, banner, or theme categories
- **Featured**: View promoted and recommended items
- **New Arrivals**: See the latest additions to the shop

### Purchase Management
- **Buy Items**: Purchase items for permanent ownership
- **Rent Assets**: Temporary access to premium items
- **Transaction History**: Review all your purchases and rentals
- **Refund Requests**: Request refunds for eligible purchases

### Asset Management
- **View Assets**: See all owned and rented items
- **Activate Items**: Set avatars, banners, or themes as active
- **Extend Rentals**: Extend rental periods for continued access
- **Cancel Rentals**: End rental agreements early

## Financial Management

### SBD Token Strategy
- **Earning Tokens**: Participate in family activities and system rewards
- **Budget Planning**: Set monthly spending limits
- **Value Assessment**: Compare item costs to usage frequency
- **Bulk Purchases**: Consider package deals for better value

### Spending Analytics
- **Track Expenses**: Monitor spending patterns and trends
- **Category Analysis**: See where you spend most tokens
- **ROI Evaluation**: Assess value from purchased vs rented items
- **Budget Alerts**: Set up spending notifications

## Best Practices

### Smart Shopping
1. **Start with Rentals**: Test items before committing to purchase
2. **Seasonal Timing**: Buy seasonal items during off-peak periods
3. **Bundle Opportunities**: Look for coordinated item sets
4. **Quality Focus**: Invest in high-quality items you'll use frequently
5. **Balance Variety**: Mix purchases and rentals for diverse options

### Asset Organization
1. **Regular Reviews**: Periodically assess your asset collection
2. **Active Rotation**: Change active items regularly for variety
3. **Rental Management**: Track rental expiration dates
4. **Storage Optimization**: Keep frequently used items easily accessible

## Troubleshooting

### Common Issues
- **Insufficient Balance**: Earn more SBD tokens or request family transfers
- **Purchase Failures**: Check network connection and retry
- **Asset Not Appearing**: Allow time for processing and refresh
- **Rental Expired**: Extend rental or purchase item for continued access

### Support Actions
- **Check Balance**: Verify current SBD token balance
- **Transaction Status**: Review recent purchase attempts
- **Asset Verification**: Confirm item ownership and activation
- **System Status**: Check for shop maintenance or issues

## Recommendations Based on Your Profile
{"- **New User**: Start with rental items to explore preferences" if current_balance < 50 else ""}
{"- **Active Shopper**: Consider purchasing frequently rented items" if current_balance > 200 else ""}
{"- **Budget Conscious**: Focus on featured items and seasonal sales" if current_balance < 100 else ""}

Remember: The digital shop is designed to enhance your Second Brain Database experience. Shop responsibly within your means and enjoy personalizing your digital presence!

---
*Generated at {datetime.now(timezone.utc).isoformat()} for user {user_context.username}*
*Current SBD Balance: {current_balance} tokens*
"""

            logger.info("Provided shop navigation guidance prompt to user %s", user_context.user_id)
            return prompt.strip()

        except Exception as e:
            logger.error("Failed to generate shop navigation guidance prompt: %s", e)
            return f"Error generating shop navigation guidance: {str(e)}"

    @mcp_server.prompt("workspace_management_guide")
    async def workspace_management_guidance_prompt() -> str:
        """
        Provide workspace management guidance for team operations.

        Offers comprehensive guidance for workspace creation, member management,
        and team collaboration within the workspace system.

        Returns:
            Workspace management guidance prompt
        """
        try:
            user_context = get_mcp_user_context()

            # Get user's workspace information for context
            workspaces_collection = db_manager.get_collection("workspaces")
            user_workspaces = await workspaces_collection.find({"members.user_id": user_context.user_id}).to_list(
                length=None
            )

            # Determine user's roles and capabilities
            owned_workspaces = [w for w in user_workspaces if w.get("owner_id") == user_context.user_id]
            admin_workspaces = [
                w
                for w in user_workspaces
                if any(
                    m.get("user_id") == user_context.user_id and m.get("role") == "admin" for m in w.get("members", [])
                )
            ]

            # Create audit trail
            await create_mcp_audit_trail(
                operation="workspace_management_guidance_prompt",
                user_context=user_context,
                resource_type="prompt",
                resource_id="workspace_management_guide",
                metadata={"workspace_count": len(user_workspaces)},
            )

            prompt = f"""
# Workspace Management Assistant

You are helping **{user_context.username}** manage team workspaces in the Second Brain Database system.

## Current Workspace Status
- **Total Workspaces**: {len(user_workspaces)}
- **Owned Workspaces**: {len(owned_workspaces)}
- **Admin Workspaces**: {len(admin_workspaces)}
- **Member-only Workspaces**: {len(user_workspaces) - len(admin_workspaces)}

## Workspace Operations

### Workspace Creation & Management
- **Create Workspace**: Set up new team workspaces with wallet integration
- **Update Settings**: Modify workspace name, description, and configuration
- **Delete Workspace**: Permanently remove workspaces (owner only)
- **Workspace Analytics**: Access usage statistics and team metrics

### Team Member Management
- **Add Members**: Invite existing users to join workspaces
- **Remove Members**: Remove team members from workspaces
- **Update Roles**: Manage member permissions and administrative access
- **Member Analytics**: Track team participation and activity

### Financial Management
- **Workspace Wallet**: Manage team SBD token funds
- **Token Requests**: Create and approve workspace funding requests
- **Spending Permissions**: Configure team member wallet access
- **Transaction History**: Monitor workspace financial activity

### Administrative Functions
- **Audit Logs**: Review comprehensive workspace activity
- **Health Monitoring**: Check workspace system status
- **Backup Admins**: Designate backup administrators
- **Emergency Access**: Handle critical administrative situations

## Team Collaboration Best Practices

### Workspace Setup
1. **Clear Purpose**: Define workspace goals and objectives
2. **Appropriate Naming**: Use descriptive, professional names
3. **Member Onboarding**: Provide clear role definitions and expectations
4. **Permission Structure**: Set up appropriate access levels

### Member Management
1. **Role Clarity**: Clearly define admin vs member responsibilities
2. **Regular Reviews**: Periodically assess team membership
3. **Communication**: Maintain open channels for team coordination
4. **Performance Tracking**: Monitor member contributions and engagement

### Financial Oversight
1. **Budget Planning**: Establish workspace spending budgets
2. **Approval Workflows**: Implement token request approval processes
3. **Expense Tracking**: Monitor spending patterns and categories
4. **Financial Reporting**: Regular review of workspace finances

## Security & Governance

### Access Control
- **Principle of Least Privilege**: Grant minimum necessary permissions
- **Regular Audits**: Review member access and activity logs
- **Role Rotation**: Consider periodic admin role changes
- **Emergency Procedures**: Establish protocols for urgent situations

### Compliance & Monitoring
- **Activity Logging**: All workspace actions are automatically logged
- **Audit Trails**: Maintain comprehensive records for compliance
- **Performance Metrics**: Track workspace health and usage
- **Security Monitoring**: Watch for unusual or suspicious activity

## Common Workflows

### Setting Up a New Workspace
1. Create workspace with clear name and description
2. Configure initial settings and permissions
3. Add core team members with appropriate roles
4. Set up wallet permissions and spending limits
5. Establish communication and collaboration protocols

### Managing Team Changes
1. Regular member reviews and role assessments
2. Onboarding new members with proper orientation
3. Offboarding departing members securely
4. Updating permissions based on role changes

### Financial Management
1. Regular wallet balance monitoring
2. Token request review and approval processes
3. Spending analysis and budget adjustments
4. Financial reporting and transparency

## Troubleshooting

### Common Issues
- **Permission Denied**: Verify admin/owner role for administrative actions
- **Member Not Found**: Ensure user exists in system before adding
- **Wallet Issues**: Check workspace wallet status and permissions
- **Access Problems**: Review member roles and workspace settings

### Resolution Steps
1. **Verify Permissions**: Check your role in the workspace
2. **Check System Status**: Ensure workspace systems are operational
3. **Review Logs**: Examine audit logs for error details
4. **Contact Support**: Use system health checks for assistance

## Advanced Features

### Analytics & Reporting
- **Usage Statistics**: Track workspace activity and engagement
- **Financial Analytics**: Analyze spending patterns and trends
- **Member Performance**: Monitor individual and team metrics
- **Health Dashboards**: Real-time workspace status monitoring

### Integration Capabilities
- **API Access**: Programmatic workspace management
- **Automation**: Automated workflows and processes
- **Monitoring**: Real-time alerts and notifications
- **Backup Systems**: Data protection and recovery

## Recommendations for Your Workspaces
{"- **New to Workspaces**: Start with small teams to learn the system" if len(user_workspaces) == 0 else ""}
{"- **Growing Teams**: Consider workspace limits and scaling strategies" if len(user_workspaces) > 3 else ""}
{"- **Multiple Workspaces**: Implement consistent management practices" if len(owned_workspaces) > 1 else ""}

Remember: Effective workspace management requires balancing team autonomy with appropriate oversight. Focus on clear communication, proper permissions, and regular monitoring for successful team collaboration.

---
*Generated at {datetime.now(timezone.utc).isoformat()} for user {user_context.username}*
"""

            logger.info("Provided workspace management guidance prompt to user %s", user_context.user_id)
            return prompt.strip()

        except Exception as e:
            logger.error("Failed to generate workspace management guidance prompt: %s", e)
            return f"Error generating workspace management guidance: {str(e)}"

    @mcp_server.prompt("security_setup_guide")
    async def security_setup_guidance_prompt() -> str:
        """
        Provide security setup guidance for account protection.

        Offers comprehensive guidance for setting up and maintaining
        account security including 2FA, lockdowns, and best practices.

        Returns:
            Security setup guidance prompt
        """
        try:
            user_context = get_mcp_user_context()

            # Get user's current security status for context
            users_collection = db_manager.get_collection("users")
            user_data = await users_collection.find_one(
                {"_id": user_context.user_id}, {"two_factor": 1, "security": 1, "email_verified": 1}
            )

            # Analyze current security status
            two_fa_enabled = user_data.get("two_factor", {}).get("enabled", False) if user_data else False
            email_verified = user_data.get("email_verified", False) if user_data else False
            ip_lockdown = (
                user_data.get("security", {}).get("ip_lockdown", {}).get("enabled", False) if user_data else False
            )
            ua_lockdown = (
                user_data.get("security", {}).get("user_agent_lockdown", {}).get("enabled", False)
                if user_data
                else False
            )

            # Create audit trail
            await create_mcp_audit_trail(
                operation="security_setup_guidance_prompt",
                user_context=user_context,
                resource_type="prompt",
                resource_id="security_setup_guide",
                metadata={"two_fa_enabled": two_fa_enabled, "lockdowns_active": ip_lockdown or ua_lockdown},
            )

            prompt = f"""
# Account Security Setup Assistant

Welcome **{user_context.username}**! Let's secure your Second Brain Database account.

## Current Security Status
- **Email Verified**: {"✅ Yes" if email_verified else "❌ No - Please verify your email"}
- **Two-Factor Authentication**: {"✅ Enabled" if two_fa_enabled else "❌ Disabled - Highly recommended"}
- **IP Address Lockdown**: {"✅ Active" if ip_lockdown else "❌ Inactive"}
- **User Agent Lockdown**: {"✅ Active" if ua_lockdown else "❌ Inactive"}

## Security Recommendations

### Essential Security (Required)
1. **Email Verification**: Verify your email address for account recovery
2. **Strong Password**: Use a unique, complex password (12+ characters)
3. **Two-Factor Authentication**: Enable 2FA for login protection
4. **Regular Password Updates**: Change password every 6-12 months

### Advanced Security (Recommended)
1. **IP Address Lockdown**: Restrict access to trusted IP addresses
2. **User Agent Lockdown**: Limit access to trusted devices/browsers
3. **Backup Codes**: Generate and securely store 2FA backup codes
4. **Security Monitoring**: Regular review of login activity

## Security Features Available

### Two-Factor Authentication (2FA)
- **Setup Process**: Generate QR code for authenticator app
- **Backup Codes**: Emergency access codes for device loss
- **Recovery Options**: Multiple recovery methods available
- **App Compatibility**: Works with Google Authenticator, Authy, etc.

### Security Lockdowns
- **IP Lockdown**: Restrict account access to specific IP addresses
- **User Agent Lockdown**: Limit access to trusted browsers/devices
- **Temporary Access**: One-time access codes for new locations
- **Emergency Override**: Admin-assisted access for emergencies

### Account Monitoring
- **Login History**: Track all account access attempts
- **Security Events**: Monitor suspicious activity
- **Failed Attempts**: Alert on repeated login failures
- **Device Management**: Track and manage trusted devices

## Step-by-Step Security Setup

### Phase 1: Basic Security
1. **Verify Email**: Complete email verification if not done
2. **Update Password**: Ensure strong, unique password
3. **Enable 2FA**: Set up two-factor authentication
4. **Generate Backup Codes**: Save emergency access codes securely

### Phase 2: Enhanced Protection
1. **Configure IP Lockdown**: Add trusted IP addresses
2. **Set User Agent Lockdown**: Register trusted devices
3. **Review Security Settings**: Verify all configurations
4. **Test Access**: Confirm everything works correctly

### Phase 3: Ongoing Maintenance
1. **Regular Reviews**: Monthly security status checks
2. **Update Trusted Lists**: Add/remove IPs and devices as needed
3. **Monitor Activity**: Review login history regularly
4. **Update Backup Codes**: Regenerate codes periodically

## Security Operations Available

### Authentication Management
- **Get Auth Status**: Check current authentication configuration
- **Setup 2FA**: Initialize two-factor authentication
- **Verify 2FA**: Test 2FA code verification
- **Disable 2FA**: Remove 2FA (not recommended)
- **Regenerate Backup Codes**: Create new emergency codes

### Lockdown Management
- **Check Lockdown Status**: Review current lockdown settings
- **Request IP Lockdown**: Enable IP address restrictions
- **Confirm IP Lockdown**: Activate IP restrictions
- **Request UA Lockdown**: Enable user agent restrictions
- **Temporary Access**: Generate one-time access codes

### Security Monitoring
- **Security Dashboard**: Comprehensive security overview
- **Login History**: Review account access history
- **Failed Attempts**: Monitor unsuccessful login attempts
- **Device Management**: Manage trusted devices and browsers

## Best Practices

### Password Security
- **Unique Passwords**: Never reuse passwords across services
- **Password Managers**: Use tools like 1Password, Bitwarden, etc.
- **Regular Updates**: Change passwords if compromised
- **Complexity Requirements**: Mix letters, numbers, symbols

### 2FA Management
- **Secure Backup**: Store backup codes in safe location
- **Multiple Devices**: Consider multiple authenticator devices
- **Regular Testing**: Periodically test 2FA functionality
- **Recovery Planning**: Understand recovery procedures

### Lockdown Strategy
- **Gradual Implementation**: Start with IP lockdown, add UA later
- **Backup Access**: Always have alternative access methods
- **Travel Planning**: Prepare for access from new locations
- **Emergency Contacts**: Designate trusted contacts for emergencies

## Troubleshooting

### Common Issues
- **2FA Not Working**: Check device time synchronization
- **Locked Out**: Use backup codes or temporary access
- **IP Changes**: Update trusted IP addresses regularly
- **Device Issues**: Clear browser cache and cookies

### Recovery Procedures
1. **Lost 2FA Device**: Use backup codes for access
2. **Changed IP Address**: Request temporary access
3. **New Device**: Generate one-time access code
4. **Complete Lockout**: Contact system administrators

## Security Checklist
- [ ] Email address verified
- [ ] Strong, unique password set
- [ ] Two-factor authentication enabled
- [ ] Backup codes generated and stored securely
- [ ] IP lockdown configured (if desired)
- [ ] User agent lockdown configured (if desired)
- [ ] Security dashboard reviewed
- [ ] Login history checked

## Immediate Actions Needed
{"⚠️ URGENT: Verify your email address immediately" if not email_verified else ""}
{"⚠️ HIGH PRIORITY: Enable two-factor authentication" if not two_fa_enabled else ""}
{"✅ Good security posture - consider advanced features" if two_fa_enabled and email_verified else ""}

Remember: Security is an ongoing process, not a one-time setup. Regular reviews and updates are essential for maintaining account protection.

---
*Generated at {datetime.now(timezone.utc).isoformat()} for user {user_context.username}*
*Security Level: {"High" if two_fa_enabled and (ip_lockdown or ua_lockdown) else "Medium" if two_fa_enabled else "Basic"}*
"""

            logger.info("Provided security setup guidance prompt to user %s", user_context.user_id)
            return prompt.strip()

        except Exception as e:
            logger.error("Failed to generate security setup guidance prompt: %s", e)
            return f"Error generating security setup guidance: {str(e)}"

    @mcp_server.prompt("troubleshooting_guide")
    async def troubleshooting_guidance_prompt() -> str:
        """
        Provide troubleshooting guidance for common issues.

        Offers comprehensive troubleshooting assistance for common
        system issues, error resolution, and support procedures.

        Returns:
            Troubleshooting guidance prompt
        """
        try:
            user_context = get_mcp_user_context()

            # Create audit trail
            await create_mcp_audit_trail(
                operation="troubleshooting_guidance_prompt",
                user_context=user_context,
                resource_type="prompt",
                resource_id="troubleshooting_guide",
                metadata={"help_requested": True},
            )

            prompt = f"""
# Troubleshooting Assistant

Hello **{user_context.username}**! I'm here to help you resolve issues with the Second Brain Database system.

## Quick Diagnostic Steps

### 1. System Status Check
- **Check System Health**: Use system status resources to verify service availability
- **Network Connection**: Ensure stable internet connection
- **Browser Compatibility**: Use supported browsers (Chrome, Firefox, Safari, Edge)
- **Clear Cache**: Clear browser cache and cookies if experiencing issues

### 2. Authentication Issues
- **Login Problems**: Verify username/password, check 2FA if enabled
- **Token Expired**: Refresh authentication tokens or re-login
- **Permission Denied**: Verify account permissions for requested operations
- **Account Locked**: Check for security lockdowns or failed login attempts

## Common Issues & Solutions

### Family Management Issues

#### "Permission Denied" Errors
- **Cause**: Insufficient role permissions (need admin/owner role)
- **Solution**: Verify your role in the family, contact family owner if needed
- **Check**: Use `get_family_info` to confirm your role and permissions

#### "Family Not Found" Errors
- **Cause**: Invalid family ID or removed from family
- **Solution**: Verify family ID, check if you're still a member
- **Check**: Use `get_user_families` to see your current family memberships

#### SBD Token Request Issues
- **Cause**: Insufficient balance, frozen account, or limit exceeded
- **Solution**: Check family SBD account status and limits
- **Check**: Use `get_family_sbd_account` for account details

### Shop & Asset Issues

#### Purchase Failures
- **Cause**: Insufficient SBD balance or item unavailable
- **Solution**: Check balance, verify item availability
- **Check**: Use `get_sbd_balance` and `get_item_details`

#### Asset Not Appearing
- **Cause**: Processing delay or activation required
- **Solution**: Wait for processing, manually activate asset
- **Check**: Use `get_user_assets` to verify ownership

#### Rental Expiration
- **Cause**: Rental period ended
- **Solution**: Extend rental or purchase item for permanent access
- **Check**: Use `get_user_assets` to see rental status

### Workspace Issues

#### Cannot Add Members
- **Cause**: Member limit reached or user doesn't exist
- **Solution**: Check workspace limits, verify user exists
- **Check**: Use `get_workspace_details` for limits and settings

#### Wallet Access Denied
- **Cause**: Insufficient wallet permissions
- **Solution**: Request permissions from workspace admin
- **Check**: Use `get_workspace_wallet` to verify permissions

### Security Issues

#### 2FA Not Working
- **Cause**: Time synchronization or wrong code
- **Solution**: Check device time, regenerate codes if needed
- **Check**: Use `get_2fa_status` to verify configuration

#### Locked Out of Account
- **Cause**: IP/User Agent lockdown or failed attempts
- **Solution**: Use backup codes or request temporary access
- **Check**: Use `get_trusted_ips_status` and `get_trusted_user_agents_status`

## Error Code Reference

### HTTP Status Codes
- **400 Bad Request**: Invalid input data or malformed request
- **401 Unauthorized**: Authentication required or token expired
- **403 Forbidden**: Insufficient permissions for operation
- **404 Not Found**: Resource doesn't exist or access denied
- **429 Too Many Requests**: Rate limit exceeded, wait and retry
- **500 Internal Server Error**: System error, contact support

### MCP-Specific Errors
- **MCPAuthenticationError**: Login required or session expired
- **MCPAuthorizationError**: Insufficient permissions for operation
- **MCPValidationError**: Invalid input parameters or data
- **MCPRateLimitError**: Too many requests, implement backoff

## Diagnostic Tools Available

### System Health Checks
- **System Status**: Overall system health and component status
- **API Metrics**: Performance and availability metrics
- **Database Status**: Database connectivity and performance
- **Redis Status**: Cache system health and performance

### Account Diagnostics
- **Auth Status**: Current authentication and session status
- **Security Dashboard**: Comprehensive security overview
- **Permission Check**: Verify permissions for specific operations
- **Activity History**: Review recent account activity

### Resource Verification
- **Family Access**: Verify family membership and permissions
- **Workspace Access**: Check workspace membership and roles
- **Asset Ownership**: Confirm asset ownership and status
- **Transaction History**: Review financial transaction records

## Step-by-Step Troubleshooting

### For Authentication Issues
1. **Clear Browser Data**: Clear cache, cookies, and stored data
2. **Check Credentials**: Verify username and password accuracy
3. **Test 2FA**: Ensure authenticator app is working correctly
4. **Review Security**: Check for active lockdowns or restrictions
5. **Contact Support**: If issues persist, use system health checks

### For Permission Issues
1. **Verify Role**: Check your role in family/workspace
2. **Review Permissions**: Understand required permissions for operation
3. **Contact Admin**: Request permission changes from administrators
4. **Check Limits**: Verify account limits and quotas
5. **Audit Logs**: Review recent changes that might affect permissions

### For Financial Issues
1. **Check Balance**: Verify current SBD token balance
2. **Review Limits**: Check spending limits and restrictions
3. **Transaction History**: Review recent transactions for issues
4. **Account Status**: Verify account isn't frozen or restricted
5. **Request Assistance**: Contact family/workspace admins for help

## Prevention Strategies

### Regular Maintenance
- **Weekly**: Review account activity and security status
- **Monthly**: Check family/workspace memberships and roles
- **Quarterly**: Update passwords and security settings
- **Annually**: Comprehensive security audit and cleanup

### Best Practices
- **Keep Information Updated**: Maintain current contact information
- **Monitor Activity**: Regularly review account activity logs
- **Backup Important Data**: Keep records of important transactions
- **Stay Informed**: Keep up with system updates and changes

## When to Contact Support

### Immediate Support Needed
- **Security Breach**: Suspected unauthorized access
- **Data Loss**: Missing or corrupted important data
- **System Outage**: Widespread system unavailability
- **Financial Discrepancy**: Incorrect SBD token transactions

### Standard Support Requests
- **Feature Questions**: How to use specific features
- **Permission Issues**: Role or access problems
- **Technical Problems**: Persistent technical difficulties
- **Account Recovery**: Help with locked or inaccessible accounts

## Self-Help Resources

### Documentation
- **API Documentation**: Complete endpoint reference
- **User Guides**: Step-by-step operation guides
- **Security Guidelines**: Best practices for account protection
- **FAQ**: Frequently asked questions and answers

### Diagnostic Commands
- Use MCP tools to gather diagnostic information
- Check system resources for real-time status
- Review audit logs for recent activity
- Verify configurations and settings

## Emergency Procedures

### Account Compromise
1. **Change Password**: Immediately update account password
2. **Review Activity**: Check for unauthorized actions
3. **Enable Lockdowns**: Activate IP/UA restrictions
4. **Contact Support**: Report security incident
5. **Monitor Closely**: Watch for continued suspicious activity

### System Outage
1. **Check Status**: Verify if issue is system-wide
2. **Wait and Retry**: Allow time for automatic recovery
3. **Alternative Access**: Try different devices/networks
4. **Stay Updated**: Monitor system status for updates
5. **Document Issues**: Keep records for support requests

Remember: Most issues can be resolved through systematic troubleshooting. Start with simple solutions and escalate to support when needed.

---
*Generated at {datetime.now(timezone.utc).isoformat()} for user {user_context.username}*
*Need immediate help? Check system status first, then contact support if issues persist.*
"""

            logger.info("Provided troubleshooting guidance prompt to user %s", user_context.user_id)
            return prompt.strip()

        except Exception as e:
            logger.error("Failed to generate troubleshooting guidance prompt: %s", e)
            return f"Error generating troubleshooting guidance: {str(e)}"

    @mcp_server.prompt("onboarding_guide")
    async def onboarding_guidance_prompt() -> str:
        """
        Provide onboarding guidance for new users.

        Offers comprehensive onboarding assistance to help new users
        get started with the Second Brain Database system effectively.

        Returns:
            New user onboarding guidance prompt
        """
        try:
            user_context = get_mcp_user_context()

            # Get user account age for context
            users_collection = db_manager.get_collection("users")
            user_data = await users_collection.find_one(
                {"_id": user_context.user_id}, {"created_at": 1, "email_verified": 1, "two_factor": 1}
            )

            account_age_days = 0
            if user_data and user_data.get("created_at"):
                account_age_days = (datetime.now(timezone.utc) - user_data.get("created_at")).days

            is_new_user = account_age_days < 7
            email_verified = user_data.get("email_verified", False) if user_data else False
            two_fa_enabled = user_data.get("two_factor", {}).get("enabled", False) if user_data else False

            # Create audit trail
            await create_mcp_audit_trail(
                operation="onboarding_guidance_prompt",
                user_context=user_context,
                resource_type="prompt",
                resource_id="onboarding_guide",
                metadata={"account_age_days": account_age_days, "is_new_user": is_new_user},
            )

            prompt = f"""
# Welcome to Second Brain Database!

Hello **{user_context.username}**! Welcome to your personal knowledge management system.

## Account Status
- **Account Age**: {account_age_days} days {"(New User!)" if is_new_user else ""}
- **Email Verified**: {"✅ Complete" if email_verified else "❌ Please verify your email"}
- **Security Setup**: {"✅ 2FA Enabled" if two_fa_enabled else "⚠️ 2FA Recommended"}

## Getting Started Checklist

### Essential Setup (Complete First)
- [ ] **Verify Email Address**: Check your inbox and verify your email
- [ ] **Set Up Two-Factor Authentication**: Enable 2FA for account security
- [ ] **Complete Profile**: Add display name and basic profile information
- [ ] **Explore Interface**: Familiarize yourself with the main features

### Core Features to Explore
- [ ] **Family Management**: Create or join family accounts
- [ ] **Digital Shop**: Browse and purchase avatars, banners, themes
- [ ] **SBD Tokens**: Understand the token system and earning methods
- [ ] **Workspace Collaboration**: Create or join team workspaces

## What is Second Brain Database?

### Core Concept
Second Brain Database is your personal knowledge management system that helps you:
- **Store Information**: Organize and manage personal data
- **Collaborate**: Work with family and team members
- **Customize**: Personalize your digital presence
- **Secure**: Protect your information with advanced security

### Key Components

#### Family Management
- **Purpose**: Manage family relationships and shared resources
- **Features**: Member management, SBD token sharing, relationship tracking
- **Benefits**: Collaborative family activities and resource sharing

#### Digital Shop
- **Purpose**: Customize your digital appearance and experience
- **Features**: Avatars, banners, themes, rental and purchase options
- **Benefits**: Personalized interface and unique digital identity

#### SBD Tokens
- **Purpose**: Internal currency for purchases and transactions
- **Features**: Earning, spending, transferring, and requesting tokens
- **Benefits**: Flexible financial system for digital assets

#### Workspaces
- **Purpose**: Team collaboration and project management
- **Features**: Member management, shared wallets, project coordination
- **Benefits**: Organized team collaboration and resource sharing

## Step-by-Step Getting Started

### Week 1: Foundation Setup
1. **Day 1**: Complete email verification and basic security setup
2. **Day 2**: Set up your profile and explore the interface
3. **Day 3**: Learn about SBD tokens and check your balance
4. **Day 4**: Browse the digital shop and understand asset types
5. **Day 5**: Explore family features (create or join a family)
6. **Day 6**: Try workspace features if you work with teams
7. **Day 7**: Review security settings and enable advanced features

### Week 2: Active Usage
1. **Customize Profile**: Purchase or rent your first avatar/banner
2. **Family Activities**: Participate in family token sharing
3. **Security Enhancement**: Enable IP/User Agent lockdowns
4. **Explore Advanced Features**: Try all available tools and resources
5. **Establish Routines**: Develop regular usage patterns

## Feature Deep Dive

### Family Management
- **Creating Families**: Start with a descriptive name and clear purpose
- **Inviting Members**: Send invitations with personal messages
- **Managing Finances**: Set up SBD token sharing and approval workflows
- **Relationship Mapping**: Define family relationships for better organization

### Digital Shop Experience
- **Browsing Strategy**: Start with featured items and new arrivals
- **Purchase Decisions**: Try rentals before committing to purchases
- **Asset Management**: Learn to activate and manage your digital assets
- **Budget Planning**: Set spending limits and track expenses

### Security Best Practices
- **Strong Authentication**: Use unique passwords and enable 2FA
- **Regular Monitoring**: Check login history and security events
- **Privacy Controls**: Understand and configure privacy settings
- **Backup Planning**: Set up recovery methods and backup codes

## Common New User Questions

### "How do I earn SBD tokens?"
- **Family Activities**: Participate in family operations and approvals
- **System Rewards**: Complete profile setup and verification tasks
- **Referral Programs**: Invite friends and family to join
- **Regular Usage**: Active participation in system features

### "What should I buy first in the shop?"
- **Start Small**: Try rental items to explore preferences
- **Profile Basics**: Consider a simple avatar and banner
- **Seasonal Items**: Look for limited-time offers and featured items
- **Budget Wisely**: Don't spend all tokens immediately

### "How do families work?"
- **Shared Resources**: Families can share SBD tokens and collaborate
- **Role-Based Access**: Different roles (owner, admin, member) have different permissions
- **Approval Workflows**: Financial transactions often require approval
- **Relationship Tracking**: Map family relationships for better organization

### "Are workspaces necessary?"
- **Team Collaboration**: Essential for team-based projects
- **Resource Sharing**: Shared wallets and collaborative features
- **Optional Feature**: Not required for individual users
- **Professional Use**: Ideal for business and organizational needs

## Tips for Success

### Engagement Strategies
1. **Regular Check-ins**: Visit daily to stay engaged with features
2. **Explore Gradually**: Don't try to learn everything at once
3. **Ask Questions**: Use troubleshooting resources when stuck
4. **Join Communities**: Participate in family and workspace activities

### Avoiding Common Mistakes
1. **Don't Skip Security**: Always complete security setup first
2. **Budget Carefully**: Don't overspend SBD tokens early on
3. **Read Descriptions**: Understand features before using them
4. **Keep Records**: Track important transactions and changes

### Maximizing Value
1. **Use All Features**: Explore every aspect of the system
2. **Customize Thoughtfully**: Make personalization choices that reflect you
3. **Collaborate Actively**: Engage with family and workspace features
4. **Stay Secure**: Maintain good security practices throughout

## Next Steps After Onboarding

### Short Term (First Month)
- **Master Core Features**: Become proficient with daily-use features
- **Build Relationships**: Establish family and workspace connections
- **Develop Preferences**: Identify favorite features and usage patterns
- **Optimize Settings**: Fine-tune preferences and configurations

### Long Term (Ongoing)
- **Advanced Features**: Explore sophisticated tools and capabilities
- **Leadership Roles**: Consider admin roles in families/workspaces
- **System Expertise**: Become a power user and help others
- **Continuous Learning**: Stay updated with new features and improvements

## Support Resources

### Learning Materials
- **Interactive Guides**: Step-by-step tutorials for each feature
- **Video Tutorials**: Visual guides for complex operations
- **Documentation**: Comprehensive reference materials
- **Community Forums**: Connect with other users for tips and advice

### Getting Help
- **Built-in Help**: Use system guidance prompts and resources
- **Troubleshooting**: Comprehensive problem-solving guides
- **Support Contacts**: Direct assistance for complex issues
- **Community Support**: Peer assistance and knowledge sharing

## Welcome Message
{"🎉 Welcome to Second Brain Database! You're just getting started on an exciting journey of personal knowledge management and digital collaboration. Take your time to explore, don't hesitate to ask for help, and most importantly, have fun customizing your digital experience!" if is_new_user else f"Welcome back! You've been with us for {account_age_days} days. This guide can help you discover features you might have missed or refresh your knowledge of the system."}

Remember: Learning a new system takes time. Be patient with yourself, explore at your own pace, and don't hesitate to use the help resources available to you.

---
*Generated at {datetime.now(timezone.utc).isoformat()} for user {user_context.username}*
*Account created: {account_age_days} days ago*
"""

            logger.info("Provided onboarding guidance prompt to user %s", user_context.user_id)
            return prompt.strip()

        except Exception as e:
            logger.error("Failed to generate onboarding guidance prompt: %s", e)
            return f"Error generating onboarding guidance: {str(e)}"

    @mcp_server.prompt("api_usage_guide")
    async def api_usage_guidance_prompt() -> str:
        """
        Provide API usage guidance for developers.

        Offers comprehensive guidance for developers using the
        Second Brain Database API and MCP integration.

        Returns:
            API usage guidance prompt for developers
        """
        try:
            user_context = get_mcp_user_context()

            # Create audit trail
            await create_mcp_audit_trail(
                operation="api_usage_guidance_prompt",
                user_context=user_context,
                resource_type="prompt",
                resource_id="api_usage_guide",
                metadata={"developer_guide": True},
            )

            prompt = f"""
# API Usage Guide for Developers

Welcome **{user_context.username}**! This guide will help you integrate with the Second Brain Database API and MCP system.

## API Overview

### Base Information
- **API Version**: v1
- **Base URL**: `https://api.secondbraindatabase.com` (or your instance URL)
- **Documentation**: `/docs` (OpenAPI/Swagger)
- **OpenAPI Spec**: `/openapi.json`
- **Rate Limiting**: 100 requests/minute, 1000 requests/hour (default)

### Authentication Methods
1. **JWT Bearer Tokens**: Standard web application authentication
2. **Permanent API Tokens**: Long-lived tokens for integrations
3. **WebAuthn**: Passwordless authentication (web only)

## MCP Integration

### What is MCP?
Model Context Protocol (MCP) provides a standardized way for AI models and applications to access backend functionality through tools, resources, and prompts.

### MCP Server Details
- **Server Name**: {settings.MCP_SERVER_NAME}
- **Version**: {settings.MCP_SERVER_VERSION}
- **Tools Available**: 25+ comprehensive tools
- **Resources Available**: 10+ information resources
- **Prompts Available**: 7+ guidance prompts

### MCP Client Setup
```json
{{
  "mcpServers": {{
    "second-brain-db": {{
      "command": "your-mcp-client-command",
      "args": ["--server", "your-server-url"],
      "env": {{
        "SBD_API_TOKEN": "your-api-token"
      }}
    }}
  }}
}}
Authentication Setup
Getting API Tokens
Login to Account: Authenticate with your credentials
Navigate to Tokens: Go to profile settings > API tokens
Create Token: Generate a new permanent API token
Secure Storage: Store token securely (never commit to code)
Set Permissions: Configure appropriate token permissions
Using Authentication
Bash

# HTTP Header Authentication
curl -H "Authorization: Bearer YOUR_TOKEN" \\
     [https://api.secondbraindatabase.com/endpoint](https://api.secondbraindatabase.com/endpoint)# MCP Tool Authentication# Authentication is handled automatically by MCP security wrappers
Available API Endpoints
Family Management
GET /family - List user's families
POST /family - Create new family
GET /family/{{id}} - Get family details
PUT /family/{{id}} - Update family settings
DELETE /family/{{id}} - Delete family
POST /family/{{id}}/invite - Invite family member
GET /family/{{id}}/members - List family members
User Profile
GET /profile - Get user profile
PUT /profile - Update profile
GET /profile/preferences - Get user preferences
PUT /profile/preferences - Update preferences
POST /profile/avatar - Upload avatar
POST /profile/banner - Upload banner
Digital Shop
GET /shop/items - Browse shop items
GET /shop/items/{{id}} - Get item details
POST /shop/purchase - Purchase item
POST /shop/rent - Rent item
GET /shop/transactions - Transaction history
SBD Tokens
GET /sbd/balance - Get token balance
POST /sbd/transfer - Transfer tokens
GET /sbd/history - Transaction history
POST /sbd/request - Request tokens
MCP Tools Reference
Family Management Tools
get_family_info(family_id) - Get family information
get_family_members(family_id) - List family members
create_family(name?) - Create new family
add_family_member(family_id, email, role) - Invite member
update_family_settings(family_id, updates) - Update settings
Authentication Tools
get_auth_status() - Current authentication status
setup_2fa() - Initialize two-factor authentication
get_security_dashboard() - Security overview
request_ip_lockdown() - Enable IP restrictions
Shop Tools
list_shop_items(category?, limit?) - Browse items
purchase_item(item_id, quantity?) - Buy item
get_user_assets() - List owned/rented assets
get_sbd_balance() - Check token balance
MCP Resources Reference
Information Resources
family://{{family_id}}/info - Family information
family://{{family_id}}/members - Member list
user://{{user_id}}/profile - User profile
user://{{user_id}}/assets - User assets
shop://catalog - Shop catalog
system://status - System health
Usage Examples
Python

# Access family information resource
family_info = await mcp_client.read_resource("family://123/info")# Get user assets
assets = await mcp_client.read_resource("user://me/assets")# Check system status
status = await mcp_client.read_resource("system://status")
Error Handling
HTTP Status Codes
200 OK - Request successful
400 Bad Request - Invalid input data
401 Unauthorized - Authentication required
403 Forbidden - Insufficient permissions
404 Not Found - Resource not found
429 Too Many Requests - Rate limit exceeded
500 Internal Server Error - Server error
Error Response Format
JSON

{{
  "error": "error_type",
  "message": "Human readable message",
  "details": "Additional error details",
  "timestamp": "2024-01-01T00:00:00Z"
}}
MCP Error Handling
Python

try:
    result = await mcp_client.call_tool("get_family_info", {{"family_id": "123"}})except MCPAuthenticationError:
    # Handle authentication failure
    passexcept MCPAuthorizationError:
    # Handle permission denial
    passexcept MCPValidationError:
    # Handle invalid input
    pass
Rate Limiting
Default Limits
Standard Users: 100 requests/minute, 1000 requests/hour
Premium Users: 200 requests/minute, 2000 requests/hour
API Integrations: Custom limits based on usage
Rate Limit Headers
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
Handling Rate Limits
Python

import timeimport requestsdef api_request_with_backoff(url, headers):
    response = requests.get(url, headers=headers)

    if response.status_code == 429:
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
        wait_time = max(0, reset_time - int(time.time()))
        time.sleep(wait_time + 1)
        return api_request_with_backoff(url, headers)

    return response
Best Practices
Security
Token Security: Never expose API tokens in client-side code
HTTPS Only: Always use HTTPS for API requests
Token Rotation: Regularly rotate API tokens
Minimal Permissions: Use tokens with minimal required permissions
Secure Storage: Store tokens in secure credential management systems
Performance
Caching: Cache responses when appropriate
Batch Operations: Use batch endpoints when available
Pagination: Handle paginated responses properly
Connection Pooling: Reuse HTTP connections
Async Operations: Use async/await for better performance
Error Handling
Retry Logic: Implement exponential backoff for retries
Graceful Degradation: Handle API unavailability gracefully
Logging: Log API errors for debugging
User Feedback: Provide meaningful error messages to users
Circuit Breakers: Implement circuit breaker patterns for resilience
Example Implementations
Python SDK Example
Python

import asynciofrom second_brain_db import SecondBrainClientasync def main():
    client = SecondBrainClient(api_token="your-token")

    # Get user families
    families = await client.get_user_families()

    # Create new family
    new_family = await client.create_family(name="My Family")

    # Get family members
    members = await client.get_family_members(new_family.id)

    print(f"Created family with {len(members)} members")

asyncio.run(main())
Testing & Development
Development Environment
Base URL: http://localhost:8000 (local development)
Test Tokens: Use development API tokens for testing
Mock Data: Development environment includes sample data
Debug Mode: Enable debug logging for detailed information
Testing Strategies
Unit Tests: Test individual API calls and responses
Integration Tests: Test complete workflows and user journeys
Load Tests: Verify performance under expected load
Error Tests: Test error handling and edge cases
Security Tests: Verify authentication and authorization
Support & Resources
Documentation
API Reference: Complete endpoint documentation at /docs
MCP Specification: Model Context Protocol documentation
SDK Documentation: Language-specific SDK guides
Example Code: Sample implementations and use cases
Community & Support
Developer Forum: Community discussions and Q&A
GitHub Issues: Bug reports and feature requests
Support Email: Direct technical support contact
Office Hours: Regular developer Q&A sessions
Staying Updated
Changelog: API version changes and updates
Migration Guides: Upgrading between API versions
Newsletter: Developer-focused updates and announcements
Beta Programs: Early access to new features
Remember: Good API integration requires proper error handling, security practices, and respect for rate limits. Start with small implementations and gradually build more complex integrations.
Generated at {datetime.now(timezone.utc).isoformat()} for developer {user_context.username}
API Documentation: /docs | MCP Server: {settings.MCP_SERVER_NAME}
"""
            logger.info("Provided API usage guidance prompt to user %s", user_context.user_id)
            return prompt.strip()

        except Exception as e:
            logger.error("Failed to generate API usage guidance prompt: %s", e)
            return f"Error generating API usage guidance: {str(e)}"

else:
    logger.warning("FastMCP not available - guidance prompts will not be registered")
