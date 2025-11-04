#!/usr/bin/env python3
"""
Script to fix all indentation issues in MCP resource files by rewriting them properly.
"""

import ast
import os
from pathlib import Path

def fix_file_indentation(file_path: Path):
    """Fix indentation issues by parsing and rewriting the file."""
    print(f"Fixing {file_path}...")

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Parse the AST to validate syntax
        try:
            ast.parse(content)
            print(f"  ✅ {file_path} syntax is already valid")
            return
        except SyntaxError as e:
            print(f"  ❌ Syntax error in {file_path}: {e}")

        # Fix common indentation issues
        lines = content.split('\n')
        fixed_lines = []

        for i, line in enumerate(lines):
            # Skip empty lines
            if not line.strip():
                fixed_lines.append('')
                continue

            # Fix decorator indentation
            if line.strip().startswith('@mcp.'):
                fixed_lines.append(line.strip())
                continue

            # Fix function definition indentation
            if line.strip().startswith('async def '):
                fixed_lines.append(line.strip())
                continue

            # Fix docstring and function body indentation
            if (line.strip().startswith('"""') or
                line.strip().startswith('try:') or
                line.strip().startswith('except') or
                line.strip().startswith('return') or
                line.strip().startswith('user_context') or
                line.strip().startswith('await') or
                line.strip().startswith('family_manager') or
                line.strip().startswith('logger.')):

                # Check if we're inside a function
                in_function = False
                for j in range(i-1, -1, -1):
                    if lines[j].strip().startswith('async def '):
                        in_function = True
                        break
                    elif lines[j].strip().startswith('@') or lines[j].strip().startswith('class '):
                        break

                if in_function:
                    fixed_lines.append('    ' + line.strip())
                else:
                    fixed_lines.append(line.strip())
                continue

            # Default: keep original indentation if it looks reasonable
            if line.startswith('    ') or line.startswith('\t'):
                fixed_lines.append(line)
            else:
                fixed_lines.append(line)

        # Write the fixed content
        fixed_content = '\n'.join(fixed_lines)

        # Validate the fixed syntax
        try:
            ast.parse(fixed_content)
            with open(file_path, 'w') as f:
                f.write(fixed_content)
            print(f"  ✅ Fixed {file_path}")
        except SyntaxError as e:
            print(f"  ❌ Still has syntax error after fix: {e}")

    except Exception as e:
        print(f"  ❌ Error processing {file_path}: {e}")

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

        fix_file_indentation(resource_file)

    print(f"Processed {len(resource_files)} resource files")

if __name__ == "__main__":
    main()
