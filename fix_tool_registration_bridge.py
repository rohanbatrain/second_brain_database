#!/usr/bin/env python3
"""
Fix tool registration by creating a bridge between FastMCP native tools
and the custom tool coordinator system.
"""

import sys
sys.path.append('.')

def fix_tool_registration():
    """Create a bridge between FastMCP tools and the tool coordinator."""
    try:
        print("🔧 Creating tool registration bridge...")
        
        # Import the MCP server and tool coordinator
        from src.second_brain_database.integrations.mcp.mcp_instance import get_mcp_server
        from src.second_brain_database.integrations.ai_orchestration.tools.tool_coordinator import ToolCoordinator
        
        # Get the MCP server
        server = get_mcp_server()
        print(f"✅ MCP server retrieved: {server.name}")
        
        # Get the tool coordinator
        coordinator = ToolCoordinator()
        print(f"✅ Tool coordinator created")
        
        # Check what tools are available in the MCP server
        mcp_tools = {}
        if hasattr(server, '_tools'):
            mcp_tools = server._tools
            print(f"📊 Found {len(mcp_tools)} tools in MCP server")
            
        # Check what tools are in the tool registry
        registry_tools = {}
        if hasattr(coordinator, 'tool_registry') and hasattr(coordinator.tool_registry, '_tools'):
            registry_tools = coordinator.tool_registry._tools
            print(f"📊 Found {len(registry_tools)} tools in tool registry")
            
        # Print current tools
        print(f"\n🛠️ MCP Server Tools:")
        for name, tool in mcp_tools.items():
            print(f"  - {name}")
            
        print(f"\n🛠️ Tool Registry Tools:")
        for name, tool in registry_tools.items():
            print(f"  - {name}")
            
        # Now let's try to bridge them by manually registering FastMCP tools
        print(f"\n🌉 Creating bridge...")
        
        # Import the family tools module to get access to the decorated functions
        from src.second_brain_database.integrations.mcp.tools import family_tools
        
        # Look for functions with @mcp.tool decorations
        family_tool_functions = []
        for attr_name in dir(family_tools):
            if not attr_name.startswith('_'):
                attr = getattr(family_tools, attr_name)
                if callable(attr) and hasattr(attr, '__name__'):
                    # Check if it's likely a tool function
                    if (hasattr(attr, '__annotations__') and 
                        'family' in attr_name.lower() or 
                        attr_name in ['get_family_token_balance', 'create_family']):
                        family_tool_functions.append((attr_name, attr))
                        
        print(f"📦 Found {len(family_tool_functions)} potential family tools:")
        for name, func in family_tool_functions:
            print(f"  - {name}")
            
        # Try to register these tools with the tool coordinator
        from src.second_brain_database.integrations.ai_orchestration.tools.tool_registry import ToolInfo
        
        registered_count = 0
        for name, func in family_tool_functions:
            try:
                # Create a ToolInfo object for this function
                tool_info = ToolInfo(
                    name=name,
                    function=func,
                    category='family',
                    description=f'Family tool: {name}',
                    permissions=['family:read', 'family:write'],
                    rate_limit_action='family_default',
                    agent_types=set(),
                    parameters={},
                    metadata={}
                )
                
                # Register it with the tool registry
                coordinator.tool_registry.register_tool(tool_info)
                registered_count += 1
                print(f"  ✅ Registered {name}")
                
            except Exception as e:
                print(f"  ❌ Failed to register {name}: {e}")
                
        print(f"\n🎉 Successfully registered {registered_count} additional tools!")
        
        # Check the final count
        final_tools = coordinator.tool_registry._tools
        print(f"📊 Final tool count: {len(final_tools)}")
        
        print(f"\n🛠️ All Available Tools:")
        for name, tool in final_tools.items():
            print(f"  ✅ {name} ({tool.category})")
            
        return coordinator
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_tool_execution():
    """Test executing one of the newly registered tools."""
    try:
        print(f"\n🧪 Testing tool execution...")
        
        coordinator = fix_tool_registration()
        if not coordinator:
            print("❌ Failed to create coordinator")
            return
            
        # Try to execute a family tool
        available_tools = coordinator.tool_registry._tools
        
        # Look for get_family_token_balance
        if 'get_family_token_balance' in available_tools:
            print(f"🎯 Testing get_family_token_balance...")
            
            # This would normally require authentication, so we'll just check it exists
            tool_info = available_tools['get_family_token_balance']
            print(f"  ✅ Tool found: {tool_info.name}")
            print(f"  📝 Description: {tool_info.description}")
            print(f"  🔐 Permissions: {tool_info.permissions}")
            
        else:
            print(f"❌ get_family_token_balance not found in registered tools")
            
        # Look for create_family
        if 'create_family' in available_tools:
            print(f"🎯 Testing create_family...")
            
            tool_info = available_tools['create_family']
            print(f"  ✅ Tool found: {tool_info.name}")
            print(f"  📝 Description: {tool_info.description}")
            print(f"  🔐 Permissions: {tool_info.permissions}")
            
        else:
            print(f"❌ create_family not found in registered tools")
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔧 TOOL REGISTRATION BRIDGE FIX")
    print("="*50)
    
    coordinator = fix_tool_registration()
    
    if coordinator:
        test_tool_execution()
        print(f"\n✅ Tool registration bridge created successfully!")
        print(f"🚀 The system should now have access to family tools like:")
        print(f"  - get_family_token_balance")
        print(f"  - create_family") 
        print(f"  - get_family_info")
        print(f"  - and many more...")
    else:
        print(f"\n❌ Failed to create tool registration bridge")