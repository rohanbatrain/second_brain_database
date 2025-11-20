#!/usr/bin/env python3
"""
Helper script to install and verify DeepSeek-R1:1.5b model for Ollama.

This script helps you install the DeepSeek-R1 model and verify it's working
with your Second Brain Database system.
"""

import subprocess
import sys
import asyncio
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.integrations.ollama import OllamaClient
from second_brain_database.config import settings


def run_command(command, description):
    """Run a shell command and return the result."""
    print(f"🔄 {description}...")
    try:
        # Split command if it's a string, otherwise use as-is
        if isinstance(command, str):
            cmd_args = command.split()
        else:
            cmd_args = command

        result = subprocess.run(cmd_args, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ {description} failed")
            if result.stderr.strip():
                print(f"   Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"❌ {description} failed with exception: {e}")
        return False


async def test_model(model_name):
    """Test if a model is working."""
    print(f"🧪 Testing {model_name}...")

    client = OllamaClient(
        base_url=settings.OLLAMA_HOST,
        timeout=60  # Longer timeout for first run
    )

    try:
        response = await client.generate(
            f"Hello! Please confirm you are {model_name} and say hello back.",
            model=model_name,
            temperature=0.3
        )
        print(f"✅ {model_name} is working!")
        print(f"   Response: {response[:100]}...")
        await client.close()
        return True
    except Exception as e:
        print(f"❌ {model_name} test failed: {e}")
        await client.close()
        return False


def main():
    """Main installation and verification process."""
    print("🚀 DeepSeek-R1:1.5b Installation Helper")
    print("=" * 50)

    # Check if Ollama is installed
    print("1️⃣ Checking Ollama installation...")
    if not run_command("ollama --version", "Checking Ollama version"):
        print("❌ Ollama is not installed or not in PATH")
        print("💡 Please install Ollama first: https://ollama.ai/")
        return 1

    # List current models
    print("\n2️⃣ Listing current models...")
    run_command("ollama list", "Listing installed models")

    # Check if DeepSeek-R1 is already installed
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if result.returncode == 0 and "deepseek-r1" in result.stdout:
        print("✅ DeepSeek-R1 is already installed!")
    else:
        print("\n3️⃣ Installing DeepSeek-R1:1.5b...")
        print("⚠️ This may take several minutes depending on your internet connection...")

        if not run_command("ollama pull deepseek-r1:1.5b", "Installing DeepSeek-R1:1.5b"):
            print("❌ Failed to install DeepSeek-R1:1.5b")
            print("💡 Try running manually: ollama pull deepseek-r1:1.5b")
            return 1

    # Verify both models are available
    print("\n4️⃣ Verifying model availability...")

    async def verify_models():
        models_to_test = ["gemma3:1b", "deepseek-r1:1.5b"]
        results = []

        for model in models_to_test:
            result = await test_model(model)
            results.append((model, result))

        return results

    try:
        model_results = asyncio.run(verify_models())

        print("\n📊 Model Verification Results:")
        all_working = True
        for model, working in model_results:
            status = "✅ Working" if working else "❌ Failed"
            print(f"   {model}: {status}")
            if not working:
                all_working = False

        if all_working:
            print("\n🎉 All models are working correctly!")
            print("\n💡 Next steps:")
            print("   - Run: python test_deepseek_integration.py")
            print("   - Try the intelligent model selection features")
            print("   - Use DeepSeek-R1 for complex reasoning tasks")
            print("   - Use Gemma3 for fast, simple responses")
            return 0
        else:
            print("\n⚠️ Some models are not working properly")
            print("💡 Troubleshooting:")
            print("   - Make sure Ollama is running")
            print("   - Try restarting Ollama: ollama serve")
            print("   - Check model names: ollama list")
            return 1

    except Exception as e:
        print(f"❌ Model verification failed: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Installation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
