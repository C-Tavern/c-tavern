"""
توليد الصور — مجاني تماماً عبر Pollinations.AI
لا يتطلب مفتاح API أو اشتراكاً مدفوعاً.
"""

import io
import random
import logging
import urllib.parse
import requests

logger = logging.getLogger(__name__)

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
TIMEOUT = 60


def generate_image(prompt: str, width: int = 512, height: int = 512) -> io.BytesIO | None:
    arabic_prefix = "صورة عالية الجودة: "
    full_prompt = f"{arabic_prefix}{prompt}, high quality, detailed, artistic"
    encoded = urllib.parse.quote(full_prompt)
    seed = random.randint(1, 999999)

    url = (
        f"{POLLINATIONS_BASE}/{encoded}"
        f"?width={width}&height={height}&seed={seed}&nologo=true&enhance=true"
    )

    logger.info("🎨 توليد صورة عبر Pollinations.AI — prompt: %s...", prompt[:40])
    try:
        resp = requests.get(url, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type:
            logger.error("استجابة غير متوقعة من Pollinations: %s", content_type)
            return None
        buf = io.BytesIO(resp.content)
        buf.seek(0)
        logger.info("✅ تم توليد الصورة بنجاح (%d bytes)", len(resp.content))
        return buf
    except requests.exceptions.Timeout:
        logger.error("انتهت مهلة توليد الصورة.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error("خطأ في توليد الصورة: %s", e)
        return None


def get_image_url(prompt: str, width: int = 512, height: int = 512) -> str:
    encoded = urllib.parse.quote(f"{prompt}, high quality, detailed")
    seed = random.randint(1, 999999)
    return (
        f"{POLLINATIONS_BASE}/{encoded}"
        f"?width={width}&height={height}&seed={seed}&nologo=true"
    )
