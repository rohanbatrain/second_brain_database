"""Celery tasks for voice processing.

Async tasks for:
- Voice transcription with Deepgram
- TTS generation
- Voice analytics
"""
from typing import Dict, Any, Optional
import base64

from .celery_app import celery_app
from ..managers.logging_manager import get_logger
from ..database import db_manager

try:
    from deepgram import DeepgramClient, PrerecordedOptions
except ImportError:
    # Handle older deepgram SDK versions
    from deepgram import DeepgramClient
    PrerecordedOptions = None

logger = get_logger(prefix="[VoiceTasks]")


@celery_app.task(name="transcribe_audio_deepgram", bind=True, max_retries=3)
def transcribe_audio_deepgram(
    self,
    audio_data: str,  # Base64 encoded
    user_id: str,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Transcribe audio using Deepgram.
    
    Args:
        audio_data: Base64 encoded audio
        user_id: User ID for tracking
        options: Deepgram options
        
    Returns:
        Transcription result
    """
    try:
        from ..config import settings
        
        # Decode audio
        audio_bytes = base64.b64decode(audio_data)
        
        # Initialize Deepgram client
        deepgram = DeepgramClient(settings.DEEPGRAM_API_KEY)
        
        # Configure options
        default_options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            punctuate=True,
            paragraphs=True,
            utterances=True,
            diarize=True,
        )
        
        if options:
            for key, value in options.items():
                setattr(default_options, key, value)
        
        # Transcribe
        response = deepgram.listen.prerecorded.v("1").transcribe_file(
            {"buffer": audio_bytes},
            default_options
        )
        
        # Extract transcript
        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        confidence = response["results"]["channels"][0]["alternatives"][0]["confidence"]
        
        result = {
            "transcript": transcript,
            "confidence": confidence,
            "user_id": user_id,
            "model": "nova-2",
            "duration": response["metadata"]["duration"],
            "words": response["results"]["channels"][0]["alternatives"][0].get("words", [])
        }
        
        # Store in MongoDB
        db_manager.get_collection("voice_transcriptions").insert_one({
            **result,
            "created_at": datetime.now(timezone.utc)
        })
        
        logger.info(
            f"Transcribed audio for user {user_id}, "
            f"confidence: {confidence:.2f}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@celery_app.task(name="generate_tts_deepgram")
def generate_tts_deepgram(
    text: str,
    user_id: str,
    voice: str = "aura-asteria-en"
) -> Dict[str, Any]:
    """Generate speech from text using Deepgram TTS.
    
    Args:
        text: Text to synthesize
        user_id: User ID
        voice: Voice model
        
    Returns:
        Audio data (base64 encoded)
    """
    try:
        from ..config import settings
        
        deepgram = DeepgramClient(settings.DEEPGRAM_API_KEY)
        
        # Generate speech
        response = deepgram.speak.v("1").save(
            text,
            {
                "model": voice,
                "encoding": "linear16",
                "sample_rate": 24000
            }
        )
        
        # Encode audio to base64
        audio_b64 = base64.b64encode(response).decode()
        
        result = {
            "audio": audio_b64,
            "text": text,
            "voice": voice,
            "user_id": user_id,
            "format": "linear16",
            "sample_rate": 24000
        }
        
        logger.info(f"Generated TTS for user {user_id}, {len(text)} chars")
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating TTS: {e}", exc_info=True)
        return {"error": str(e)}


@celery_app.task(name="analyze_voice_sentiment")
def analyze_voice_sentiment(transcription_id: str) -> Dict[str, Any]:
    """Analyze sentiment from voice transcription.
    
    Args:
        transcription_id: MongoDB transcription ID
        
    Returns:
        Sentiment analysis
    """
    try:
        from bson import ObjectId
        
        # Get transcription
        collection = db_manager.get_collection("voice_transcriptions")
        transcription = collection.find_one({"_id": ObjectId(transcription_id)})
        
        if not transcription:
            return {"error": "Transcription not found"}
        
        # Sentiment analysis disabled - LangChain orchestrator removed
        logger.info(f"Sentiment analysis requested but LangChain is disabled for transcription {transcription_id}")
        
        sentiment = {
            "transcription_id": transcription_id,
            "sentiment": "neutral",  # Placeholder - analysis disabled
            "confidence": 0.0,
            "analyzed_at": datetime.now(timezone.utc),
            "note": "Sentiment analysis disabled - LangChain system removed"
        }
        
        # Store sentiment
        collection.update_one(
            {"_id": ObjectId(transcription_id)},
            {"$set": {"sentiment": sentiment}}
        )
        
        logger.info(f"Analyzed sentiment for transcription {transcription_id}")
        
        return sentiment
        
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}", exc_info=True)
        return {"error": str(e)}
