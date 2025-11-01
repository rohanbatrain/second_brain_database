#!/usr/bin/env python3
"""
Fix Tool Coordinator for FastMCP 2.x Integration

This script updates the tool coordinator to work with FastMCP 2.x native tools
instead of looking for custom _mcp_tool_name attributes.
"""

def update_tool_coordinator():
    """Update the tool coordinator to work with FastMCP 2.x tools."""
    
    file_path = "src/second_brain_database/integrations/ai_orchestration/tools/tool_coordinator.py"
    
    print(f"Updating {file_path} for FastMCP 2.x compatibility...")
    
    # Read the current file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace the _register_module_tools method to work with FastMCP 2.x
    old_method = '''    def _register_module_tools(self, module: Any, category: str) -> None:
        """Register all tools from a module with the tool registry."""
        try:
            # Get all functions that are decorated as MCP tools
            for name in dir(module):
                try:
                    obj = getattr(module, name)
                    # Check for authenticated_tool decorated functions
                    if callable(obj) and hasattr(obj, '_mcp_tool_name'):
                        # This is an MCP tool function decorated with @authenticated_tool
                        tool_name = getattr(obj, '_mcp_tool_name', name)
                        description = getattr(obj, '_mcp_tool_description', '')
                        permissions = getattr(obj, '_mcp_tool_permissions', [])
                        rate_limit_action = getattr(obj, '_mcp_rate_limit_action', 'default')
                        
                        self.tool_registry.register_tool(
                            name=tool_name,
                            function=obj,
                            category=category,
                            description=description,
                            permissions=permissions,
                            rate_limit_action=rate_limit_action
                        )
                        logger.debug("Registered MCP tool: %s", tool_name)
                except Exception as attr_error:
                    # Skip objects that can't be accessed (like imports that failed)
                    logger.debug("Skipped object %s in %s module: %s", name, category, attr_error)
                    continue
                    
            logger.debug("Registered tools from %s module", category)
            
        except Exception as e:
            logger.warning("Failed to register tools from %s module: %s", category, e)'''

    new_method = '''    def _register_module_tools(self, module: Any, category: str) -> None:
        """Register all tools from a module with the tool registry (FastMCP 2.x compatible)."""
        try:
            tools_registered = 0
            
            # Get all functions that are decorated as MCP tools
            for name in dir(module):
                try:
                    obj = getattr(module, name)
                    
                    # Check for FastMCP 2.x tools (async functions that start with common prefixes)
                    if callable(obj) and asyncio.iscoroutinefunction(obj):
                        # Check if it's likely a tool function based on naming patterns
                        if any(name.startswith(prefix) for prefix in [
                            'get_', 'create_', 'update_', 'delete_', 'list_', 'send_', 'accept_', 
                            'decline_', 'add_', 'remove_', 'promote_', 'demote_', 'freeze_', 
                            'unfreeze_', 'mark_', 'review_', 'validate_', 'test_'
                        ]):
                            # Register as a tool with default settings
                            tool_name = name
                            description = obj.__doc__ or f"Tool: {name}"
                            
                            # Extract first line of docstring as description
                            if obj.__doc__:
                                description = obj.__doc__.split('\\n')[0].strip()
                            
                            # Determine permissions based on function name and category
                            permissions = self._determine_permissions(name, category)
                            
                            self.tool_registry.register_tool(
                                name=tool_name,
                                function=obj,
                                category=category,
                                description=description,
                                permissions=permissions,
                                rate_limit_action=f"{category}_default"
                            )
                            tools_registered += 1
                            logger.debug("Registered FastMCP tool: %s (category: %s)", tool_name, category)
                    
                    # Also check for legacy authenticated_tool decorated functions
                    elif callable(obj) and hasattr(obj, '_mcp_tool_name'):
                        # This is a legacy MCP tool function decorated with @authenticated_tool
                        tool_name = getattr(obj, '_mcp_tool_name', name)
                        description = getattr(obj, '_mcp_tool_description', '')
                        permissions = getattr(obj, '_mcp_tool_permissions', [])
                        rate_limit_action = getattr(obj, '_mcp_rate_limit_action', 'default')
                        
                        self.tool_registry.register_tool(
                            name=tool_name,
                            function=obj,
                            category=category,
                            description=description,
                            permissions=permissions,
                            rate_limit_action=rate_limit_action
                        )
                        tools_registered += 1
                        logger.debug("Registered legacy MCP tool: %s", tool_name)
                        
                except Exception as attr_error:
                    # Skip objects that can't be accessed (like imports that failed)
                    logger.debug("Skipped object %s in %s module: %s", name, category, attr_error)
                    continue
                    
            logger.info("Registered %d tools from %s module", tools_registered, category)
            
        except Exception as e:
            logger.warning("Failed to register tools from %s module: %s", category, e)
    
    def _determine_permissions(self, function_name: str, category: str) -> List[str]:
        """Determine permissions for a function based on its name and category."""
        permissions = []
        
        # Base permission for the category
        permissions.append(f"{category}:read")
        
        # Add write permissions for modifying operations
        if any(function_name.startswith(prefix) for prefix in [
            'create_', 'update_', 'delete_', 'add_', 'remove_', 'promote_', 
            'demote_', 'freeze_', 'unfreeze_', 'send_', 'accept_', 'decline_'
        ]):
            permissions.append(f"{category}:write")
        
        # Add admin permissions for administrative operations
        if any(function_name.startswith(prefix) for prefix in [
            'promote_', 'demote_', 'freeze_', 'unfreeze_', 'delete_'
        ]) or 'admin' in function_name:
            permissions.append(f"{category}:admin")
        
        return permissions'''
    
    # Replace the method
    if old_method in content:
        content = content.replace(old_method, new_method)
        
        # Add the import for asyncio at the top
        if "import asyncio" not in content:
            content = content.replace(
                "from typing import Dict, Any, List, Optional, Set",
                "from typing import Dict, Any, List, Optional, Set\nimport asyncio"
            )
        
        # Write back
        with open(file_path, 'w') as f:
            f.write(content)
        
        print("✅ Updated tool coordinator for FastMCP 2.x compatibility")
        return True
    else:
        print("❌ Could not find the method to replace")
        return False

