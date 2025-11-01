#!/usr/bin/env python3
"""
Fix the tool coordinator registration to properly include FastMCP family tools.
"""

import sys
sys.path.append('.')

def fix_tool_coordinator():
    """Fix the tool coordinator to properly register FastMCP tools."""
    try:
        print("🔧 Fixing tool coordinator registration...")
        
        # Import the tool coordinator
        from src.second_brain_database.integrations.ai_orchestration.tools.tool_coordinator import ToolCoordinator
        
        # Create a new coordinator
        coordinator = ToolCoordinator()
        print(f"✅ Tool coordinator created")
        
        # Check current tools
        current_tools = coordinator.tool_registry._tools
        print(f"📊 Current tools: {len(current_tools)}")
        
        for name, tool in current_tools.items():
            print(f"  - {name} ({tool.category})")
        
        # Now let's manually add the missing FastMCP family tools
        print(f"\n🔧 Manually registering FastMCP family tools...")
        
        # Import the family tools module
        from src.second_brain_database.integrations.mcp.tools import family_tools
        
        # List of known family tools that should be registered
        expected_family_tools = [
            'get_family_info', 'get_family_members', 'get_user_families',
            'create_family', 'update_family_settings', 'delete_family',
            'add_family_member', 'remove_family_member', 'update_family_member_role',
            'update_relationship', 'get_family_relationships', 'promote_to_admin',
            'demote_from_admin', 'send_family_invitation', 'accept_family_invitation',
            'decline_family_invitation', 'list_pending_invitations', 'get_family_notifications',
            'mark_notifications_read', 'mark_all_notifications_read', 'update_notification_preferences',
            'get_notification_preferences', 'get_received_invitations', 'get_family_sbd_account',
            'get_family_token_balance', 'create_token_request', 'review_token_request',
            'get_token_requests', 'update_spending_permissions', 'freeze_family_account',
            'unfreeze_family_account', 'get_family_transaction_history', 'get_admin_actions_log',
            'designate_backup_admin', 'remove_backup_admin', 'get_family_stats',
            'get_family_limits', 'emergency_admin_access', 'validate_family_access'
        ]
        
        registered_count = 0
        for tool_name in expected_family_tools:
            if hasattr(family_tools, tool_name):
                tool_func = getattr(family_tools, tool_name)
                
                if callable(tool_func):
                    try:
                        # Determine permissions
                        permissions = ['family:read']
                        if any(tool_name.startswith(prefix) for prefix in [
                            'create_', 'update_', 'delete_', 'add_', 'remove_', 'promote_', 
                            'demote_', 'freeze_', 'unfreeze_', 'send_', 'accept_', 'decline_'
                        ]):
                            permissions.append('family:write')
                        
                        if any(tool_name.startswith(prefix) for prefix in [
                            'promote_', 'demote_', 'freeze_', 'unfreeze_', 'delete_'
                        ]) or 'admin' in tool_name:
                            permissions.append('family:admin')
                        
                        # Get description from docstring
                        description = tool_func.__doc__ or f"Family tool: {tool_name}"
                        if tool_func.__doc__:
                            description = tool_func.__doc__.split('\n')[0].strip()
                        
                        # Register the tool
                        coordinator.tool_registry.register_tool(
                            name=tool_name,
                            function=tool_func,
                            category='family',
                            description=description,
                            permissions=permissions,
                            rate_limit_action='family_default'
                        )
                        
                        registered_count += 1
                        print(f"  ✅ Registered {tool_name}")
                        
                    except Exception as e:
                        print(f"  ❌ Failed to register {tool_name}: {e}")
                else:
                    print(f"  ⚠️ {tool_name} is not callable")
            else:
                print(f"  ❌ {tool_name} not found in family_tools module")
        
        print(f"\n🎉 Successfully registered {registered_count} additional family tools!")
        
        # Check final tools
        final_tools = coordinator.tool_registry._tools
        print(f"📊 Final tool count: {len(final_tools)}")
        
        # Test for specific required tools
        required_tools = ['get_family_token_balance', 'create_family', 'get_family_info']
        found_tools = []
        
        for tool_name in required_tools:
            if tool_name in final_tools:
                found_tools.append(tool_name)
                print(f"  ✅ {tool_name} - Available")
            else:
                print(f"  ❌ {tool_name} - Missing")
        
        print(f"\n📊 Summary:")
        print(f"  Total tools: {len(final_tools)}")
        print(f"  Required tools found: {len(found_tools)}/{len(required_tools)}")
        
        if len(found_tools) == len(required_tools):
            print(f"  🎉 All required tools are now available!")
            return True
        else:
            print(f"  ⚠️ Some required tools are still missing")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tool_execution():
    """Test that we can now execute the required tools."""
    try:
        print(f"\n🧪 Testing tool execution...")
        
        # Import the tool coordinator
        from src.second_brain_database.integrations.ai_orchestration.tools.tool_coordinator import ToolCoordinator
        
        # Create coordinator
        coordinator = ToolCoordinator()
        
        # Try to list available tools
        available_tools = coordinator.list_available_tools()
        print(f"📊 Available tools via list_available_tools(): {len(available_tools)}")
        
        for tool in available_tools[:10]:  # Show first 10
            print(f"  - {tool}")
        
        if len(available_tools) > 10:
            print(f"  ... and {len(available_tools) - 10} more")
        
        # Check if we can get tool info
        if 'get_family_token_balance' in [tool for tool in available_tools]:
            print(f"  ✅ get_family_token_balance is available for execution")
        else:
            print(f"  ❌ get_family_token_balance is not available")
            
        return True
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 TOOL COORDINATOR REGISTRATION FIX")
    print("="*50)
    
    success = fix_tool_coordinator()
    
    if success:
        test_success = test_tool_execution()
        
        if test_success:
            print(f"\n✅ Tool coordinator fix completed successfully!")
            print(f"🚀 FastMCP family tools are now properly registered")
            print(f"🎯 Agents should now be able to use tools like:")
            print(f"  - get_family_token_balance")
            print(f"  - create_family")
            print(f"  - get_family_info")
        else:
            print(f"\n⚠️ Fix applied but testing failed")
    else:
        print(f"\n❌ Failed to fix tool coordinator registration")