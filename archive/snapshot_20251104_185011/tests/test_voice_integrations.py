"""Tests for voice integrations."""

import pytest
from unittest.mock import AsyncMock, patch

from second_brain_database.integrations.ollama import OllamaClient
from second_brain_database.integrations.livekit import create_access_token
from second_brain_database.integrations.voice_processor import VoiceProcessor


class TestOllamaClient:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        from unittest.mock import MagicMock
        client = OllamaClient("http://test.com")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Hello world"}
        mock_resp.raise_for_status = AsyncMock()

        with patch.object(client._client, 'post', return_value=mock_resp) as mock_post:
            result = await client.generate("test prompt")
            assert result == "Hello world"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_options(self):
        from unittest.mock import MagicMock
        client = OllamaClient("http://test.com")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Response"}
        mock_resp.raise_for_status = AsyncMock()

        with patch.object(client._client, 'post', return_value=mock_resp) as mock_post:
            result = await client.generate("prompt", model="test-model", temperature=0.5)
            assert result == "Response"
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert payload['model'] == "test-model"
            assert payload['options']['temperature'] == 0.5


class TestLiveKitToken:
    def test_create_access_token(self):
        token = create_access_token("api_key", "secret", "identity", "room")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_grants(self):
        token = create_access_token("api_key", "secret", "identity", "room", can_publish=False)
        assert isinstance(token, str)


class TestVoiceProcessor:
    @patch('pyttsx3.init')
    def test_init(self, mock_tts):
        mock_tts.return_value = AsyncMock()
        processor = VoiceProcessor()
        assert processor.tts_engine is not None

    @pytest.mark.asyncio
    async def test_speech_to_text(self):
        processor = VoiceProcessor()
        with patch.object(processor.stt_recognizer, 'recognize_google', return_value="hello"):
            result = await processor.speech_to_text(b"audio_data")
            assert result == "hello"

    @pytest.mark.asyncio
    async def test_text_to_speech(self):
        processor = VoiceProcessor()
        processor.tts_engine = AsyncMock()

        with patch('tempfile.NamedTemporaryFile') as mock_tmp:
            mock_file = mock_tmp.return_value.__enter__.return_value
            mock_file.name = "/tmp/test.wav"
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = b"audio_bytes"
                result = await processor.text_to_speech("hello")
                assert result == b"audio_bytes"