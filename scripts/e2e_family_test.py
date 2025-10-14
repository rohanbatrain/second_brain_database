#!/usr/bin/env python3
"""
Simple end-to-end script to test family endpoints against a running local server.
Flow:
 - Register user A
 - Register user B
 - Login user A -> get token
 - Create family (user A)
 - Invite user B to family (by email)
 - Login user B -> get token
 - Respond to invitation (accept) as user B
 - Verify user B's families include the created family

Run: python3 scripts/e2e_family_test.py
"""
import sys
import time
import uuid
import requests

BASE = "http://127.0.0.1:8000"

pw = "TestPassw0rd!"  # meets validation rules

def make_email(prefix):
    return f"{prefix}+{uuid.uuid4().hex[:8]}@example.com"


def register(username, email, password):
    url = f"{BASE}/auth/register"
    payload = {"username": username, "email": email, "password": password}
    r = requests.post(url, json=payload)
    print(f"REGISTER {email} -> {r.status_code}")
    if r.status_code not in (200,201):
        print(r.text)
        raise SystemExit(2)
    return r.json()


def verify_email_by_username(username):
    url = f"{BASE}/auth/verify-email?username={username}"
    r = requests.get(url)
    print(f"VERIFY {username} -> {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        raise SystemExit(2)
    return r.json()


def login_email(email, password):
    url = f"{BASE}/auth/login"
    payload = {"email": email, "password": password}
    r = requests.post(url, json=payload)
    print(f"LOGIN {email} -> {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        raise SystemExit(3)
    return r.json()["access_token"]


def create_family(token, name):
    url = f"{BASE}/family/create"
    headers = {"Authorization": f"Bearer {token}"}
    # Avoid reserved prefixes like 'family_' (validation treats reserved prefixes as invalid
    # if they appear anywhere in the name). Use a safe short name instead.
    payload = {"name": name.replace("Family", "Clan")}
    r = requests.post(url, json=payload, headers=headers)
    print(f"CREATE FAMILY -> {r.status_code}")
    if r.status_code != 201:
        print(r.text)
        raise SystemExit(4)
    return r.json()


def invite_member(token, family_id, invitee_email):
    url = f"{BASE}/family/{family_id}/invite"
    headers = {"Authorization": f"Bearer {token}"}
    # New API expects an identifier and identifier_type (email or username)
    payload = {"identifier": invitee_email, "relationship_type": "child", "identifier_type": "email"}
    r = requests.post(url, json=payload, headers=headers)
    print(f"INVITE {invitee_email} -> {r.status_code}")
    if r.status_code != 201:
        print(r.text)
        raise SystemExit(5)
    return r.json()


def respond_invitation(token, invitation_id, action="accept"):
    url = f"{BASE}/family/invitation/{invitation_id}/respond"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"action": action}
    r = requests.post(url, json=payload, headers=headers)
    print(f"RESPOND INVITE {invitation_id} -> {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        raise SystemExit(6)
    return r.json()


def get_my_families(token):
    url = f"{BASE}/family/my-families"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    print(f"GET MY FAMILIES -> {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        raise SystemExit(7)
    return r.json()


if __name__ == "__main__":
    # Create two demo users
    u1 = f"demo_user_a_{uuid.uuid4().hex[:6]}"
    u2 = f"demo_user_b_{uuid.uuid4().hex[:6]}"
    email1 = make_email('a')
    email2 = make_email('b')

    print("Registering users...")
    register(u1, email1, pw)
    register(u2, email2, pw)

    print("Verifying user emails...")
    verify_email_by_username(u1)
    verify_email_by_username(u2)

    print("Logging in user A")
    token_a = login_email(email1, pw)

    print("Creating family as A")
    # Use a full UUID hex to minimize chance of name collisions in local DB
    fam = create_family(token_a, f"TestFamily_{uuid.uuid4().hex}")
    family_id = fam.get("family_id")
    print("Created family:", family_id)

    print("Inviting user B by email")
    inv = invite_member(token_a, family_id, email2)
    invitation_id = inv.get("invitation_id")
    print("Invitation ID:", invitation_id)

    print("Logging in user B")
    token_b = login_email(email2, pw)

    print("User B accepting invitation")
    resp = respond_invitation(token_b, invitation_id, action="accept")
    print("Invitation response:", resp)

    print("Verifying membership for user B")
    families_b = get_my_families(token_b)
    print("User B families:", families_b)
    found = any(f.get("family_id") == family_id for f in families_b)
    if not found:
        print("Family not found in user B's families")
        sys.exit(8)

    print("E2E test completed successfully")
    sys.exit(0)
