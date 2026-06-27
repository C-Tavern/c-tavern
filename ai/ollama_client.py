import requests
import logging
from utils.config import OLLAMA_API_URL, OLLAMA_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """أنت كلافو، رفيق ذكي ودافئ.
تتحدث بأسلوب ودي وعاطفي وإيجابي، وتتذكر تفاصيل المحادثات السابقة.
تواصل دائماً بلغة المستخدم."""


def build_messages(history: list[dict], user_message: str,
                   system_prompt: str | None = None) -> list[dict]:
    prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT
    messages = [{"role": "system", "content": prompt}]
    for entry in history[-10:]:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


def ask_ollama(user_message: str, history: list[dict] | None = None,
               system_prompt: str | None = None) -> str:
    if history is None:
        history = []

    messages = build_messages(history, user_message, system_prompt)
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    payload = {"model": MODEL_NAME, "messages": messages, "stream": False}
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
        logger.exception("خطأ غير متوقع: %s", e)
        return "⚠️ حدث خطأ غير متوقع. يرجى المحاولة مجدداً."
