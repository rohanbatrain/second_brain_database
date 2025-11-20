#!/usr/bin/env python3
"""
Script to update MCP tools to use modern FastMCP 2.x patterns.

This script adds @mcp.tool decorators to all existing @authenticated_tool functions
while preserving the existing security and functionality.
"""

import re
import os
from pathlib import Path

def update_tool_file(file_path: Path):
    """Update a single tool file to use modern FastMCP 2.x patterns."""
    print(f"Updating {file_path}...")

    with open(file_path, 'r') as f:
        content = f.read()

    # Add import for mcp if not already present
    if 'from ..modern_server import mcp' not in content:
        # Find the import section and add the mcp import
        import_pattern = r'(from \.\.security import.*\n)'
        replacement = r'\1from ..modern_server import mcp\n'
        content = re.sub(import_pattern, replacement, content)

    # Pattern to match @authenticated_tool decorators
    pattern = r'(@authenticated_tool\([\s\S]*?\))\nasync def (\w+)'

    def replace_decorator(match):
        auth_decorator = match.group(1)
        func_name = match.group(2)

        # Determine appropriate tags based on function name and file
        tags = {"secure", "production"}

        if 'family' in file_path.name:
            tags.add("family")
        elif 'shop' in file_path.name:
            tags.add("shop")
        elif 'workspace' in file_path.name:
            tags.add("workspace")
        elif 'admin' in file_path.name:
            tags.add("admin")
        elif 'test' in file_path.name:
            tags.update({"testing", "development"})

        # Add specific tags based on function name
        if 'create' in func_name or 'add' in func_name:
            tags.add("write")
        elif 'get' in func_name or 'list' in func_name:
            tags.add("read")
        elif 'update' in func_name or 'modify' in func_name:
            tags.add("write")
        elif 'delete' in func_name or 'remove' in func_name:
            tags.add("write")

        tags_str = ', '.join(f'"{tag}"' for tag in sorted(tags))

        return f'@mcp.tool(tags={{{tags_str}}})\n{auth_decorator}\nasync def {func_name}'

    # Apply the replacement
    updated_content = re.sub(pattern, replace_decorator, content)

    # Write back the updated content
    with open(file_path, 'w') as f:
        f.write(updated_content)

    print(f"Updated {file_path}")

def main():
    """Update all MCP tool files."""
    tools_dir = Path("src/second_brain_database/integrations/mcp/tools")

    if not tools_dir.exists():
        print(f"Tools directory not found: {tools_dir}")
        return

    # Find all Python files in the tools directory
    tool_files = list(tools_dir.glob("*.py"))

    for tool_file in tool_files:
        if tool_file.name == "__init__.py":
            continue

        try:
            update_tool_file(tool_file)
        except Exception as e:
            print(f"Error updating {tool_file}: {e}")

    print(f"Updated {len(tool_files)} tool files")

if __name__ == "__main__":
    main()
