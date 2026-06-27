"""
SANF🔞RA - 💭!! — Main Application Entry Point
Flask web dashboard + Telegram + WhatsApp + GitHub sync.
"""

import asyncio
import logging
import threading
import signal
import sys
from datetime import timedelta
import os as _os
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_file, Response

from utils.config import validate_config, config_summary, SECRET_KEY, BOT_NAME, DASHBOARD_BG_URL
from utils.auth import require_auth, login, logout, is_authenticated
from ai.llm_router import ask_llm
from ai.image_gen import get_image_url
from ai.tts import text_to_speech, list_voices
from utils.push import send_push, broadcast_push, is_push_enabled, VAPID_PUBLIC_KEY
from bots.telegram_bot import build_telegram_app
from bots.whatsapp_bot import get_whatsapp_blueprint
from sync_github import start_sync_watcher, stop_sync_watcher
from db.memory import (
    init_db, get_history, save_message, clear_history, get_stats,
    save_push_subscription, delete_push_subscription,
    delete_push_subscription_by_endpoint, get_all_push_subscriptions,
    get_push_subscription_count, mark_push_notified,
)
from db.personas import (
    init_personas, list_personas, get_active_persona,
    set_active_persona, create_persona, delete_persona,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(days=7)
app.register_blueprint(get_whatsapp_blueprint())

_github_observer = None
_telegram_thread = None
PLATFORM = "web"


@app.route("/sw.js")
def service_worker():
    """Serve the service worker from the root scope so it can control all pages."""
    sw_path = _os.path.join(app.static_folder, "sw.js")
    with open(sw_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(
        content,
        mimetype="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@app.route("/manifest.json")
def manifest():
    """Serve manifest from root for maximum browser compatibility."""
    return send_file(
        _os.path.join(app.static_folder, "manifest.json"),
        mimetype="application/manifest+json",
    )


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if is_authenticated():
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if login(username, password):
            return redirect(url_for("index"))
        error = "❌ اسم المستخدم أو كلمة المرور غير صحيحة."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout_route():
    logout()
    return redirect(url_for("login_page"))


@app.route("/")
@require_auth
def index():
    return render_template("index.html", bg_url=DASHBOARD_BG_URL, bot_name=BOT_NAME)


@app.route("/api/status")
@require_auth
def api_status():
    return jsonify(config_summary())


@app.route("/api/memory/stats")
@require_auth
def api_memory_stats():
    return jsonify(get_stats())


@app.route("/api/personas", methods=["GET"])
@require_auth
def api_personas():
    session_id = session.get("web_session", "web-default")
    active = get_active_persona(PLATFORM, session_id)
    return jsonify({"شخصيات": list_personas(), "النشطة": active})


@app.route("/api/personas/set", methods=["POST"])
@require_auth
def api_set_persona():
    data = request.get_json(silent=True) or {}
    persona_id = data.get("persona_id")
    session_id = session.get("web_session", "web-default")
    if not persona_id:
        return jsonify({"خطأ": "persona_id مطلوب."}), 400
    ok = set_active_persona(PLATFORM, session_id, int(persona_id))
    if not ok:
        return jsonify({"خطأ": "الشخصية غير موجودة."}), 404
    from db.personas import get_persona_by_id
    p = get_persona_by_id(int(persona_id))
    return jsonify({"حالة": "تم التفعيل", "شخصية": p})


@app.route("/api/personas/create", methods=["POST"])
@require_auth
def api_create_persona():
    data = request.get_json(silent=True) or {}
    name   = data.get("name", "").strip()
    desc   = data.get("description", "").strip()
    prompt = data.get("system_prompt", "").strip()
    avatar = data.get("avatar", "✨").strip() or "✨"
    if not name or not prompt:
        return jsonify({"خطأ": "الاسم والتعليمات مطلوبان."}), 400
    p = create_persona(name, desc, prompt, avatar, created_by="web")
    if not p:
        return jsonify({"خطأ": f"اسم «{name}» مستخدم بالفعل."}), 409
    return jsonify({"حالة": "تم الإنشاء", "شخصية": p}), 201


@app.route("/api/personas/<int:persona_id>", methods=["DELETE"])
@require_auth
def api_delete_persona(persona_id: int):
    ok = delete_persona(persona_id, requested_by="web")
    if not ok:
        return jsonify({"خطأ": "لا يمكن حذف الشخصية (افتراضية أو غير موجودة)."}), 400
    return jsonify({"حالة": "تم الحذف"})


@app.route("/api/chat", methods=["POST"])
@require_auth
def api_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    session_id = session.get("web_session", "web-default")
    if "web_session" not in session:
        import uuid
        session["web_session"] = f"web-{uuid.uuid4().hex[:8]}"
        session_id = session["web_session"]
    if not message:
        return jsonify({"خطأ": "الرسالة فارغة."}), 400

    history = get_history(PLATFORM, session_id)
    persona = get_active_persona(PLATFORM, session_id)
    reply = ask_llm(message, history, system_prompt=persona.get("system_prompt"))
    save_message(PLATFORM, session_id, "user", message)
    save_message(PLATFORM, session_id, "assistant", reply)
    return jsonify({"reply": reply, "persona": persona.get("name"), "avatar": persona.get("avatar")})


@app.route("/api/chat/clear", methods=["POST"])
@require_auth
def api_chat_clear():
    session_id = session.get("web_session", "web-default")
    deleted = clear_history(PLATFORM, session_id)
    return jsonify({"حالة": "تم المسح.", "عدد_المحذوف": deleted})


@app.route("/api/image", methods=["POST"])
@require_auth
def api_image():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"خطأ": "الوصف مطلوب."}), 400
    url = get_image_url(prompt)
    return jsonify({"url": url, "prompt": prompt})


@app.route("/api/tts", methods=["POST"])
@require_auth
def api_tts():
    data = request.get_json(silent=True) or {}
    text  = data.get("text", "").strip()
    voice = data.get("voice", "default")
    if not text:
        return jsonify({"خطأ": "النص مطلوب."}), 400
    if len(text) > 1200:
        text = text[:1200]
    audio_buf = text_to_speech(text, voice_key=voice)
    if not audio_buf:
        return jsonify({"خطأ": "فشل توليد الصوت. حاول مجدداً."}), 500
    audio_buf.seek(0)
    return send_file(
        audio_buf,
        mimetype="audio/mpeg",
        as_attachment=False,
        download_name="sanfra-voice.mp3",
    )


@app.route("/api/tts/voices", methods=["GET"])
@require_auth
def api_tts_voices():
    return jsonify(list_voices())


# ── Push Notification Routes ──────────────────────────────────────────────────

@app.route("/api/push/vapid-public-key", methods=["GET"])
@require_auth
def api_push_vapid_key():
    if not is_push_enabled():
        return jsonify({"خطأ": "Push غير مُفعَّل — VAPID_PUBLIC_KEY مطلوب."}), 503
    return jsonify({"publicKey": VAPID_PUBLIC_KEY})


@app.route("/api/push/subscribe", methods=["POST"])
@require_auth
def api_push_subscribe():
    data = request.get_json(silent=True) or {}
    sub  = data.get("subscription", {})
    endpoint = sub.get("endpoint", "")
    keys     = sub.get("keys", {})
    p256dh   = keys.get("p256dh", "")
    auth     = keys.get("auth", "")
    if not endpoint or not p256dh or not auth:
        return jsonify({"خطأ": "بيانات الاشتراك غير مكتملة."}), 400
    sess_id = session.get("web_session", "web-default")
    ua      = request.headers.get("User-Agent", "")[:200]
    ok = save_push_subscription(sess_id, endpoint, p256dh, auth, ua)
    if not ok:
        return jsonify({"خطأ": "فشل حفظ الاشتراك."}), 500
    count = get_push_subscription_count()
    return jsonify({"حالة": "تم الاشتراك", "إجمالي_المشتركين": count}), 201


@app.route("/api/push/unsubscribe", methods=["POST"])
@require_auth
def api_push_unsubscribe():
    sess_id = session.get("web_session", "web-default")
    delete_push_subscription(sess_id)
    return jsonify({"حالة": "تم إلغاء الاشتراك"})


@app.route("/api/push/send", methods=["POST"])
@require_auth
def api_push_send():
    """Admin endpoint: broadcast a push to all or a single session."""
    if not is_push_enabled():
        return jsonify({"خطأ": "Push غير مُفعَّل — VAPID keys مطلوبة."}), 503
    data    = request.get_json(silent=True) or {}
    title   = data.get("title",   "SANFFOURA 🔞")
    body    = data.get("body",    "💋 لديك رسالة جديدة")
    url     = data.get("url",     "/")
    icon    = data.get("icon",    "/static/icons/icon-192x192.png")
    target  = data.get("session_id")          # optional — single target

    subs = get_all_push_subscriptions()
    if not subs:
        return jsonify({"خطأ": "لا يوجد مشتركون."}), 404

    if target:
        subs = [s for s in subs if s["session_id"] == target]
        if not subs:
            return jsonify({"خطأ": "المشترك غير موجود."}), 404

    sent = failed = 0
    expired_endpoints = []
    for sub in subs:
        ok = send_push(sub["subscription_info"], title, body, icon, url)
        if ok:
            sent += 1
            mark_push_notified(sub["session_id"])
        else:
            failed += 1
            expired_endpoints.append(sub["subscription_info"]["endpoint"])

    for ep in expired_endpoints:
        delete_push_subscription_by_endpoint(ep)

    return jsonify({
        "حالة":         "تم الإرسال",
        "مُرسَل":       sent,
        "فاشل":         failed,
        "منتهي_الصلاحية": len(expired_endpoints),
    })


@app.route("/api/push/status", methods=["GET"])
@require_auth
def api_push_status():
    return jsonify({
        "مُفعَّل":         is_push_enabled(),
        "إجمالي_المشتركين": get_push_subscription_count(),
    })


def run_telegram_bot():
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
    logger.info("إشارة إيقاف مستلمة...")
    stop_sync_watcher(_github_observer)
    sys.exit(0)


def initialize_app():
    global _github_observer, _telegram_thread

    logger.info("=" * 55)
    logger.info("🔞  %s | تشغيل التطبيق", BOT_NAME)
    logger.info("=" * 55)

    init_db()
    init_personas()

    missing = validate_config()
    if missing:
        logger.warning("⚠️  متغيرات بيئة غير محددة: %s", ", ".join(missing))

    for key, val in config_summary().items():
        logger.info("  %-34s %s", key + ":", val)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    _github_observer = start_sync_watcher(".")
    _telegram_thread = start_telegram_background()

    logger.info("🌐  خادم الويب: http://0.0.0.0:5000")
    logger.info("=" * 55)


initialize_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
