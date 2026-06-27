"""
كلافو — رفيقك الذكي
نقطة دخول التطبيق الرئيسية.

يشغّل هذا الملف:
- خادم Flask (لوحة التحكم + ربط واتساب) على المنفذ 5000
- بوت تيليغرام في خيط خلفي منفصل
- مراقب الملفات لمزامنة GitHub تلقائياً
"""

import asyncio
import logging
import threading
import signal
import sys
from flask import Flask, request, jsonify, render_template

from utils.config import validate_config, config_summary
from ai.ollama_client import ask_ollama
from bots.telegram_bot import build_telegram_app
from bots.whatsapp_bot import get_whatsapp_blueprint
from sync_github import start_sync_watcher, stop_sync_watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")
app.register_blueprint(get_whatsapp_blueprint())

_chat_histories: dict[str, list[dict]] = {}
_github_observer = None
_telegram_thread = None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(config_summary())


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    session_id = data.get("session_id", "web-default")

    if not message:
        return jsonify({"خطأ": "الرسالة فارغة."}), 400

    history = _chat_histories.setdefault(session_id, [])
    reply = ask_ollama(message, history)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    if len(history) > 40:
        _chat_histories[session_id] = history[-40:]

    return jsonify({"reply": reply, "session_id": session_id})


@app.route("/api/chat/clear", methods=["POST"])
def api_chat_clear():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "web-default")
    _chat_histories.pop(session_id, None)
    return jsonify({"حالة": "تم مسح سجل المحادثة."})


def run_telegram_bot():
    """تشغيل بوت تيليغرام في خيط مستقل مع حلقة أحداث خاصة."""
    telegram_app = build_telegram_app()
    if not telegram_app:
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        async with telegram_app:
            logger.info("🚀 بدء تشغيل بوت تيليغرام (polling)...")
            await telegram_app.start()
            await telegram_app.updater.start_polling(drop_pending_updates=True)
            stop_event = asyncio.Event()
            try:
                await stop_event.wait()
            except asyncio.CancelledError:
                pass
            finally:
                await telegram_app.updater.stop()
                await telegram_app.stop()

    try:
        loop.run_until_complete(_run())
    except Exception as e:
        logger.error("خطأ في بوت تيليغرام: %s", e)
    finally:
        loop.close()


def start_telegram_background():
    thread = threading.Thread(target=run_telegram_bot, name="telegram-bot", daemon=True)
    thread.start()
    logger.info("✅ تم تشغيل بوت تيليغرام في الخلفية.")
    return thread


def handle_shutdown(signum, frame):
    logger.info("إشارة إيقاف مستلمة — جاري إيقاف التطبيق...")
    stop_sync_watcher(_github_observer)
    sys.exit(0)


def main():
    global _github_observer, _telegram_thread

    logger.info("=" * 55)
    logger.info("🤖  كلافو — رفيقك الذكي | تشغيل التطبيق")
    logger.info("=" * 55)

    missing = validate_config()
    if missing:
        logger.warning("⚠️  متغيرات البيئة التالية غير محددة: %s", ", ".join(missing))

    for key, val in config_summary().items():
        logger.info("  %-30s %s", key + ":", val)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    _github_observer = start_sync_watcher(".")
    _telegram_thread = start_telegram_background()

    logger.info("=" * 55)
    logger.info("🌐  خادم الويب يعمل على: http://0.0.0.0:5000")
    logger.info("=" * 55)

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
