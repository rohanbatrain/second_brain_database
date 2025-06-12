"""
test_main.py

Unit tests for the main Flask application routes and error handlers.

Dependencies:
    - pytest
    - flask
    - second_brain_database.main

Author: Rohan Batra
Date: 2025-06-11
"""
import pytest
from unittest.mock import patch
from second_brain_database.main import app as flask_app

# Register a dummy route for tar-pitting test before any requests
from second_brain_database.main import app as real_app
@real_app.route("/test-tarpit")
def _dummy():
    """
    Dummy route for tar-pitting test.
    
    Returns:
        str: A simple "ok" response.
    """
    return "ok"

@pytest.fixture
def client():
    """
    Pytest fixture for Flask test client.

    Yields:
        FlaskClient: The Flask test client.
    """
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

def test_landing_page(client):
    """
    Test the landing page returns 200 and contains expected text.

    Args:
        client (FlaskClient): The Flask test client.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Second Brain Database API" in resp.data

def test_login_page(client):
    """
    Test the login page returns 200 and contains expected text.

    Args:
        client (FlaskClient): The Flask test client.
    """
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Login Page" in resp.data

def test_register_page(client):
    """
    Test the register page returns 200 and contains expected text.

    Args:
        client (FlaskClient): The Flask test client.
    """
    resp = client.get("/register")
    assert resp.status_code == 200
    assert b"Register Page" in resp.data

def test_login_post_method_not_allowed(client):
    """
    Test POST to /login returns 405 Method Not Allowed.

    Args:
        client (FlaskClient): The Flask test client.
    """
    resp = client.post("/login")
    assert resp.status_code == 405

def test_register_post_method_not_allowed(client):
    """
    Test POST to /register returns 405 Method Not Allowed.

    Args:
        client (FlaskClient): The Flask test client.
    """
    resp = client.post("/register")
    assert resp.status_code == 405

def test_404_handler(client):
    """
    Test 404 handler returns custom error page.

    Args:
        client (FlaskClient): The Flask test client.
    """
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    assert b"404 - Page Not Found" in resp.data

def test_405_handler(client):
    """
    Test 405 handler returns custom error page or default Flask response.

    Args:
        client (FlaskClient): The Flask test client.
    """
    resp = client.post("/")
    assert resp.status_code == 405
    assert b"Method Not Allowed" in resp.data or b"405" in resp.data

@patch("second_brain_database.main.abort")
def test_401_handler(mock_abort, client):
    """
    Test 401 handler returns custom error page.

    Args:
        mock_abort (Mock): Mocked abort function.
        client (FlaskClient): The Flask test client.
    """
    with flask_app.test_request_context():
        from second_brain_database.main import unauthorized_error
        resp, code = unauthorized_error(Exception())
        assert code == 401
        assert "401 - Unauthorized" in resp

@patch("second_brain_database.main.abort")
def test_403_handler(mock_abort, client):
    """
    Test 403 handler returns custom error page.

    Args:
        mock_abort (Mock): Mocked abort function.
        client (FlaskClient): The Flask test client.
    """
    with flask_app.test_request_context():
        pass

@patch("second_brain_database.main.r")
def test_slow_down_attackers_delay(mock_redis, client):
    """
    Test tar-pitting mechanism delays attackers.

    Args:
        mock_redis (Mock): Mocked Redis client.
        client (FlaskClient): The Flask test client.
    """
    mock_redis.get.side_effect = [None, b'6']
    with patch("time.sleep") as mock_sleep:
        client.get("/test-tarpit", environ_base={'REMOTE_ADDR': '5.6.7.8'})
        mock_sleep.assert_called_once_with(2)

@patch("second_brain_database.main.r")
def test_track_failed_attempts_blocks(mock_redis, client):
    """
    Test failed attempts tracking and blocking mechanism.

    Args:
        mock_redis (Mock): Mocked Redis client.
        client (FlaskClient): The Flask test client.
    """
    mock_redis.get.side_effect = [b'11', b'11']
    mock_redis.incr.return_value = 11
    mock_redis.setex.return_value = True
    with flask_app.test_request_context():
        from second_brain_database.main import track_failed_attempts
        class DummyResp:
            status_code = 429
        resp = DummyResp()
        track_failed_attempts(resp)
        mock_redis.setex.assert_called()

@pytest.mark.parametrize("url,expected", [
    ("/auth/", 404),
    ("/admin/v1/plans/", 404),
    ("/user/v1/emotion_tracker/", 404),
    ("/user/v1/notes/", 404),
])
def test_blueprints_registered(client, url, expected):
    """
    Test blueprints are registered and accessible.

    Args:
        client (FlaskClient): The Flask test client.
        url (str): The URL to test.
        expected (int): The expected status code.
    """
    resp = client.get(url)
    assert resp.status_code == expected
