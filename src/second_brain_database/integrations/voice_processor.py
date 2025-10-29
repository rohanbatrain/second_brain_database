"""Voice processing pipeline for STT and TTS.

This module provides speech-to-text (STT) using SpeechRecognition and text-to-speech (TTS)
using pyttsx3. It handles audio transcoding and processing for the voice agent.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import asyncio
import subprocess

try:
    # Optional dependency: ffmpeg-python provides the `ffmpeg` module.
    # The project declares this in dependencies, but allow importing the module
    # to be optional at runtime so missing packages don't crash the app at import time.
    import ffmpeg  # type: ignore
    _HAS_FFMPEG = True
except Exception:  # pragma: no cover - environment dependent
    ffmpeg = None  # type: ignore
    _HAS_FFMPEG = False
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import pyttsx3

from second_brain_database.config import settings


class VoiceProcessor:
    def __init__(self):
        self.stt_recognizer = sr.Recognizer()
        self.tts_engine = pyttsx3.init()

    async def speech_to_text(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """Convert audio bytes to text using SpeechRecognition."""
        # Convert bytes to AudioData
        audio = sr.AudioData(audio_data, sample_rate, 2)  # 2 bytes per sample

        try:
            text = self.stt_recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            raise RuntimeError(f"STT service error: {e}")

    async def text_to_speech(self, text: str, output_path: Optional[str] = None) -> bytes:
        """Convert text to speech using pyttsx3."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            try:
                # Generate speech
                self.tts_engine.save_to_file(text, tmp.name)
                self.tts_engine.runAndWait()

                # Read back as bytes
                with open(tmp.name, "rb") as f:
                    audio_bytes = f.read()

                return audio_bytes
            finally:
                Path(tmp.name).unlink(missing_ok=True)

    async def transcode_audio(self, audio_data: bytes, from_format: str = "wav", to_format: str = "opus", sample_rate: int = 16000) -> bytes:
        """Transcode audio between formats using ffmpeg."""
        # Use ffmpeg for transcoding via subprocess
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-f", from_format,
            "-i", "pipe:0",
            "-f", to_format,
            "-ar", str(sample_rate),
            "-y",
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate(audio_data)
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg transcoding error: {stderr.decode()}")
        return stdout

    async def record_audio(self, duration: float = 5.0, sample_rate: int = 16000) -> bytes:
        """Record audio from microphone (for testing)."""
        loop = asyncio.get_event_loop()
        audio_data = await loop.run_in_executor(
            None,
            lambda: sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype=np.int16)
        )
        sd.wait()

        # Convert to bytes
        return audio_data.tobytes()

    async def play_audio(self, audio_data: bytes, sample_rate: int = 16000):
        """Play audio data (for testing)."""
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: sd.play(audio_np, samplerate=sample_rate))
        sd.wait()


# Global instance
voice_processor = VoiceProcessor()


__all__ = ["VoiceProcessor", "voice_processor"]