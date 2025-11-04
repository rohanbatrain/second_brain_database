"""Tests for voice routes."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient

from second_brain_database.main import app
from second_brain_database.integrations.voice_processor import voice_processor


@pytest.fixture
def client():
    from second_brain_database.main import app
    from second_brain_database.routes.auth.services.auth.login import get_current_user
    
    # Mock auth for all tests
    app.dependency_overrides[get_current_user] = lambda: {"_id": "user1"}
    
    client = TestClient(app)
    yield client
    # Clean up
    app.dependency_overrides = {}


class TestVoiceRoutes:
    @patch('second_brain_database.routes.voice.settings')
    def test_get_livekit_token_missing_config(self, mock_settings, client):
        mock_settings.LIVEKIT_API_KEY = None
        mock_settings.LIVEKIT_API_SECRET = None
        response = client.post("/voice/token", json={})
        assert response.status_code == 503

    @patch('second_brain_database.routes.voice._get_ollama_client')
    def test_call_ollama_success(self, mock_client_func, client):
        mock_client = AsyncMock()
        mock_client.generate.return_value = "response"
        mock_client_func.return_value = mock_client

        response = client.post("/voice/ollama", json={"prompt": "hello"})
        assert response.status_code == 200
        assert response.json()["result"] == "response"

    @patch.object(voice_processor, 'speech_to_text')
    def test_speech_to_text(self, mock_stt, client):
        mock_stt.return_value = "transcribed text"

        # Mock file upload
        files = {"file": ("test.wav", b"audio_data", "audio/wav")}
        response = client.post("/voice/stt", files=files)
        assert response.status_code == 200
        assert response.json()["text"] == "transcribed text"

    @patch.object(voice_processor, 'text_to_speech')
    def test_text_to_speech(self, mock_tts, client):
        mock_tts.return_value = b"audio_bytes"

        response = client.post("/voice/tts", json={"prompt": "hello"})
        assert response.status_code == 200
        assert response.json()["audio"] == "YXVkaW9fYnl0ZXM="  # base64 encoded

    @patch.object(voice_processor, 'speech_to_text')
    @patch('second_brain_database.routes.voice._get_ollama_client')
    @patch.object(voice_processor, 'text_to_speech')
    def test_voice_agent_pipeline(self, mock_tts, mock_client_func, mock_stt, client):
        # Mock STT
        mock_stt.return_value = "hello world"

        # Mock Ollama
        mock_client = AsyncMock()
        mock_client.generate.return_value = "Hello back!"
        mock_client_func.return_value = mock_client

        # Mock TTS
        mock_tts.return_value = b"tts_audio"

        files = {"file": ("test.wav", b"audio_data", "audio/wav")}
        response = client.post("/voice/agent", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["input_text"] == "hello world"
        assert data["output_text"] == "Hello back!"
        assert data["audio"] == "dHRzX2F1ZGlv"  # base64