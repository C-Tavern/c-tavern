"""
تحويل النص إلى صوت — مجاني تماماً عبر edge-tts
يستخدم محرك Microsoft Edge TTS بدون أي مفتاح API.
"""

import io
import asyncio
import logging
import tempfile
import os
import edge_tts

logger = logging.getLogger(__name__)

VOICES = {
    "ar": "ar-SA-HamedNeural",
    "ar-female": "ar-SA-ZariyahNeural",
    "en": "en-US-AriaNeural",
    "default": "ar-SA-HamedNeural",
}


async def _synthesize(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice)
    audio_chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
    return b"".join(audio_chunks)


def text_to_speech(text: str, voice_key: str = "ar") -> io.BytesIO | None:
    voice = VOICES.get(voice_key, VOICES["default"])
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
    return {
        "ar — عربي (ذكر)": VOICES["ar"],
        "ar-female — عربي (أنثى)": VOICES["ar-female"],
        "en — إنجليزي": VOICES["en"],
    }
