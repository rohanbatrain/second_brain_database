"""
Test module to validate development environment setup.

This module contains tests to ensure that all development dependencies
are properly installed and the development environment is correctly configured.
"""

import subprocess
import sys
from typing import List


def test_development_tools_available():
    """Test that all development tools are available and working."""
    tools = [
        ["pylint", "--version"],
        ["black", "--version"],
        ["isort", "--version"],
        ["mypy", "--version"],
        ["pytest", "--version"],
        ["pre-commit", "--version"],
    ]

    for tool_cmd in tools:
        try:
            result = subprocess.run(["uv", "run"] + tool_cmd, capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, f"Tool {tool_cmd[0]} failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            assert False, f"Tool {tool_cmd[0]} timed out"
        except Exception as e:
            assert False, f"Tool {tool_cmd[0]} error: {e}"


def test_python_imports():
    """Test that all development dependencies can be imported."""
    import_tests = [
        "pylint",
        "black",
        "isort",
        "mypy",
        "pytest",
        "pytest_cov",
        "pytest_asyncio",
        "pre_commit",
        "multipart",
    ]

    for module_name in import_tests:
        try:
            __import__(module_name)
        except ImportError as e:
            assert False, f"Failed to import {module_name}: {e}"


def test_code_quality_tools_work():
    """Test that code quality tools can run on the codebase."""
    # Test that black can check formatting (should pass after formatting)
    result = subprocess.run(
        ["uv", "run", "black", "--check", "scripts/validate_dev_environment.py"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"Black formatting check failed: {result.stderr}"

    # Test that isort can check imports
    result = subprocess.run(
        ["uv", "run", "isort", "--check-only", "scripts/validate_dev_environment.py"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"isort import check failed: {result.stderr}"


def test_pytest_configuration():
    """Test that pytest is properly configured."""
    # Run pytest on this test file to ensure it works
    result = subprocess.run(["uv", "run", "pytest", __file__, "-v"], capture_output=True, text=True)
    # This should pass (though it will be recursive, we just want to ensure pytest works)
    assert "FAILED" not in result.stdout, f"Pytest configuration issue: {result.stdout}"


def test_development_dependencies_in_pyproject():
    """Test that development dependencies are properly declared in pyproject.toml."""
    import tomllib

    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)

    # Check that dev dependencies exist
    assert "project" in pyproject_data
    assert "optional-dependencies" in pyproject_data["project"]
    assert "dev" in pyproject_data["project"]["optional-dependencies"]

    dev_deps = pyproject_data["project"]["optional-dependencies"]["dev"]

    # Check for key development tools
    dev_dep_names = [dep.split(">=")[0].split("==")[0] for dep in dev_deps]
    required_tools = ["pylint", "black", "isort", "mypy", "pytest", "pytest-cov", "pytest-asyncio", "pre-commit"]

    for tool in required_tools:
        assert any(tool in dep for dep in dev_dep_names), f"Missing development dependency: {tool}"
