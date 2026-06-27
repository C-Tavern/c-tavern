import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str            = os.getenv("GROQ_API_KEY", "")
ANTHROPIC_API_KEY: str       = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY: str          = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY: str          = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY", "")
OPEN_ROUTER_API_KEY: str     = os.getenv("OPEN_ROUTER_API_KEY", "")

GROQ_MODEL: str              = os.getenv("GROQ_MODEL", "llama3-8b-8192")
ANTHROPIC_MODEL: str         = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
OPENAI_MODEL: str            = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GOOGLE_MODEL: str            = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
OPEN_ROUTER_MODEL: str       = os.getenv("OPEN_ROUTER_MODEL", "openai/gpt-4o-mini")

TELEGRAM_TOKEN: str          = os.getenv("TELEGRAM_TOKEN", "")
GITHUB_TOKEN: str            = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO: str             = os.getenv("GITHUB_REPO", "")
ADMIN_USERNAME: str          = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD: str          = os.getenv("ADMIN_PASSWORD", "")
SECRET_KEY: str              = os.getenv("SECRET_KEY", os.urandom(32).hex())

BOT_NAME: str = "SANF🔞RA - 💭!!"

IMAGE_GEN_PROVIDER: str      = os.getenv("IMAGE_GEN_PROVIDER", "pollinations")
TTS_PROVIDER: str            = os.getenv("TTS_PROVIDER", "edge-tts")
TTS_VOICE: str               = os.getenv("TTS_VOICE", "ar-EG-SalmaNeural")

WELCOME_IMAGE_URL: str       = "https://i.postimg.cc/XJpmFGVH/file-00000000c9ec71f48e9f0ac5c06c1c4d.png"
DASHBOARD_BG_URL: str        = "https://i.postimg.cc/XNBtYC10/file-0000000084487246995745f704ea604f.png"


def get_active_llm_provider() -> str:
    if GROQ_API_KEY:
        return "groq"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if OPENAI_API_KEY:
        return "openai"
    if GOOGLE_API_KEY:
        return "google"
    if OPEN_ROUTER_API_KEY:
        return "openrouter"
    return "none"


def validate_config() -> list:
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if get_active_llm_provider() == "none":
        missing.append("(no LLM API key — need one of: GROQ/ANTHROPIC/OPENAI/GOOGLE/OPEN_ROUTER)")
    return missing


def config_summary() -> dict:
    provider = get_active_llm_provider()
    return {
        "مزود_الذكاء_الاصطناعي": provider,
        "تيليغرام_مُفعّل": bool(TELEGRAM_TOKEN),
        "مزامنة_جيتهاب_مُفعّلة": bool(GITHUB_TOKEN and GITHUB_REPO),
        "لوحة_التحكم_محمية": bool(ADMIN_USERNAME and ADMIN_PASSWORD),
        "مزود_الصور": IMAGE_GEN_PROVIDER,
        "مزود_الصوت": TTS_PROVIDER,
    }
