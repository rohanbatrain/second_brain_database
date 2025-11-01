#!/usr/bin/env python3
"""
Debug script to check MCP tool registration
"""

import sys
sys.path.append('.')

def check_tool_module(module_name):
    print(f"\n=== Checking {module_name} ===")
    try:
        if module_name == "family_tools":
            from src.second_brain_database.integrations.mcp.tools import family_tools as module
        elif module_name == "shop_tools":
            from src.second_brain_database.integrations.mcp.tools import shop_tools as module
        elif module_name == "auth_tools":
            from src.second_brain_database.integrations.mcp.tools import auth_tools as module
        else:
            print(f"Unknown module: {module_name}")
            return
            
        print(f"✅ {module_name} imported successfully")
        
        # Check all attributes
        all_attrs = dir(module)
        functions = []
        decorated_functions = []
        
        for name in all_attrs:
            if not name.startswith('_'):
                try:
                    obj = getattr(module, name)
                    if callable(obj):
                        functions.append(name)
                        if hasattr(obj, '_mcp_tool_name'):
                            decorated_functions.append((name, obj._mcp_tool_name))
                except:
                    pass
        
        print(f"Total functions: {len(functions)}")
        print(f"Decorated functions: {len(decorated_functions)}")
        
        if decorated_functions:
            print("Decorated functions:")
            for func_name, tool_name in decorated_functions[:5]:
                print(f"  ✅ {func_name} -> {tool_name}")
            if len(decorated_functions) > 5:
                print(f"  ... and {len(decorated_functions) - 5} more")
        else:
            print("❌ No decorated functions found!")
            print("Sample functions:", functions[:10])
            
            # Check one function in detail
            if functions:
                sample_func = getattr(module, functions[0])
                print(f"\nSample function '{functions[0]}' attributes:")
                for attr in dir(sample_func):
                    if attr.startswith('_mcp'):
                        print(f"  {attr}: {getattr(sample_func, attr, 'N/A')}")
                        
    except Exception as e:
        print(f"❌ Error importing {module_name}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_tool_module("family_tools")
    check_tool_module("shop_tools") 
    check_tool_module("auth_tools")