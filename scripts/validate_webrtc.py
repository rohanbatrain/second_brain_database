#!/usr/bin/env python3
"""
WebRTC Startup Validation

This script validates that the WebRTC implementation is properly
integrated and all dependencies are available.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def validate_imports():
    """Validate all WebRTC imports."""
    print("🔍 Validating WebRTC imports...")
    
    try:
        # Core imports
        from second_brain_database.webrtc import router, webrtc_manager
        from second_brain_database.webrtc.schemas import (
            WebRtcMessage,
            MessageType,
            WebRtcConfig,
            IceServerConfig
        )
        from second_brain_database.webrtc.dependencies import get_current_user_ws
        from second_brain_database.webrtc.connection_manager import WebRtcManager
        
        print("  ✅ Core WebRTC imports successful")
        
        # Validate router is a FastAPI router
        from fastapi import APIRouter
        assert isinstance(router, APIRouter), "router is not an APIRouter instance"
        print("  ✅ Router is valid FastAPI APIRouter")
        
        # Validate schemas
        assert hasattr(MessageType, 'OFFER'), "MessageType missing OFFER"
        assert hasattr(MessageType, 'ANSWER'), "MessageType missing ANSWER"
        assert hasattr(MessageType, 'ICE_CANDIDATE'), "MessageType missing ICE_CANDIDATE"
        print("  ✅ Message schemas validated")
        
        # Validate manager
        assert hasattr(webrtc_manager, 'publish_to_room'), "Missing publish_to_room"
        assert hasattr(webrtc_manager, 'subscribe_to_room'), "Missing subscribe_to_room"
        print("  ✅ Connection manager validated")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except AssertionError as e:
        print(f"  ❌ Validation error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False


def validate_configuration():
    """Validate WebRTC configuration."""
    print("\n🔍 Validating WebRTC configuration...")
    
    try:
        from second_brain_database.config import settings
        
        # Check WebRTC settings exist
        assert hasattr(settings, 'WEBRTC_STUN_URLS'), "Missing WEBRTC_STUN_URLS"
        assert hasattr(settings, 'WEBRTC_ICE_TRANSPORT_POLICY'), "Missing WEBRTC_ICE_TRANSPORT_POLICY"
        assert hasattr(settings, 'WEBRTC_ROOM_PRESENCE_TTL'), "Missing WEBRTC_ROOM_PRESENCE_TTL"
        
        print(f"  ✅ STUN URLs: {settings.WEBRTC_STUN_URLS}")
        print(f"  ✅ ICE Transport Policy: {settings.WEBRTC_ICE_TRANSPORT_POLICY}")
        print(f"  ✅ Presence TTL: {settings.WEBRTC_ROOM_PRESENCE_TTL}s")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Config import error: {e}")
        return False
    except AssertionError as e:
        print(f"  ❌ Config validation error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False


def validate_main_integration():
    """Validate integration with main app."""
    print("\n🔍 Validating main app integration...")
    
    try:
        # Import main app
        from second_brain_database.main import app
        
        # Check if WebRTC router is included
        routes = [route.path for route in app.routes]
        
        # Look for WebRTC routes
        webrtc_routes = [r for r in routes if '/webrtc' in r]
        
        if webrtc_routes:
            print(f"  ✅ Found {len(webrtc_routes)} WebRTC routes:")
            for route in webrtc_routes:
                print(f"     - {route}")
            return True
        else:
            print("  ⚠️  No WebRTC routes found in app")
            return False
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_router_endpoints():
    """Validate router has expected endpoints."""
    print("\n🔍 Validating router endpoints...")
    
    try:
        from second_brain_database.webrtc import router
        
        # Get all routes from the router
        routes = router.routes
        
        expected_endpoints = [
            ("/webrtc/ws/{room_id}", "websocket_endpoint"),
            ("/webrtc/config", "get_webrtc_config"),
            ("/webrtc/rooms/{room_id}/participants", "get_room_participants")
        ]
        
        found_endpoints = []
        for route in routes:
            path = getattr(route, 'path', None)
            name = getattr(route, 'name', None)
            if path:
                found_endpoints.append((path, name))
        
        print(f"  ✅ Found {len(found_endpoints)} endpoints:")
        for path, name in found_endpoints:
            print(f"     - {path} ({name})")
        
        # Check for expected endpoints
        missing = []
        for expected_path, expected_name in expected_endpoints:
            found = any(path == expected_path for path, _ in found_endpoints)
            if not found:
                missing.append(expected_path)
        
        if missing:
            print(f"  ⚠️  Missing expected endpoints: {missing}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("WebRTC Implementation Validation")
    print("=" * 60)
    
    results = []
    
    # Run validation checks
    results.append(("Imports", validate_imports()))
    results.append(("Configuration", validate_configuration()))
    results.append(("Router Endpoints", validate_router_endpoints()))
    results.append(("Main App Integration", validate_main_integration()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(result for _, result in results)
    
    print("=" * 60)
    if all_passed:
        print("🎉 All validation checks passed!")
        print("\nWebRTC implementation is ready to use.")
        print("\nNext steps:")
        print("1. Start the server: uvicorn src.second_brain_database.main:app")
        print("2. Test with: python tests/test_webrtc_client.py")
        print("3. Check docs: docs/WEBRTC_IMPLEMENTATION.md")
        return 0
    else:
        print("⚠️  Some validation checks failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
