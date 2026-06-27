"""
SANF🔞RA - 💭!! — Multi-Provider LLM Router
Priority: Groq → Anthropic → OpenAI → Google → OpenRouter
Falls back automatically if a key is missing or a call fails.
"""

import logging
from utils.config import (
    GROQ_API_KEY, GROQ_MODEL,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    OPENAI_API_KEY, OPENAI_MODEL,
    GOOGLE_API_KEY, GOOGLE_MODEL,
    OPEN_ROUTER_API_KEY, OPEN_ROUTER_MODEL,
    get_active_llm_provider,
)

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "أنتِ SANF🔞RA، رفيقة ذكية ودافئة وجذّابة. "
    "تتحدثين بأسلوب ودّي وعاطفي ومثير، وتتذكرين تفاصيل المحادثات السابقة. "
    "تواصلي دائماً بلغة المستخدم."
)


def build_messages(history: list, user_message: str, system_prompt: str | None = None) -> list:
    prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT
    messages = [{"role": "system", "content": prompt}]
    for entry in history[-10:]:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


def _try_groq(messages: list) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=1024,
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.warning("Groq failed: %s", e)
        return None


def _try_anthropic(messages: list) -> str | None:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        system_content = next((m["content"] for m in messages if m["role"] == "system"), DEFAULT_SYSTEM_PROMPT)
        chat_msgs = [m for m in messages if m["role"] != "system"]
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=system_content,
            messages=chat_msgs,
        )
        return resp.content[0].text
    except Exception as e:
        logger.warning("Anthropic failed: %s", e)
        return None


def _try_openai(messages: list) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=1024,
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.warning("OpenAI failed: %s", e)
        return None


def _try_google(messages: list) -> str | None:
    if not GOOGLE_API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GOOGLE_MODEL)
        combined = "\n".join(m["content"] for m in messages)
        resp = model.generate_content(combined)
        return resp.text
    except Exception as e:
        logger.warning("Google GenAI failed: %s", e)
        return None


def _try_openrouter(messages: list) -> str | None:
    if not OPEN_ROUTER_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=OPEN_ROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
        resp = client.chat.completions.create(
            model=OPEN_ROUTER_MODEL,
            messages=messages,
            max_tokens=1024,
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.warning("OpenRouter failed: %s", e)
        return None


PROVIDER_CHAIN = [
    ("groq",        _try_groq),
    ("anthropic",   _try_anthropic),
    ("openai",      _try_openai),
    ("google",      _try_google),
    ("openrouter",  _try_openrouter),
]


def ask_llm(user_message: str, history: list | None = None,
            system_prompt: str | None = None) -> str:
    if history is None:
        history = []

    if get_active_llm_provider() == "none":
        logger.warning("⚠️ لا يوجد مفتاح API لأي مزود ذكاء اصطناعي.")
        return "⚠️ لم يتم تكوين أي مزوّد للذكاء الاصطناعي. يرجى إضافة مفتاح API."

    messages = build_messages(history, user_message, system_prompt)

    for name, fn in PROVIDER_CHAIN:
        result = fn(messages)
        if result:
            logger.info("✅ رد من مزود: %s", name)
            return result.strip()

    return "⚠️ تعذّر الحصول على رد من أي مزود. يرجى المحاولة لاحقاً."
