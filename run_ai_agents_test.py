#!/usr/bin/env python3
"""
AI Agents Test Launcher

Simple launcher script for the AI Agents Real-World Testing Suite.
Handles environment setup and launches the Streamlit application.

Usage:
    python run_ai_agents_test.py
    
    Or directly:
    streamlit run ai_agents_real_world_test.py
"""

import subprocess
import sys
import os
from pathlib import Path

def check_requirements():
    """Check if required packages are installed."""
    required_packages = [
        'streamlit',
        'fastapi', 
        'pydantic',
        'motor',
        'redis'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("📦 Install them with:")
        print(f"   pip install {' '.join(missing_packages)}")
        print("\n   Or install from requirements:")
        print("   pip install -r requirements_streamlit.txt")
        return False
    
    return True

def check_environment():
    """Check if the environment is properly configured."""
    # Check if we're in the right directory
    if not Path("src/second_brain_database").exists():
        print("❌ Please run this script from the project root directory")
        print("   (The directory containing src/second_brain_database/)")
        return False
    
    # Check if configuration files exist
    config_files = [".sbd", ".env"]
    config_found = any(Path(f).exists() for f in config_files)
    
    if not config_found:
        print("⚠️  No configuration file found (.sbd or .env)")
        print("   The app may not work properly without proper configuration")
        print("   Continue anyway? (y/n): ", end="")
        
        response = input().lower().strip()
        if response not in ['y', 'yes']:
            return False
    
    return True

def launch_streamlit():
    """Launch the Streamlit application."""
    try:
        print("🚀 Launching AI Agents Real-World Testing Suite...")
        print("📱 The app will open in your default web browser")
        print("🔗 URL: http://localhost:8501")
        print("\n⏹️  Press Ctrl+C to stop the application\n")
        
        # Launch Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "ai_agents_real_world_test.py",
            "--server.port", "8501",
            "--server.address", "localhost"
        ])
        
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Failed to launch Streamlit: {e}")
        return False
    
    return True

def main():
    """Main launcher function."""
    print("🤖 AI Agents Real-World Testing Suite Launcher")
    print("=" * 50)
    
    # Check requirements
    print("🔍 Checking requirements...")
    if not check_requirements():
        sys.exit(1)
    
    # Check environment
    print("🔍 Checking environment...")
    if not check_environment():
        sys.exit(1)
    
    print("✅ All checks passed!")
    print()
    
    # Launch the application
    if not launch_streamlit():
        sys.exit(1)

if __name__ == "__main__":
    main()