#!/usr/bin/env python3
"""
Script to fix Pydantic V1 Config classes to V2 ConfigDict
"""

import re

def fix_config_in_file(file_path):
    """Fix all Config classes to use ConfigDict in a file."""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace class Config: with model_config = ConfigDict(
    # and schema_extra with json_schema_extra
    config_pattern = r'(\s+)class Config:\s*\n\s+schema_extra = {'
    
    def replace_config(match):
        indent = match.group(1)
        return f'{indent}model_config = ConfigDict(\n{indent}    json_schema_extra={{'
    
    content = re.sub(config_pattern, replace_config, content)
    
    # Fix the closing of the config - need to find the matching closing brace
    # and add the closing parenthesis for ConfigDict
    lines = content.split('\n')
    new_lines = []
    in_config = False
    brace_count = 0
    
    for line in lines:
        if 'model_config = ConfigDict(' in line:
            in_config = True
            brace_count = 0
        
        if in_config:
            # Count braces to find the end of the config
            brace_count += line.count('{') - line.count('}')
            
            if brace_count == 0 and '}' in line:
                # This is the closing line of the config
                line = line.replace('}', '}\n    )')
                in_config = False
        
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed Config classes in {file_path}")

if __name__ == "__main__":
    fix_config_in_file("src/second_brain_database/models/family_models.py")