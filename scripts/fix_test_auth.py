#!/usr/bin/env python3
"""
Script to fix authentication in IPAM enhancement tests.
Replaces unittest.mock.patch with FastAPI dependency overrides.
"""

import re

def fix_test_file(filepath):
    """Fix authentication mocking in test file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern to match test methods with patch context manager
    # Matches: async def test_xxx(self, test_client, auth_headers, ...):
    #          with patch(...) as mock_auth:
    #              mock_auth.return_value = ...
    #              response = test_client.post(...)
    
    # Step 1: Replace test_client parameter with authenticated_client
    content = re.sub(
        r'async def (test_\w+)\(self, test_client, auth_headers,',
        r'async def \1(self, authenticated_client,',
        content
    )
    
    # Step 2: Replace test_client, auth_headers) with authenticated_client)
    content = re.sub(
        r'async def (test_\w+)\(self, test_client, auth_headers\)',
        r'async def \1(self, authenticated_client)',
        content
    )
    
    # Step 3: Remove patch context managers and their mock_auth.return_value lines
    # This is more complex - we need to handle indentation
    
    # Pattern: with patch(...) as mock_auth:\n            mock_auth.return_value = {...}\n            \n
    pattern = r'        with patch\("second_brain_database\.routes\.ipam\.dependencies\.get_current_user_for_ipam"\) as mock_auth:\n            mock_auth\.return_value = \{[^}]+\}\n            \n'
    content = re.sub(pattern, '', content)
    
    # Step 4: Fix indentation - move response = lines back 12 spaces (3 levels)
    # Find lines that start with "            response = test_client" or "            response = authenticated_client"
    lines = content.split('\n')
    fixed_lines = []
    in_test_method = False
    
    for i, line in enumerate(lines):
        # Check if we're in a test method
        if 'async def test_' in line:
            in_test_method = True
        elif line and not line[0].isspace() and in_test_method:
            in_test_method = False
        
        # If line starts with 12 spaces and contains response = or assert, reduce to 8 spaces
        if in_test_method and line.startswith('            ') and not line.startswith('             '):
            # This is a line with 12 spaces (3 levels of indentation)
            # Reduce to 8 spaces (2 levels)
            fixed_lines.append('        ' + line[12:])
        else:
            fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    # Step 5: Replace test_client. with authenticated_client.
    content = content.replace('test_client.post(', 'authenticated_client.post(')
    content = content.replace('test_client.get(', 'authenticated_client.get(')
    content = content.replace('test_client.put(', 'authenticated_client.put(')
    content = content.replace('test_client.patch(', 'authenticated_client.patch(')
    content = content.replace('test_client.delete(', 'authenticated_client.delete(')
    
    # Step 6: Remove headers=auth_headers from requests
    content = re.sub(r',\s*headers=auth_headers', '', content)
    content = re.sub(r'headers=auth_headers,\s*', '', content)
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Fixed {filepath}")

if __name__ == '__main__':
    fix_test_file('tests/test_ipam_enhancements.py')
    print("Authentication mocking fixed!")
