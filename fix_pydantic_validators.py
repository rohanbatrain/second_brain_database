#!/usr/bin/env python3
"""
Script to fix Pydantic V1 validators to V2 field_validators
"""

import re

def fix_validators_in_file(file_path):
    """Fix all @validator decorators to @field_validator in a file."""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace @validator with @field_validator and add @classmethod
    # Pattern: @validator('field_name') or @validator('field1', 'field2')
    validator_pattern = r'@validator\((.*?)\)\s*\n\s*def\s+(\w+)\s*\(cls,'
    
    def replace_validator(match):
        fields = match.group(1)
        method_name = match.group(2)
        return f'@field_validator({fields})\n    @classmethod\n    def {method_name}(cls,'
    
    content = re.sub(validator_pattern, replace_validator, content)
    
    # Also need to handle cases where values parameter is used
    # Replace 'values' parameter with 'info' and update usage
    content = content.replace('def validate_reason(cls, v, values):', 'def validate_reason(cls, v, info):')
    content = content.replace("values.get('action')", "info.data.get('action')")
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed validators in {file_path}")

if __name__ == "__main__":
    fix_validators_in_file("src/second_brain_database/models/family_models.py")