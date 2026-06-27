import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "")
OLLAMA_API_URL: str = os.getenv("OLLAMA_API_URL", "https://ollama.com")
MODEL_NAME: str = os.getenv("MODEL_NAME", "llama3")
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")

REQUIRED_SECRETS = {
    "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
    "OLLAMA_API_URL": OLLAMA_API_URL,
    "MODEL_NAME": MODEL_NAME,
}


def validate_config() -> list[str]:
    missing = []
    for key, value in REQUIRED_SECRETS.items():
        if not value:
            missing.append(key)
    return missing


def config_summary() -> dict:
    return {
        "نموذج_الذكاء_الاصطناعي": MODEL_NAME,
        "رابط_أولاما": OLLAMA_API_URL,
        "تيليغرام_مُفعّل": bool(TELEGRAM_TOKEN),
        "مزامنة_جيتهاب_مُفعّلة": bool(GITHUB_TOKEN and GITHUB_REPO),
    }
