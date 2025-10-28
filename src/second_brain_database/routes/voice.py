"""Voice integration endpoints for LiveKit + Ollama.

This router provides endpoints for:
- Generating LiveKit access tokens
- Calling Ollama for text responses
- Speech-to-text processing
- Text-to-speech synthesis
- Full voice agent pipeline (audio in -> text -> LLM -> TTS -> audio out)

All endpoints require authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional

from second_brain_database.config import settings
from second_brain_database.integrations.ollama import OllamaClient
from second_brain_database.integrations.livekit import create_access_token
from second_brain_database.integrations.voice_processor import voice_processor
from second_brain_database.routes.auth.services.auth.login import get_current_user

router = APIRouter(prefix="/voice", tags=["voice"])


class TokenRequest(BaseModel):
    room: Optional[str] = None
    identity: Optional[str] = None
    ttl_seconds: Optional[int] = 3600
    can_publish: bool = True
    can_subscribe: bool = True


class PromptRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    temperature: float = 0.7


# Create a long-lived Ollama client instance for reuse
_ollama_client: Optional[OllamaClient] = None


def _get_ollama_client() -> OllamaClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(base_url=settings.OLLAMA_HOST, model=settings.OLLAMA_MODEL)
    return _ollama_client


@router.post("/token")
async def get_livekit_token(req: TokenRequest, current_user: dict = Depends(get_current_user)):
    # Ensure API key/secret configured
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise HTTPException(status_code=503, detail="LiveKit integration not configured on server")

    identity = req.identity or (str(current_user.get("_id")) if current_user else "anon")
    token = create_access_token(
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET.get_secret_value() if settings.LIVEKIT_API_SECRET else "",
        identity=identity,
        room=req.room,
        ttl_seconds=req.ttl_seconds or 3600,
        can_publish=req.can_publish,
        can_subscribe=req.can_subscribe,
    )

    return {"token": token, "livekit_url": settings.LIVEKIT_URL}


@router.post("/ollama")
async def call_ollama(req: PromptRequest, current_user: dict = Depends(get_current_user)):
    client = _get_ollama_client()
    try:
        text = await client.generate(req.prompt, model=req.model, temperature=req.temperature)
        return {"result": text}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {e}")


@router.post("/stt")
async def speech_to_text(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if not file.filename.lower().endswith(('.wav', '.mp3', '.flac')):
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    audio_data = await file.read()
    try:
        text = await voice_processor.speech_to_text(audio_data)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT processing failed: {e}")


@router.post("/tts")
async def text_to_speech(req: PromptRequest, current_user: dict = Depends(get_current_user)):
    try:
        audio_bytes = await voice_processor.text_to_speech(req.prompt)
        import base64
        encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
        return {"audio": encoded_audio, "content_type": "audio/wav"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS processing failed: {e}")


@router.post("/agent")
async def voice_agent(file: UploadFile = File(...), model: Optional[str] = None, temperature: float = 0.7, current_user: dict = Depends(get_current_user)):
    """Full voice agent pipeline: STT -> Ollama -> TTS."""
    if not file.filename.lower().endswith(('.wav', '.mp3', '.flac')):
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    audio_data = await file.read()

    try:
        # STT
        text_input = await voice_processor.speech_to_text(audio_data)

        # LLM
        client = _get_ollama_client()
        text_output = await client.generate(text_input, model=model, temperature=temperature)

        # TTS
        audio_output = await voice_processor.text_to_speech(text_output)
        import base64
        encoded_audio = base64.b64encode(audio_output).decode('utf-8')

        return {
            "input_text": text_input,
            "output_text": text_output,
            "audio": encoded_audio,
            "content_type": "audio/wav"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice agent processing failed: {e}")
