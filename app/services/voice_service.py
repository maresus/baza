"""
Voice Service - Glasovna komunikacija z Whisper transkripcijo

FUNKCIONALNOST:
1. Voice transcription - OpenAI Whisper API
2. Audio file handling - upload, conversion
3. Slovenian language support
4. Integration with chat flow

UPORABA:
    from app.services.voice_service import VoiceService

    voice = VoiceService()
    text = await voice.transcribe_audio(audio_file)
"""

import os
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, BinaryIO
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Supported audio formats
SUPPORTED_FORMATS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg"}
MAX_FILE_SIZE_MB = 25  # Whisper limit

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WHISPER_MODEL = "whisper-1"
DEFAULT_LANGUAGE = "sl"  # Slovenščina


class VoiceServiceError(Exception):
    """Custom exception for voice service errors."""
    pass


class VoiceService:
    """Service za transkripcijo glasovnih sporočil."""

    def __init__(self):
        self.openai_client = None
        self._init_client()

    def _init_client(self) -> None:
        """Inicializira OpenAI client."""
        if not OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set - voice transcription will not work")
            return

        try:
            from openai import OpenAI
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI client initialized for Whisper")
        except ImportError:
            logger.warning("openai package not installed - run: pip install openai")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")

    def is_available(self) -> bool:
        """Preveri ali je voice service na voljo."""
        return self.openai_client is not None

    def validate_audio_file(
        self,
        filename: str,
        file_size_bytes: int
    ) -> Dict[str, Any]:
        """
        Validira audio datoteko.

        Args:
            filename: Ime datoteke
            file_size_bytes: Velikost v bajtih

        Returns:
            {"valid": bool, "error": str or None}
        """
        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            return {
                "valid": False,
                "error": f"Nepodprt format. Podprti: {', '.join(SUPPORTED_FORMATS)}"
            }

        # Check file size
        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            return {
                "valid": False,
                "error": f"Datoteka prevelika. Maksimum: {MAX_FILE_SIZE_MB} MB"
            }

        return {"valid": True, "error": None}

    async def transcribe_audio(
        self,
        audio_file: BinaryIO,
        filename: str,
        language: str = DEFAULT_LANGUAGE
    ) -> Dict[str, Any]:
        """
        Transkribira audio datoteko v besedilo.

        Args:
            audio_file: Audio datoteka (file-like object)
            filename: Ime datoteke (za določitev formata)
            language: Jezik transkripcije (default: sl)

        Returns:
            {
                "success": bool,
                "text": str or None,
                "language": str,
                "duration_seconds": float or None,
                "error": str or None
            }
        """
        if not self.is_available():
            return {
                "success": False,
                "text": None,
                "error": "Voice service ni na voljo. Prosimo, pišite sporočilo."
            }

        result = {
            "success": False,
            "text": None,
            "language": language,
            "duration_seconds": None,
            "error": None,
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Save to temp file (Whisper API needs a file path)
            ext = Path(filename).suffix.lower()
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(audio_file.read())
                tmp_path = tmp.name

            try:
                # Call Whisper API
                with open(tmp_path, "rb") as audio:
                    response = self.openai_client.audio.transcriptions.create(
                        model=WHISPER_MODEL,
                        file=audio,
                        language=language,
                        response_format="verbose_json"
                    )

                # Parse response
                result["success"] = True
                result["text"] = response.text.strip()
                result["duration_seconds"] = getattr(response, 'duration', None)

                logger.info(f"Transcription successful: {len(result['text'])} chars")

            finally:
                # Clean up temp file
                os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            result["error"] = f"Napaka pri transkripciji: {str(e)}"

        return result

    async def transcribe_from_path(
        self,
        file_path: str,
        language: str = DEFAULT_LANGUAGE
    ) -> Dict[str, Any]:
        """
        Transkribira audio iz poti na disku.

        Args:
            file_path: Pot do audio datoteke
            language: Jezik transkripcije

        Returns:
            Rezultat transkripcije
        """
        if not os.path.exists(file_path):
            return {
                "success": False,
                "text": None,
                "error": "Datoteka ne obstaja"
            }

        filename = os.path.basename(file_path)

        # Validate
        file_size = os.path.getsize(file_path)
        validation = self.validate_audio_file(filename, file_size)
        if not validation["valid"]:
            return {
                "success": False,
                "text": None,
                "error": validation["error"]
            }

        with open(file_path, "rb") as f:
            return await self.transcribe_audio(f, filename, language)

    async def transcribe_from_bytes(
        self,
        audio_bytes: bytes,
        filename: str,
        language: str = DEFAULT_LANGUAGE
    ) -> Dict[str, Any]:
        """
        Transkribira audio iz bajtov.

        Args:
            audio_bytes: Audio podatki
            filename: Ime datoteke (za format)
            language: Jezik transkripcije

        Returns:
            Rezultat transkripcije
        """
        import io

        # Validate
        validation = self.validate_audio_file(filename, len(audio_bytes))
        if not validation["valid"]:
            return {
                "success": False,
                "text": None,
                "error": validation["error"]
            }

        audio_file = io.BytesIO(audio_bytes)
        return await self.transcribe_audio(audio_file, filename, language)


# ================================================================
# FASTAPI ENDPOINTS (za integracijo v router)
# ================================================================

from fastapi import UploadFile, File, HTTPException


async def handle_voice_upload(
    file: UploadFile,
    session_id: str = None
) -> Dict[str, Any]:
    """
    Handler za voice upload endpoint.

    Args:
        file: Naložena audio datoteka
        session_id: ID seje (opcijsko)

    Returns:
        Rezultat transkripcije + metadata
    """
    voice_service = get_voice_service()

    if not voice_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Voice service ni na voljo"
        )

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Manjka ime datoteke"
        )

    # Read content
    content = await file.read()

    # Validate
    validation = voice_service.validate_audio_file(file.filename, len(content))
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=validation["error"]
        )

    # Transcribe
    result = await voice_service.transcribe_from_bytes(
        content,
        file.filename
    )

    # Add session info
    result["session_id"] = session_id
    result["filename"] = file.filename
    result["file_size_bytes"] = len(content)

    return result


# ================================================================
# TEXT-TO-SPEECH (Optional - za prihodnost)
# ================================================================

async def text_to_speech(
    text: str,
    voice: str = "alloy"
) -> Optional[bytes]:
    """
    Pretvori besedilo v govor (TTS).

    Args:
        text: Besedilo za pretvorbo
        voice: Glas (alloy, echo, fable, onyx, nova, shimmer)

    Returns:
        Audio bytes (MP3) ali None če napaka
    """
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set - TTS not available")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )

        return response.content

    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


# Singleton instance
_voice_service = None


def get_voice_service() -> VoiceService:
    """Vrne singleton instance."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
