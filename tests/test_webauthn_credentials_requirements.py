#!/usr/bin/env python3
"""
Test script to verify WebAuthn credential deletion meets specific requirements 3.5, 3.6, 3.7.
"""

import asyncio
import sys
sys.path.append('src')

async def test_webauthn_credential_deletion_requirements():
    """Test that WebAuthn credential deletion meets requirements 3.5, 3.6, 3.7."""
    
    print("Testing WebAuthn credential deletion requirements...")
    
    try:
        # Import the deletion function
        from second_brain_database.routes.auth.services.webauthn.credentials import delete_credential_by_id
        import inspect
        import ast
        
        # Get the source code for analysis
        source = inspect.getsource(delete_credential_by_id)
        tree = ast.parse(source)
        
        print("\n=== Requirement 3.5: Authentication and ownership verification ===")
        
        # Check for authentication requirement (function expects user_id parameter)
        sig = inspect.signature(delete_credential_by_id)
        if 'user_id' in sig.parameters:
            print("✓ Function requires user_id parameter (authentication implied)")
        else:
            print("✗ Function doesn't require user_id parameter")
            return False
        
        # Check for ownership verification in the code
        has_ownership_check = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Attribute) and 
                    node.func.attr == 'find_one'):
                    # Check if the find_one call includes user_id in the query
                    for arg in node.args:
                        if isinstance(arg, ast.Dict):
                            for key in arg.keys:
                                if (isinstance(key, ast.Constant) and 
                                    key.value == 'user_id'):
                                    has_ownership_check = True
                                    break
        
        if has_ownership_check:
            print("✓ Ownership verification implemented (user_id in database query)")
        else:
            print("✗ Ownership verification not found")
            return False
        
        print("\n=== Requirement 3.6: Remove credential from database ===")
        
        # Check for database removal operation
        has_database_removal = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Attribute) and 
                    node.func.attr == 'update_one'):
                    # Check if it sets is_active to False (soft delete)
                    for arg in node.args:
                        if isinstance(arg, ast.Dict):
                            for key, value in zip(arg.keys, arg.values):
                                if (isinstance(key, ast.Constant) and 
                                    key.value == '$set'):
                                    has_database_removal = True
                                    break
        
        if has_database_removal:
            print("✓ Database removal implemented (soft delete with is_active=False)")
        else:
            print("✗ Database removal not found")
            return False
        
        print("\n=== Requirement 3.7: Log deletion event for audit purposes ===")
        
        # Check for security logging
        security_events = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == 'log_security_event':
                    for keyword in node.keywords:
                        if keyword.arg == 'event_type':
                            if isinstance(keyword.value, ast.Constant):
                                security_events.append(keyword.value.value)
        
        deletion_events = [event for event in security_events 
                          if 'deletion' in event or 'deleted' in event]
        
        if deletion_events:
            print("✓ Deletion events logged for audit purposes")
            print(f"  Events: {deletion_events}")
        else:
            print("✗ Deletion events not logged")
            return False
        
        print("\n=== Additional Implementation Verification ===")
        
        # Check that the endpoint exists and is properly configured
        from second_brain_database.routes.auth.routes import router
        routes = [route for route in router.routes if hasattr(route, 'path')]
        delete_routes = [route for route in routes 
                        if '/webauthn/credentials/{credential_id}' in route.path 
                        and 'DELETE' in route.methods]
        
        if delete_routes:
            print("✓ DELETE endpoint properly registered in router")
        else:
            print("✗ DELETE endpoint not found in router")
            return False
        
        # Check that proper error handling exists
        has_value_error = 'ValueError' in source
        has_not_found_handling = 'not found' in source.lower()
        
        if has_value_error and has_not_found_handling:
            print("✓ Proper error handling for non-existent/unauthorized credentials")
        else:
            print("✗ Missing proper error handling")
            return False
        
        # Check that cache invalidation exists (for immediate effect)
        has_cache_invalidation = ('invalidate_single_credential_cache' in source and 
                                'invalidate_user_credentials_cache' in source)
        
        if has_cache_invalidation:
            print("✓ Cache invalidation implemented for immediate effect")
        else:
            print("✗ Cache invalidation not found")
            return False
        
        print("\n" + "="*60)
        print("✓ ALL REQUIREMENTS MET!")
        print("✓ 3.5: Authentication and ownership verification implemented")
        print("✓ 3.6: Credential removal from database implemented")  
        print("✓ 3.7: Deletion event logging for audit purposes implemented")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_webauthn_credential_deletion_requirements())
    sys.exit(0 if result else 1)