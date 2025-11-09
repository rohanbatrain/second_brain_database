#!/usr/bin/env python3
"""
Test script for User Agent lockdown email functions.
"""

import asyncio
import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


async def test_user_agent_email_functions():
    """Test the User Agent lockdown email functions."""
    try:
        # Import the functions
        # Import the HTML template function
        from second_brain_database.routes.auth.routes_html import render_trusted_user_agent_lockdown_email
        from second_brain_database.routes.auth.services.auth.password import (
            send_blocked_user_agent_notification,
            send_user_agent_lockdown_code_email,
        )

        print("✅ Successfully imported User Agent lockdown email functions")

        # Test the HTML template function
        test_code = "ABC123"
        test_action = "enable"
        test_user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        ]

        html_content = render_trusted_user_agent_lockdown_email(test_code, test_action, test_user_agents)
        print("✅ Successfully rendered User Agent lockdown email template")
        print(f"Template length: {len(html_content)} characters")

        # Test the email functions (they will use console output in dev mode)
        print("\n--- Testing send_user_agent_lockdown_code_email ---")
        await send_user_agent_lockdown_code_email(
            email="test@example.com", code=test_code, action=test_action, trusted_user_agents=test_user_agents
        )

        print("\n--- Testing send_blocked_user_agent_notification ---")
        await send_blocked_user_agent_notification(
            email="test@example.com",
            attempted_user_agent="Mozilla/5.0 (Unknown Browser)",
            trusted_user_agents=test_user_agents,
            endpoint="/api/test-endpoint",
        )

        print("\n✅ All User Agent lockdown email functions work correctly!")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing functions: {e}")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_user_agent_email_functions())
    sys.exit(0 if success else 1)
