#!/bin/bash

# OAuth2 Test Flask App Setup Script

set -e

echo "🚀 Setting up OAuth2 Test Flask Application"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "📝 Please edit .env file with your OAuth2 configuration:"
    echo "   - OAUTH2_CLIENT_ID: Your OAuth2 client ID"
    echo "   - OAUTH2_CLIENT_SECRET: Your OAuth2 client secret"
    echo "   - OAUTH2_BASE_URL: Your OAuth2 provider URL (e.g., http://localhost:8000)"
    echo "   - SECRET_KEY: A secure secret key for Flask sessions"
    echo ""
fi

# Run tests
echo "🧪 Running tests..."
python test_oauth2.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Edit .env file with your OAuth2 configuration"
echo "   2. Start your OAuth2 provider (Second Brain Database)"
echo "   3. Run the application: python app.py"
echo "   4. Open http://localhost:5000 in your browser"
echo ""
echo "🐳 Docker alternative:"
echo "   docker-compose up --build"
echo ""
echo "🔍 Troubleshooting:"
echo "   - Check logs for detailed error information"
echo "   - Verify OAuth2 provider is running and accessible"
echo "   - Ensure redirect URI matches registered client"
echo "   - Test with: curl http://localhost:5000/health"