def test_updated_coordinator():
    """Test the updated tool coordinator."""
    
    print("\n=== Testing Updated Tool Coordinator ===")
    
    import subprocess
    import sys
    
    result = subprocess.run([
        sys.executable, '-c', '''
import sys
sys.path.append(".")

try:
    # Test the tool coordinator
    from src.second_brain_database.integrations.ai_orchestration.tools.tool_coordinator import ToolCoordinator
    from src.second_brain_database.integrations.ai_orchestration.tools.tool_registry import ToolRegistry
    
    print("✅ Tool coordinator imported successfully")
    
    # Create a tool coordinator instance
    tool_registry = ToolRegistry()
    coordinator = ToolCoordinator(tool_registry)
    
    print("✅ Tool coordinator created successfully")
    
    # Check how many tools are registered
    tool_count = len(tool_registry.tools) if hasattr(tool_registry, 'tools') else 0
    print(f"Tools registered: {tool_count}")
    
    if tool_count > 0:
        print("🎉 TOOLS ARE NOW REGISTERED!")
        # List some tools
        if hasattr(tool_registry, 'tools'):
            for i, (name, tool_info) in enumerate(tool_registry.tools.items()):
                if i < 5:  # Show first 5 tools
                    print(f"  ✅ {name}: {tool_info.get('description', 'No description')}")
    else:
        print("❌ No tools registered yet")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
'''
    ], capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    return "🎉 TOOLS ARE NOW REGISTERED!" in result.stdout

def main():
    """Main function to fix the tool coordinator."""
    
    print("🔧 Fixing Tool Coordinator for FastMCP 2.x...")
    print("=" * 60)
    
    # Step 1: Update tool coordinator
    print("\n1. Updating tool coordinator...")
    coordinator_updated = update_tool_coordinator()
    
    # Step 2: Test updated coordinator
    print("\n2. Testing updated coordinator...")
    coordinator_test = test_updated_coordinator()
    
    # Summary
    print("\n" + "=" * 60)
    print("🔧 Tool Coordinator Fix Summary:")
    print(f"  Coordinator updated: {'✅' if coordinator_updated else '❌'}")
    print(f"  Coordinator test: {'✅' if coordinator_test else '❌'}")
    
    if coordinator_test:
        print("\n🎉 SUCCESS! Tool coordinator now works with FastMCP 2.x!")
        print("\nNext steps:")
        print("1. Run: python test_real_user_rohan.py")
        print("2. The system should now show tools being found and executed")
        print("3. Family and commerce operations should work")
    else:
        print("\n❌ Tool coordinator still needs work.")
        print("\nThe issue might be in the tool registry or execution system.")

if __name__ == "__main__":
    main()