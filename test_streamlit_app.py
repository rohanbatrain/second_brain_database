#!/usr/bin/env python3
"""
Test script to verify the Streamlit app can start without errors.
"""

import sys
import os
import subprocess
import time
import signal
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

def test_streamlit_import():
    """Test if the Streamlit app can be imported without errors."""
    print("🔍 Testing Streamlit app import...")
    
    try:
        # Try to import the main components
        import streamlit as st
        print("  ✓ Streamlit imported successfully")
        
        # Test if we can import our app components
        from ai_agents_real_world_test import AIAgentTester, REAL_WORLD_SCENARIOS, TEST_USER_CONTEXTS
        print("  ✓ AI testing components imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False

def test_streamlit_syntax():
    """Test if the Streamlit app has valid syntax."""
    print("🔍 Testing Streamlit app syntax...")
    
    try:
        # Use Python to check syntax
        result = subprocess.run([
            sys.executable, "-m", "py_compile", "ai_agents_real_world_test.py"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("  ✓ Streamlit app syntax is valid")
            return True
        else:
            print(f"  ❌ Syntax error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ Syntax check timed out")
        return False
    except Exception as e:
        print(f"  ❌ Syntax check failed: {e}")
        return False

def test_streamlit_startup():
    """Test if the Streamlit app can start (quick test)."""
    print("🔍 Testing Streamlit app startup...")
    
    try:
        # Start Streamlit in the background
        process = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", 
            "ai_agents_real_world_test.py",
            "--server.port", "8502",  # Use different port to avoid conflicts
            "--server.headless", "true",
            "--server.runOnSave", "false"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait a few seconds for startup
        time.sleep(5)
        
        # Check if process is still running
        if process.poll() is None:
            print("  ✓ Streamlit app started successfully")
            
            # Terminate the process
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"  ❌ Streamlit app failed to start")
            print(f"  Error: {stderr}")
            return False
            
    except Exception as e:
        print(f"  ❌ Startup test failed: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 Streamlit App Testing")
    print("=" * 30)
    
    # Test imports
    imports_ok = test_streamlit_import()
    
    if not imports_ok:
        print("\n❌ Import tests failed. Cannot proceed with further tests.")
        return False
    
    # Test syntax
    syntax_ok = test_streamlit_syntax()
    
    if not syntax_ok:
        print("\n❌ Syntax tests failed. Fix syntax errors before proceeding.")
        return False
    
    # Test startup (optional - can be slow)
    print("\n🚀 Testing app startup (this may take a moment)...")
    startup_ok = test_streamlit_startup()
    
    if startup_ok:
        print("\n🎉 All tests passed! The Streamlit app should work correctly.")
        print("\nTo run the app:")
        print("  python run_ai_agents_test.py")
        print("  # or")
        print("  streamlit run ai_agents_real_world_test.py")
        return True
    else:
        print("\n⚠️  App startup test failed, but imports and syntax are OK.")
        print("The app may still work - try running it manually:")
        print("  streamlit run ai_agents_real_world_test.py")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)