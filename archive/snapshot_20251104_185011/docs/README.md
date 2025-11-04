# Second Brain Database

A comprehensive FastAPI application for managing your second brain database - a knowledge management system designed to store, organize, and retrieve information efficiently.

## Features

- **User Authentication & Authorization**: Secure JWT-based authentication with 2FA support
- **Permanent API Tokens**: Long-lived tokens for API access and integrations
- **Knowledge Management**: Store and organize your personal knowledge base
- **Themes & Customization**: Personalize your experience with custom themes
- **Shop Integration**: Manage digital assets and purchases
- **Avatar & Banner Management**: Customize your profile appearance
- **Family Management**: Shared resources and relationships
- **Voice Agent**: LiveKit + Ollama integration for voice conversations

## Voice Agent Setup

The voice agent enables real-time voice conversations using LiveKit for WebRTC and Ollama for local LLM processing.

### Prerequisites

1. **Ollama**: Install and run Ollama locally
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.ai/install.sh | sh

   # Pull a model (e.g., llama2)
   ollama pull llama2

   # Start Ollama server
   ollama serve
   ```

2. **LiveKit Server**: Set up a LiveKit server or use LiveKit Cloud
   - Get API key and secret from your LiveKit deployment

### Configuration

Set the following environment variables:

```bash
# Ollama configuration
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3b

# LiveKit configuration
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
LIVEKIT_URL=https://your-livekit-server:7880

# Voice processing
VOICE_TTS_VOICE=en
```

### Voice Endpoints

- `POST /voice/token`: Generate LiveKit access token
- `POST /voice/ollama`: Send text prompt to Ollama
- `POST /voice/stt`: Speech-to-text (upload audio file)
- `POST /voice/tts`: Text-to-speech
- `POST /voice/agent`: Full voice pipeline (STT -> LLM -> TTS)

### Example Usage

```python
import requests

# Get LiveKit token
token_resp = requests.post("http://localhost:8000/voice/token",
                          json={"room": "voice-room", "identity": "user1"})
token = token_resp.json()["token"]

# Process voice
with open("audio.wav", "rb") as f:
    files = {"file": ("audio.wav", f, "audio/wav")}
    resp = requests.post("http://localhost:8000/voice/agent", files=files)
    result = resp.json()
    print(f"Input: {result['input_text']}")
    print(f"Response: {result['output_text']}")
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   uv sync --extra voice
   ```
3. Set up environment variables (see Configuration)
4. Run the application:
   ```bash
   uv run uvicorn src.second_brain_database.main:app --reload
   ```

## Docker

Build and run with Docker:

```bash
docker build -t second-brain-db .
docker run -p 8000:8000 -e LIVEKIT_API_KEY=... -e LIVEKIT_API_SECRET=... second-brain-db
```

## API Documentation

Access the interactive API documentation at `http://localhost:8000/docs` when running locally.

## Security

- JWT token authentication
- Rate limiting and abuse protection
- Redis-based session management
- Comprehensive audit logging

## Development

Run tests:
```bash
uv run pytest
```

Lint code:
```bash
uv run pylint src/
```

## License

MIT License