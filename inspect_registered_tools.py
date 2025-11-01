#!/usr/bin/env python3
"""
Comprehensive tool inspection script to identify all registered tools
and their exact names in the MCP system.
"""

import sys
sys.path.append('.')

def inspect_tool_coordinator():
    """Inspect the tool coordinator and show all registered tools."""
    try:
        from src.second_brain_database.integrations.ai_orchestration.tools.tool_coordinator import ToolCoordinator
        
        print("🔍 Creating ToolCoordinator...")
        coordinator = ToolCoordinator()
        print("✅ Tool coordinator created successfully")
        
        # Check tool registry
        if hasattr(coordinator, 'tool_registry') and hasattr(coordinator.tool_registry, 'tools'):
            tools = coordinator.tool_registry.tools
            tool_count = len(tools)
            print(f"\n📊 Tools registered: {tool_count}")
            
            if tool_count > 0:
                print("\n🎉 REGISTERED TOOLS:")
                for i, (name, info) in enumerate(tools.items(), 1):
                    print(f"  {i:2d}. ✅ {name}")
                    if hasattr(info, 'description'):
                        print(f"      📝 {info.description}")
                    elif isinstance(info, dict) and 'description' in info:
                        print(f"      📝 {info['description']}")
                    print()
            else:
                print("❌ No tools registered in tool_registry.tools")
        else:
            print("❌ Tool registry not accessible or missing 'tools' attribute")
            
        # Check if coordinator has direct tool access
        if hasattr(coordinator, 'tools'):
            direct_tools = coordinator.tools
            print(f"\n📊 Direct tools on coordinator: {len(direct_tools) if direct_tools else 0}")
            if direct_tools:
                print("\n🔧 DIRECT TOOLS:")
                for i, (name, tool) in enumerate(direct_tools.items(), 1):
                    print(f"  {i:2d}. ✅ {name}")
                    
        return coordinator
        
    except Exception as e:
        print(f"❌ Error creating ToolCoordinator: {e}")
        import traceback
        traceback.print_exc()
        return None

def inspect_mcp_server():
    """Inspect the MCP server directly for registered tools."""
    try:
        print("\n" + "="*60)
        print("🔍 Inspecting MCP Server Tools...")
        
        from src.second_brain_database.integrations.mcp.mcp_instance import get_mcp_server
        
        server = get_mcp_server()
        print("✅ MCP server retrieved successfully")
        
        # Check FastMCP server tools
        if hasattr(server, 'list_tools'):
            try:
                tools_result = server.list_tools()
                print(f"\n📊 MCP Server tools via list_tools(): {len(tools_result.tools) if hasattr(tools_result, 'tools') else 'Unknown'}")
                
                if hasattr(tools_result, 'tools'):
                    print("\n🛠️ MCP SERVER TOOLS:")
                    for i, tool in enumerate(tools_result.tools, 1):
                        name = tool.name if hasattr(tool, 'name') else str(tool)
                        desc = tool.description if hasattr(tool, 'description') else "No description"
                        print(f"  {i:2d}. ✅ {name}")
                        print(f"      📝 {desc}")
                        print()
            except Exception as e:
                print(f"❌ Error calling list_tools(): {e}")
        
        # Check server registry directly
        if hasattr(server, '_tools'):
            tools = server._tools
            print(f"\n📊 Server._tools: {len(tools) if tools else 0}")
            if tools:
                print("\n🔧 SERVER._TOOLS:")
                for i, (name, tool) in enumerate(tools.items(), 1):
                    print(f"  {i:2d}. ✅ {name}")
                    
        return server
        
    except Exception as e:
        print(f"❌ Error inspecting MCP server: {e}")
        import traceback
        traceback.print_exc()
        return None

def inspect_individual_tool_modules():
    """Inspect individual tool modules to see what they export."""
    print("\n" + "="*60)
    print("🔍 Inspecting Individual Tool Modules...")
    
    modules_to_check = [
        ('family_tools', 'src.second_brain_database.integrations.mcp.tools.family_tools'),
        ('auth_tools', 'src.second_brain_database.integrations.mcp.tools.auth_tools'),
        ('shop_tools', 'src.second_brain_database.integrations.mcp.tools.shop_tools'),
        ('ai_tools', 'src.second_brain_database.integrations.mcp.tools.ai_tools'),
    ]
    
    for module_name, module_path in modules_to_check:
        try:
            print(f"\n📦 Checking {module_name}...")
            module = __import__(module_path, fromlist=[''])
            
            # Look for tool functions (functions decorated with @tool)
            tool_functions = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and not attr_name.startswith('_'):
                    # Check if it might be a tool function
                    if hasattr(attr, '__name__') and not attr_name in ['tool', 'server']:
                        tool_functions.append(attr_name)
            
            print(f"  📊 Found {len(tool_functions)} potential tool functions:")
            for func in tool_functions:
                print(f"    ✅ {func}")
                
        except Exception as e:
            print(f"  ❌ Error importing {module_name}: {e}")

def main():
    """Main inspection function."""
    print("🔍 COMPREHENSIVE TOOL INSPECTION")
    print("="*60)
    
    # 1. Inspect Tool Coordinator
    coordinator = inspect_tool_coordinator()
    
    # 2. Inspect MCP Server
    server = inspect_mcp_server()
    
    # 3. Inspect Individual Modules
    inspect_individual_tool_modules()
    
    print("\n" + "="*60)
    print("🎯 SUMMARY")
    print("="*60)
    
    if coordinator:
        print("✅ Tool Coordinator: Working")
    else:
        print("❌ Tool Coordinator: Failed")
        
    if server:
        print("✅ MCP Server: Working")
    else:
        print("❌ MCP Server: Failed")
    
    print("\n🚀 Next steps:")
    print("1. Check the exact tool names listed above")
    print("2. Update agent workflows to use correct names")
    print("3. Test tool execution with correct names")

if __name__ == "__main__":
    main()