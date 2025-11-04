#!/usr/bin/env python3
"""
Create a test user and a permanent token against a running Second Brain Database server.

Usage:
  python scripts/create_test_user.py --base-url http://localhost:8001 --username test_user --email test@example.com --password 'TestPass123!' --token-desc 'local-dev token'

Notes:
- The script calls POST /auth/register to create a user (returns JWT access token).
- Then it calls POST /auth/permanent-tokens with the access token to create a permanent token.
- The permanent token value is returned only once by the server; store it securely.

This is a convenience tool for local development and tests. Do NOT use it against production systems without review.
"""

import argparse
import sys
import json
from typing import Optional

import httpx


def register_user(base_url: str, username: str, email: str, password: str) -> dict:
    url = base_url.rstrip("/") + "/auth/register"
    payload = {
        "username": username,
        "email": email,
        "password": password,
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, json=payload)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"Registration failed: {r.status_code} {r.text}")
        raise
    return r.json()


def create_permanent_token(base_url: str, access_token: str, description: Optional[str] = None, ip_restrictions: Optional[list] = None) -> dict:
    url = base_url.rstrip("/") + "/auth/permanent-tokens"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {}
    if description is not None:
        payload["description"] = description
    if ip_restrictions is not None:
        payload["ip_restrictions"] = ip_restrictions

    with httpx.Client(timeout=30.0, headers=headers) as client:
        r = client.post(url, json=payload)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError:
        print(f"Permanent token creation failed: {r.status_code} {r.text}")
        raise
    return r.json()


def main():
    p = argparse.ArgumentParser(description="Create test user and permanent token")
    p.add_argument("--base-url", required=True, help="Base URL of the server, e.g. http://localhost:8001")
    p.add_argument("--username", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--token-desc", default="dev-test-token", help="Description for the permanent token")
    p.add_argument("--ip-restrictions", nargs="*", help="Optional IP restrictions (space separated)")
    args = p.parse_args()

    try:
        print(f"Registering user {args.username} <{args.email}>...")
        reg = register_user(args.base_url, args.username, args.email, args.password)
        access_token = reg.get("access_token")
        if not access_token:
            print("Server did not return access_token after registration. Response:")
            print(json.dumps(reg, indent=2))
            sys.exit(1)
        print("Registration successful. Got access token.")

        print("Creating permanent token...")
        token_resp = create_permanent_token(args.base_url, access_token, description=args.token_desc, ip_restrictions=args.ip_restrictions)

        # token_resp conforms to PermanentTokenResponse: contains token and token_id
        print("Permanent token created — STORE THIS SECURELY. This is the only time it will be shown.")
        print(json.dumps(token_resp, indent=2))
    except Exception as e:
        print("Error:", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
