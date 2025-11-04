#!/usr/bin/env python3
"""
Development Environment Setup Script

This script sets up the development environment by installing all required dependencies
and validating the installation.
"""

from pathlib import Path
import subprocess
import sys


def run_command(command: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Command: {' '.join(command)}")
        print(f"   Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"❌ {description} failed: Command not found")
        return False


def check_uv_installed() -> bool:
    """Check if uv is installed."""
    try:
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    """Main setup function."""
    print("Development Environment Setup")
    print("=" * 40)

    # Check if uv is installed
    if not check_uv_installed():
        print("❌ UV is not installed.")
        print("Please install UV first: https://docs.astral.sh/uv/getting-started/installation/")
        print("\nQuick install options:")
        print("  # On macOS and Linux:")
        print("  curl -LsSf https://astral.sh/uv/install.sh | sh")
        print("\n  # On Windows:")
        print('  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"')
        sys.exit(1)

    print("✅ UV is installed")

    # Install development dependencies
    success = run_command(["uv", "sync", "--extra", "dev"], "Installing development dependencies")

    if not success:
        print("\n❌ Failed to install development dependencies")
        sys.exit(1)

    # Run validation script
    validation_script = Path(__file__).parent / "validate_dev_environment.py"
    if validation_script.exists():
        print(f"\n🔄 Running validation...")
        result = subprocess.run(["uv", "run", "python", str(validation_script)], capture_output=False)

        if result.returncode == 0:
            print(f"\n🎉 Development environment setup completed successfully!")
        else:
            print(f"\n❌ Validation failed. Please check the output above.")
            sys.exit(1)
    else:
        print(f"\n✅ Development dependencies installed successfully!")
        print(f"\nYou can now use the following commands:")
        print(f"  uv run pylint src/")
        print(f"  uv run black src/ tests/")
        print(f"  uv run isort src/ tests/")
        print(f"  uv run mypy src/")
        print(f"  uv run pytest")


if __name__ == "__main__":
    main()
