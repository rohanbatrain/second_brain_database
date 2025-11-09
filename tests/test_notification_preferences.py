#!/usr/bin/env python3
"""
Test script for notification preferences endpoint fix.
"""

import json

import requests


# Test the notification preferences endpoint
def test_notification_preferences():
    # First, login to get access token
    login_url = "http://localhost:8000/auth/login"
    login_data = {"username": "rohanbatra", "password": "Letters,123"}

    print("Logging in...")
    login_response = requests.post(login_url, json=login_data)
    print(f"Login status: {login_response.status_code}")

    if login_response.status_code != 200:
        print("Login failed!")
        return

    access_token = login_response.json().get("access_token")
    if not access_token:
        print("No access token received!")
        return

    headers = {"Authorization": f"Bearer {access_token}"}

    # Test GET notification preferences
    print("\nTesting GET /family/notifications/preferences...")
    get_response = requests.get("http://localhost:8000/family/notifications/preferences", headers=headers)
    print(f"GET status: {get_response.status_code}")
    if get_response.status_code == 200:
        print("GET response:", json.dumps(get_response.json(), indent=2))
    else:
        print("GET failed:", get_response.text)

    # Test PUT notification preferences
    print("\nTesting PUT /family/notifications/preferences...")
    preferences_data = {"email_notifications": True, "push_notifications": False, "sms_notifications": True}

    put_response = requests.put(
        "http://localhost:8000/family/notifications/preferences", json=preferences_data, headers=headers
    )
    print(f"PUT status: {put_response.status_code}")
    if put_response.status_code == 200:
        print("PUT response:", json.dumps(put_response.json(), indent=2))
    else:
        print("PUT failed:", put_response.text)


if __name__ == "__main__":
    test_notification_preferences()
