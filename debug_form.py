#!/usr/bin/env python3
"""
Debug script to test form data handling.
"""

import asyncio
from fastapi import FastAPI, Form
from fastapi.testclient import TestClient

app = FastAPI()

@app.post("/test-form")
async def test_form(
    csrf_token: str = Form(...),
    identifier: str = Form(...),
    password: str = Form(...)
):
    return {
        "csrf_token": csrf_token,
        "identifier": identifier,
        "password": password
    }

def test_form_handling():
    client = TestClient(app)
    
    response = client.post(
        "/test-form",
        data={
            "csrf_token": "test",
            "identifier": "rohanbatra", 
            "password": "test123"
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    test_form_handling()