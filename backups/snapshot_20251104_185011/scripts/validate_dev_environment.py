#!/usr/bin/env python3
"""
Development Environment Validation Script

This script validates that all required development dependencies are properly installed
and accessible in the current environment.
"""

import subprocess
import sys
from typing import Dict, List, Tuple


def run_command(command: List[str]) -> Tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)


def validate_development_tools() -> Dict[str, Tuple[bool, str]]:
    """Validate all development tools are available and working."""
    tools = {
        "pylint": ["uv", "run", "pylint", "--version"],
        "black": ["uv", "run", "black", "--version"],
        "isort": ["uv", "run", "isort", "--version"],
        "mypy": ["uv", "run", "mypy", "--version"],
        "pytest": ["uv", "run", "pytest", "--version"],
        "pre-commit": ["uv", "run", "pre-commit", "--version"],
    }

    results = {}
    for tool_name, command in tools.items():
        success, output = run_command(command)
        results[tool_name] = (success, output)

    return results


def validate_uv_installation() -> Tuple[bool, str]:
    """Validate that uv is installed and working."""
    return run_command(["uv", "--version"])


def validate_python_imports() -> Dict[str, Tuple[bool, str]]:
    """Validate that key development packages can be imported."""
    import_tests = {
        "pylint": "import pylint; print(f'pylint {pylint.__version__}')",
        "black": "import black; print(f'black {black.__version__}')",
        "isort": "import isort; print(f'isort {isort.__version__}')",
        "mypy": "import mypy.version; print(f'mypy {mypy.version.__version__}')",
        "pytest": "import pytest; print(f'pytest {pytest.__version__}')",
    }

    results = {}
    for package_name, import_code in import_tests.items():
        success, output = run_command(["uv", "run", "python", "-c", import_code])
        results[package_name] = (success, output)

    return results


def print_results(title: str, results: Dict[str, Tuple[bool, str]]) -> bool:
    """Print validation results in a formatted way."""
    print(f"\n{title}")
    print("=" * len(title))

    all_passed = True
    for tool_name, (success, output) in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{tool_name:12} {status:8} {output}")
        if not success:
            all_passed = False

    return all_passed


def main():
    """Main validation function."""
    print("Development Environment Validation")
    print("=" * 40)

    # Check uv installation
    uv_success, uv_output = validate_uv_installation()
    print(f"\nUV Installation: {'✅ PASS' if uv_success else '❌ FAIL'} {uv_output}")

    if not uv_success:
        print("\n❌ UV is not installed or not working properly.")
        print("Please install UV first: https://docs.astral.sh/uv/getting-started/installation/")
        sys.exit(1)

    # Validate development tools
    tool_results = validate_development_tools()
    tools_passed = print_results("Development Tools", tool_results)

    # Validate Python imports
    import_results = validate_python_imports()
    imports_passed = print_results("Python Package Imports", import_results)

    # Summary
    print(f"\n{'='*40}")
    if tools_passed and imports_passed:
        print("✅ All development dependencies are properly installed and working!")
        print("\nYou can now use the following commands:")
        print("  uv run pylint src/")
        print("  uv run black src/ tests/")
        print("  uv run isort src/ tests/")
        print("  uv run mypy src/")
        print("  uv run pytest")
        sys.exit(0)
    else:
        print("❌ Some development dependencies are missing or not working properly.")
        print("\nTo fix this, try running:")
        print("  uv sync --extra dev")
        sys.exit(1)


if __name__ == "__main__":
    main()
