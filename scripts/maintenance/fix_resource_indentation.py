#!/usr/bin/env python3
"""
Script to fix indentation issues in MCP resource files.
"""

import re
import os
from pathlib import Path

def fix_resource_indentation(file_path: Path):
    """Fix indentation issues in a resource file."""
    print(f"Fixing indentation in {file_path}...")

    with open(file_path, 'r') as f:
        content = f.read()

    # Fix function body indentation after @mcp.resource decorators
    # Pattern to match function definitions with incorrect indentation
    lines = content.split('\n')
    fixed_lines = []
    in_function = False
    function_indent = 0

    for i, line in enumerate(lines):
        # Check if this is a function definition after @mcp.resource
        if line.strip().startswith('async def ') and i > 0 and '@mcp.resource' in lines[i-1]:
            in_function = True
            function_indent = len(line) - len(line.lstrip())
            fixed_lines.append(line)
        elif in_function and line.strip() == '':
            # Empty line, keep as is
            fixed_lines.append(line)
        elif in_function and line.strip() and not line.startswith(' ' * (function_indent + 4)):
            # This line should be indented relative to the function
            if line.strip().startswith('"""') or line.strip().startswith('try:') or line.strip().startswith('except'):
                # Docstring or try/except should be indented 4 spaces from function
                fixed_lines.append(' ' * (function_indent + 4) + line.strip())
            elif line.strip().startswith('user_context') or line.strip().startswith('await') or line.strip().startswith('family_manager'):
                # Function body should be indented 8 spaces from function (4 for function + 4 for try block)
                fixed_lines.append(' ' * (function_indent + 8) + line.strip())
            else:
                # Default to function body indentation
                fixed_lines.append(' ' * (function_indent + 4) + line.strip())
        elif in_function and line.strip().startswith('async def '):
            # New function, reset
            in_function = True
            function_indent = len(line) - len(line.lstrip())
            fixed_lines.append(line)
        elif line.strip().startswith('@mcp.resource'):
            # New resource decorator, reset
            in_function = False
            fixed_lines.append(line)
        else:
            # Keep line as is
            fixed_lines.append(line)
            if not in_function and line.strip() and not line.startswith(' '):
                in_function = False

    # Write back the fixed content
    with open(file_path, 'w') as f:
        f.write('\n'.join(fixed_lines))

    print(f"Fixed indentation in {file_path}")

def main():
    """Fix indentation in all MCP resource files."""
    resources_dir = Path("src/second_brain_database/integrations/mcp/resources")

    if not resources_dir.exists():
        print(f"Resources directory not found: {resources_dir}")
        return

    # Find all Python files in the resources directory
    resource_files = list(resources_dir.glob("*.py"))

    for resource_file in resource_files:
        if resource_file.name == "__init__.py":
            continue

        try:
            fix_resource_indentation(resource_file)
        except Exception as e:
            print(f"Error fixing {resource_file}: {e}")

    print(f"Fixed indentation in {len(resource_files)} resource files")

if __name__ == "__main__":
    main()
