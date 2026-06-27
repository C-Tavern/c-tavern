"""
تحويل النص إلى صوت — مجاني تماماً عبر edge-tts
صوت أنثوي عربي تعبيري بدون أي مفتاح API.
"""

import io
import asyncio
import logging
import edge_tts
from utils.config import TTS_VOICE

logger = logging.getLogger(__name__)

DEFAULT_VOICE = TTS_VOICE or "ar-EG-SalmaNeural"

VOICES = {
    "ar":          "ar-EG-SalmaNeural",
    "ar-female":   "ar-EG-SalmaNeural",
    "ar-sy":       "ar-SY-AmanyNeural",
    "ar-male":     "ar-SA-HamedNeural",
    "en":          "en-US-AriaNeural",
    "default":     DEFAULT_VOICE,
}


async def _synthesize(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def text_to_speech(text: str, voice_key: str = "default") -> io.BytesIO | None:
    voice = VOICES.get(voice_key, DEFAULT_VOICE)
    if len(text) > 1000:
        text = text[:1000] + "..."

    logger.info("🔊 توليد صوت عبر edge-tts — الصوت: %s", voice)
    try:
        loop = asyncio.new_event_loop()
        audio_bytes = loop.run_until_complete(_synthesize(text, voice))
        loop.close()

        if not audio_bytes:
            logger.error("لم يتم توليد أي بيانات صوتية.")
            return None

        buf = io.BytesIO(audio_bytes)
        buf.name = "voice.mp3"
        buf.seek(0)
        logger.info("✅ تم توليد الصوت بنجاح (%d bytes)", len(audio_bytes))
        return buf
    except Exception as e:
        logger.error("خطأ في توليد الصوت: %s", e)
        return None


def list_voices() -> dict:
    return {k: v for k, v in VOICES.items()}
