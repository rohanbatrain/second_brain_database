#!/usr/bin/env python3
"""
Script to update MCP resources and prompts to use modern FastMCP 2.x patterns.
"""

import re
import os
from pathlib import Path

def update_resource_file(file_path: Path):
    """Update a single resource file to use modern FastMCP 2.x patterns."""
    print(f"Updating {file_path}...")

    with open(file_path, 'r') as f:
        content = f.read()

    # Replace old mcp_instance import with modern_server import
    content = re.sub(
        r'from \.\.mcp_instance import get_mcp_instance',
        'from ..modern_server import mcp',
        content
    )

    # Remove the mcp instance retrieval code
    content = re.sub(
        r'# Get the shared MCP instance\nmcp = get_mcp_instance\(\)\n\nif mcp is not None:\n    \n    ',
        '',
        content
    )

    # Update @mcp.resource decorators to include tags
    def add_tags_to_resource(match):
        decorator = match.group(1)
        uri = match.group(2)

        # Determine appropriate tags
        tags = {"secure", "production"}

        if 'family' in file_path.name:
            tags.add("family")
        elif 'shop' in file_path.name:
            tags.add("shop")
        elif 'workspace' in file_path.name:
            tags.add("workspace")
        elif 'system' in file_path.name:
            tags.add("system")
        elif 'user' in file_path.name:
            tags.add("user")
        elif 'test' in file_path.name:
            tags.update({"testing", "development"})

        tags.add("resources")

        tags_str = ', '.join(f'"{tag}"' for tag in sorted(tags))

        return f'@mcp.resource("{uri}", tags={{{tags_str}}})'

    # Pattern to match @mcp.resource decorators
    resource_pattern = r'(@mcp\.resource\("([^"]+)"\))'
    content = re.sub(resource_pattern, add_tags_to_resource, content)

    # Write back the updated content
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Updated {file_path}")

def update_prompt_file(file_path: Path):
    """Update a single prompt file to use modern FastMCP 2.x patterns."""
    print(f"Updating {file_path}...")

    with open(file_path, 'r') as f:
        content = f.read()

    # Replace old mcp_instance import with modern_server import
    content = re.sub(
        r'from \.\.mcp_instance import get_mcp_instance',
        'from ..modern_server import mcp',
        content
    )

    # Remove the mcp instance retrieval code
    content = re.sub(
        r'# Get the shared MCP instance\nmcp = get_mcp_instance\(\)\n\nif mcp is not None:\n    \n    ',
        '',
        content
    )

    # Update @mcp.prompt decorators to include tags
    def add_tags_to_prompt(match):
        decorator = match.group(1)
        name = match.group(2)

        # Determine appropriate tags
        tags = {"secure", "production", "prompts"}

        if 'guidance' in file_path.name:
            tags.add("guidance")
        elif 'family' in file_path.name:
            tags.add("family")
        elif 'shop' in file_path.name:
            tags.add("shop")
        elif 'workspace' in file_path.name:
            tags.add("workspace")
        elif 'test' in file_path.name:
            tags.update({"testing", "development"})

        tags_str = ', '.join(f'"{tag}"' for tag in sorted(tags))

        return f'@mcp.prompt("{name}", tags={{{tags_str}}})'

    # Pattern to match @mcp.prompt decorators
    prompt_pattern = r'(@mcp\.prompt\("([^"]+)"\))'
    content = re.sub(prompt_pattern, add_tags_to_prompt, content)

    # Write back the updated content
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Updated {file_path}")

def main():
    """Update all MCP resource and prompt files."""
    base_dir = Path("src/second_brain_database/integrations/mcp")

    # Update resources
    resources_dir = base_dir / "resources"
    if resources_dir.exists():
        resource_files = list(resources_dir.glob("*.py"))
        for resource_file in resource_files:
            if resource_file.name == "__init__.py":
                continue
            try:
                update_resource_file(resource_file)
            except Exception as e:
                print(f"Error updating {resource_file}: {e}")
        print(f"Updated {len(resource_files)} resource files")

    # Update prompts
    prompts_dir = base_dir / "prompts"
    if prompts_dir.exists():
        prompt_files = list(prompts_dir.glob("*.py"))
        for prompt_file in prompt_files:
            if prompt_file.name == "__init__.py":
                continue
            try:
                update_prompt_file(prompt_file)
            except Exception as e:
                print(f"Error updating {prompt_file}: {e}")
        print(f"Updated {len(prompt_files)} prompt files")

if __name__ == "__main__":
    main()
