#!/usr/bin/env python3
"""
Test script to verify the performance timer fix by importing the module
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_performance_timer_import():
    """Test that the performance timer can be imported correctly"""
    try:
        from second_brain_database.utils.ai_metrics import PerformanceTimer, ai_performance_monitor
        print("✅ PerformanceTimer imported successfully")
        
        # Test creating a PerformanceTimer instance
        timer = PerformanceTimer(ai_performance_monitor, "test_metric", metadata={"test": True})
        print("✅ PerformanceTimer instance created successfully")
        
        # Test using it as a context manager
        with timer:
            print("✅ PerformanceTimer context manager works")
        
        return True
        
    except Exception as e:
        print(f"❌ Error importing or using PerformanceTimer: {e}")
        return False

def test_routes_import():
    """Test that the AI routes can be imported without errors"""
    try:
        from second_brain_database.routes.ai.routes import router
        print("✅ AI routes imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error importing AI routes: {e}")
        return False

if __name__ == "__main__":
    print("Testing Performance Timer Fix...")
    print("=" * 50)
    
    success1 = test_performance_timer_import()
    success2 = test_routes_import()
    
    print("=" * 50)
    if success1 and success2:
        print("🎉 All tests PASSED - Performance timer fix is working!")
    else:
        print("💥 Some tests FAILED - There may still be issues")