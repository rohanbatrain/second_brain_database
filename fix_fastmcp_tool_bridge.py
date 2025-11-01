#!/usr/bin/env python3
"""
Create a proper bridge between FastMCP @mcp.tool decorated functions
and the tool coordinator system.
"""

import sys
sys.path.append('.')

def extract_fastmcp_tools():
    """Extract all FastMCP tools and register them with the tool coordinator."""
    try:
        print("🔧 Extracting FastMCP tools...")
        
        # Import the MCP server to get access to registered tools
        from src.second_brain_database.integrations.mcp.mcp_instance import get_mcp_server
        from src.second_brain_database.integrations.ai_orchestration.tools.tool_coordinator import ToolCoordinator
        from src.second_brain_database.integrations.ai_orchestration.tools.tool_registry import ToolInfo
        
        # Get the MCP server
        server = get_mcp_server()
        print(f"✅ MCP server retrieved: {server.name}")
        
        # Get the tool coordinator
        coordinator = ToolCoordinator()
        print(f"✅ Tool coordinator created")
        
        # The key insight: FastMCP tools are registered in the server's tool manager
        # Let's access them directly
        fastmcp_tools = {}
        
        # Check if server has a tool manager
        if hasattr(server, 'tool_manager') and hasattr(server.tool_manager, 'tools'):
            fastmcp_tools = server.tool_manager.tools
            print(f"📊 Found {len(fastmcp_tools)} FastMCP tools in tool manager")
        elif hasattr(server, '_tools'):
            fastmcp_tools = server._tools
            print(f"📊 Found {len(fastmcp_tools)} FastMCP tools in _tools")
        else:
            # Try to access tools through other means
            for attr_name in dir(server):
                if 'tool' in attr_name.lower() and not attr_name.startswith('_'):
                    attr = getattr(server, attr_name)
                    if hasattr(attr, 'tools') or hasattr(attr, '_tools'):
                        print(f"🔍 Found potential tool container: {attr_name}")
                        
        # If we can't find tools in the server, let's manually extract them from the modules
        if not fastmcp_tools:
            print("🔍 Manually extracting tools from modules...")
            fastmcp_tools = extract_tools_from_modules()
            
        print(f"\n🛠️ FastMCP Tools Found:")
        for name, tool in fastmcp_tools.items():
            print(f"  - {name}: {type(tool)}")
            
        # Now register these tools with the tool coordinator
        registered_count = 0
        for name, tool_func in fastmcp_tools.items():
            try:
                # Determine category based on tool name
                category = determine_category(name)
                
                # Create a ToolInfo object
                tool_info = ToolInfo(
                    name=name,
                    function=tool_func,
                    category=category,
                    description=f'FastMCP tool: {name}',
                    permissions=[f'{category}:read', f'{category}:write'],
                    rate_limit_action=f'{category}_default',
                    agent_types=set(),
                    parameters={},
                    metadata={'source': 'fastmcp'}
                )
                
                # Register it with the tool registry
                coordinator.tool_registry.register_tool(tool_info)
                registered_count += 1
                print(f"  ✅ Registered {name} ({category})")
                
            except Exception as e:
                print(f"  ❌ Failed to register {name}: {e}")
                
        print(f"\n🎉 Successfully registered {registered_count} FastMCP tools!")
        
        # Check the final count
        final_tools = coordinator.tool_registry._tools
        print(f"📊 Final tool count: {len(final_tools)}")
        
        print(f"\n🛠️ All Available Tools:")
        for name, tool in final_tools.items():
            print(f"  ✅ {name} ({tool.category})")
            
        return coordinator, registered_count
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None, 0

def extract_tools_from_modules():
    """Manually extract @mcp.tool decorated functions from modules."""
    tools = {}
    
    try:
        # Import family tools module
        from src.second_brain_database.integrations.mcp.tools import family_tools
        
        # Look for functions that are likely tools
        for attr_name in dir(family_tools):
            if not attr_name.startswith('_'):
                attr = getattr(family_tools, attr_name)
                if callable(attr) and hasattr(attr, '__name__'):
                    # Check if it has tool-like characteristics
                    if (hasattr(attr, '__annotations__') and 
                        len(attr.__annotations__) > 0 and
                        not attr_name[0].isupper()):  # Not a class
                        
                        # Check if it's one of the known family tools
                        known_family_tools = [
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
                        
                        if attr_name in known_family_tools:
                            tools[attr_name] = attr
                            print(f"  📦 Found family tool: {attr_name}")
                            
    except Exception as e:
        print(f"❌ Error extracting from family_tools: {e}")
        
    try:
        # Import working test tools
        from src.second_brain_database.integrations.mcp.tools import working_test_tools
        
        for attr_name in dir(working_test_tools):
            if not attr_name.startswith('_'):
                attr = getattr(working_test_tools, attr_name)
                if callable(attr) and hasattr(attr, '__name__'):
                    if 'test' in attr_name.lower():
                        tools[attr_name] = attr
                        print(f"  📦 Found test tool: {attr_name}")
                        
    except Exception as e:
        print(f"❌ Error extracting from working_test_tools: {e}")
        
    return tools

def determine_category(tool_name):
    """Determine the category of a tool based on its name."""
    if 'family' in tool_name.lower():
        return 'family'
    elif 'shop' in tool_name.lower() or 'item' in tool_name.lower():
        return 'shop'
    elif 'auth' in tool_name.lower() or 'user' in tool_name.lower():
        return 'auth'
    elif 'admin' in tool_name.lower():
        return 'admin'
    elif 'test' in tool_name.lower():
        return 'test'
    else:
        return 'general'

def test_specific_tools():
    """Test that specific tools are now available."""
    try:
        print(f"\n🧪 Testing specific tool availability...")
        
        coordinator, _ = extract_fastmcp_tools()
        if not coordinator:
            print("❌ Failed to create coordinator")
            return
            
        # Test for specific tools that agents need
        required_tools = [
            'get_family_token_balance',
            'create_family',
            'get_family_info',
            'get_item_details'
        ]
        
        available_tools = coordinator.tool_registry._tools
        
        for tool_name in required_tools:
            if tool_name in available_tools:
                tool_info = available_tools[tool_name]
                print(f"  ✅ {tool_name} - Available ({tool_info.category})")
            else:
                print(f"  ❌ {tool_name} - Missing")
                
        # Show summary
        total_available = len(available_tools)
        required_available = sum(1 for tool in required_tools if tool in available_tools)
        
        print(f"\n📊 Summary:")
        print(f"  Total tools available: {total_available}")
        print(f"  Required tools available: {required_available}/{len(required_tools)}")
        
        if required_available == len(required_tools):
            print(f"  🎉 All required tools are now available!")
            return True
        else:
            print(f"  ⚠️ Some required tools are still missing")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 FASTMCP TOOL BRIDGE FIX")
    print("="*50)
    
    coordinator, registered_count = extract_fastmcp_tools()
    
    if coordinator and registered_count > 0:
        success = test_specific_tools()
        
        if success:
            print(f"\n✅ FastMCP tool bridge created successfully!")
            print(f"🚀 {registered_count} tools registered and ready for use")
        else:
            print(f"\n⚠️ Bridge created but some tools still missing")
    else:
        print(f"\n❌ Failed to create FastMCP tool bridge")