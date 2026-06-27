import requests
import logging
from utils.config import OLLAMA_API_URL, OLLAMA_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """أنت مساعد ذكاء اصطناعي ودود واسمك كلافو.
أنت تعمل كرفيق شخصي يدعم المستخدمين عاطفياً ويساعدهم في محادثاتهم اليومية.
تواصل دائماً بلغة المستخدم، وكن متعاطفاً وإيجابياً ومفيداً.
لديك ذاكرة طويلة الأمد وتتذكر تفاصيل المحادثات السابقة."""


def build_messages(history: list[dict], user_message: str) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for entry in history[-10:]:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


def ask_ollama(user_message: str, history: list[dict] | None = None) -> str:
    if history is None:
        history = []

    messages = build_messages(history, user_message)
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
    }

    api_url = OLLAMA_API_URL.rstrip("/")
    endpoint = f"{api_url}/api/chat"

    try:
        logger.info("إرسال طلب إلى أولاما — النموذج: %s", MODEL_NAME)
        response = requests.post(endpoint, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        reply = data.get("message", {}).get("content", "")
        if not reply:
            reply = data.get("response", "عذراً، لم أتمكن من توليد رد.")
        logger.info("تم استلام الرد من أولاما بنجاح.")
        return reply
    except requests.exceptions.ConnectionError:
        logger.error("تعذّر الاتصال بخادم أولاما على: %s", endpoint)
        return "⚠️ تعذّر الاتصال بنموذج الذكاء الاصطناعي. تأكد من تشغيل خادم أولاما."
    except requests.exceptions.Timeout:
        logger.error("انتهت مهلة الاتصال بأولاما.")
        return "⚠️ استغرق الرد وقتاً طويلاً. يرجى المحاولة مجدداً."
    except requests.exceptions.HTTPError as e:
        logger.error("خطأ HTTP من أولاما: %s", e)
        return f"⚠️ خطأ في الخادم: {e.response.status_code}"
    except Exception as e:
        logger.exception("خطأ غير متوقع أثناء الاتصال بأولاما: %s", e)
        return "⚠️ حدث خطأ غير متوقع. يرجى المحاولة مجدداً."
