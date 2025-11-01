#!/usr/bin/env python3
"""
Find the actual tool names that are registered in the system.
"""

import sys
sys.path.append('.')

def find_tool_names():
    """Find all actual tool names in the system."""
    try:
        print("🔍 Finding actual tool names...")
        
        # Method 1: Check ToolCoordinator
        from src.second_brain_database.integrations.ai_orchestration.tools.tool_coordinator import ToolCoordinator
        coordinator = ToolCoordinator()
        
        print(f"\n📊 ToolCoordinator attributes:")
        for attr in dir(coordinator):
            if not attr.startswith('_'):
                print(f"  - {attr}")
        
        # Method 2: Check tool_registry directly
        if hasattr(coordinator, 'tool_registry'):
            registry = coordinator.tool_registry
            print(f"\n📊 Tool Registry attributes:")
            for attr in dir(registry):
                if not attr.startswith('_'):
                    print(f"  - {attr}")
                    
            # Check if it has tools
            if hasattr(registry, 'tools'):
                tools = registry.tools
                print(f"\n🛠️ Registry.tools type: {type(tools)}")
                print(f"🛠️ Registry.tools content: {tools}")
                
                if isinstance(tools, dict):
                    print(f"\n🎉 FOUND {len(tools)} TOOLS IN REGISTRY:")
                    for name, tool in tools.items():
                        print(f"  ✅ {name} -> {type(tool)}")
                        
            # Check other possible attributes
            for attr_name in ['_tools', 'registered_tools', 'tool_map']:
                if hasattr(registry, attr_name):
                    attr_value = getattr(registry, attr_name)
                    print(f"\n🔧 Found {attr_name}: {type(attr_value)} = {attr_value}")
        
        # Method 3: Check MCP server tools
        print(f"\n" + "="*50)
        print("🔍 Checking MCP Server Tools...")
        
        from src.second_brain_database.integrations.mcp.mcp_instance import get_mcp_server
        server = get_mcp_server()
        
        # Check server attributes
        print(f"\n📊 MCP Server attributes:")
        server_attrs = [attr for attr in dir(server) if not attr.startswith('_')]
        for attr in server_attrs[:10]:  # Show first 10
            print(f"  - {attr}")
        if len(server_attrs) > 10:
            print(f"  ... and {len(server_attrs) - 10} more")
            
        # Try to get tools via list_tools
        try:
            tools_result = server.list_tools()
            print(f"\n🛠️ list_tools() result type: {type(tools_result)}")
            
            if hasattr(tools_result, 'tools'):
                print(f"\n🎉 MCP SERVER TOOLS ({len(tools_result.tools)}):")
                for i, tool in enumerate(tools_result.tools):
                    name = getattr(tool, 'name', f'tool_{i}')
                    print(f"  ✅ {name}")
                    
        except Exception as e:
            print(f"❌ Error calling list_tools(): {e}")
            
        # Check server._tools or similar
        for attr_name in ['_tools', 'tools', 'tool_registry']:
            if hasattr(server, attr_name):
                attr_value = getattr(server, attr_name)
                print(f"\n🔧 Server.{attr_name}: {type(attr_value)}")
                if isinstance(attr_value, dict):
                    print(f"  📊 Contains {len(attr_value)} items:")
                    for key in list(attr_value.keys())[:5]:
                        print(f"    - {key}")
                    if len(attr_value) > 5:
                        print(f"    ... and {len(attr_value) - 5} more")
        
        # Method 4: Check individual tool modules for @tool decorations
        print(f"\n" + "="*50)
        print("🔍 Checking Tool Decorations...")
        
        modules_to_check = [
            'src.second_brain_database.integrations.mcp.tools.family_tools',
            'src.second_brain_database.integrations.mcp.tools.auth_tools', 
            'src.second_brain_database.integrations.mcp.tools.shop_tools',
            'src.second_brain_database.integrations.mcp.tools.ai_tools',
        ]
        
        for module_path in modules_to_check:
            try:
                module = __import__(module_path, fromlist=[''])
                module_name = module_path.split('.')[-1]
                print(f"\n📦 {module_name}:")
                
                # Look for functions with tool decorations
                for attr_name in dir(module):
                    if not attr_name.startswith('_'):
                        attr = getattr(module, attr_name)
                        if callable(attr):
                            # Check if it has tool metadata
                            if hasattr(attr, '__name__') and hasattr(attr, '__annotations__'):
                                # Check for common tool indicators
                                if (hasattr(attr, '_tool_name') or 
                                    hasattr(attr, 'tool_name') or
                                    'tool' in attr_name.lower() or
                                    attr_name in ['get_family_token_balance', 'create_family', 'browse_shop_items']):
                                    print(f"  🎯 POTENTIAL TOOL: {attr_name}")
                                    
                                    # Check for tool metadata
                                    for meta_attr in ['_tool_name', 'tool_name', '__tool_name__']:
                                        if hasattr(attr, meta_attr):
                                            print(f"    📝 {meta_attr}: {getattr(attr, meta_attr)}")
                                            
            except Exception as e:
                print(f"  ❌ Error checking {module_path}: {e}")
        
        return coordinator, server
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None, None

if __name__ == "__main__":
    coordinator, server = find_tool_names()
    
    print(f"\n" + "="*50)
    print("🎯 CONCLUSION")
    print("="*50)
    
    if coordinator and server:
        print("✅ Both systems are working")
        print("🔍 The issue is likely in tool name mapping")
        print("📝 Check the output above for actual tool names")
    else:
        print("❌ System initialization failed")