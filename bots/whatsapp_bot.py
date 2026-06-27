import io
import uuid
import hmac
import hashlib
import logging
import qrcode
from flask import Blueprint, request, jsonify, send_file, abort
from ai.ollama_client import ask_ollama
from db.memory import get_history, save_message, clear_history, get_user_summary
from db.personas import get_active_persona, set_active_persona, list_personas, get_persona_by_name

logger = logging.getLogger(__name__)

PLATFORM = "whatsapp"
whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/whatsapp")

_qr_session_id: str = str(uuid.uuid4())
_session_connected: bool = False
_session_phone: str = ""


def _generate_qr_payload(session_id: str) -> str:
    token = hmac.new(
        session_id.encode(), b"clavo-whatsapp-session", hashlib.sha256
    ).hexdigest()[:16]
    return f"clavo-session:{session_id}:{token}"


def generate_qr_image(session_id: str) -> io.BytesIO:
    payload = _generate_qr_payload(session_id)
    qr = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#6d28d9", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@whatsapp_bp.route("/qr", methods=["GET"])
def get_qr():
    if _session_connected:
        return jsonify({"حالة": "متصل", "هاتف": _session_phone})
    return send_file(generate_qr_image(_qr_session_id), mimetype="image/png")


@whatsapp_bp.route("/qr/status", methods=["GET"])
def qr_status():
    return jsonify({"متصل": _session_connected, "معرف_الجلسة": _qr_session_id, "هاتف": _session_phone})


@whatsapp_bp.route("/connect", methods=["POST"])
def connect_session():
    global _session_connected, _session_phone, _qr_session_id
    data = request.get_json(silent=True) or {}
    if data.get("session_id", "") != _qr_session_id:
        abort(403, description="معرّف الجلسة غير صالح.")
    _session_connected = True
    _session_phone = data.get("phone", "")
    logger.info("✅ تم ربط جلسة واتساب — الهاتف: %s", _session_phone)
    return jsonify({"حالة": "تم الاتصال", "هاتف": _session_phone})


@whatsapp_bp.route("/disconnect", methods=["POST"])
def disconnect_session():
    global _session_connected, _session_phone, _qr_session_id
    _session_connected = False
    _session_phone = ""
    _qr_session_id = str(uuid.uuid4())
    return jsonify({"حالة": "تم قطع الاتصال"})


@whatsapp_bp.route("/webhook", methods=["POST"])
def webhook():
    if not _session_connected:
        return jsonify({"خطأ": "لا توجد جلسة نشطة."}), 403
    data = request.get_json(silent=True) or {}
    sender = data.get("من", data.get("from", "مجهول"))
    message_text = data.get("رسالة", data.get("message", "")).strip()
    if not message_text:
        return jsonify({"خطأ": "الرسالة فارغة."}), 400

    if message_text.startswith("/persona "):
        name = message_text[9:].strip()
        p = get_persona_by_name(name)
        if p:
            set_active_persona(PLATFORM, sender, p["id"])
            return jsonify({"رد": f"✅ تم التبديل إلى {p['avatar']} {p['name']}"})
        else:
            personas = list_personas()
            names = ", ".join(f"{x['name']}" for x in personas)
            return jsonify({"رد": f"❌ الشخصية غير موجودة. المتاح: {names}"})

    if message_text.lower() == "/personas":
        personas = list_personas()
        active = get_active_persona(PLATFORM, sender)
        lines = [f"🎭 الشخصيات المتاحة:\n"]
        for p in personas:
            mark = "✅ " if p["id"] == active.get("id") else ""
            lines.append(f"{mark}{p['avatar']} {p['name']} — {p['description']}")
        lines.append(f"\nللتبديل: /persona الاسم")
        return jsonify({"رد": "\n".join(lines)})

    logger.info("رسالة واتساب من %s: %s", sender, message_text[:60])
    history = get_history(PLATFORM, sender)
    persona = get_active_persona(PLATFORM, sender)
    reply = ask_ollama(message_text, history, system_prompt=persona.get("system_prompt"))
    save_message(PLATFORM, sender, "user", message_text)
    save_message(PLATFORM, sender, "assistant", reply)
    return jsonify({"رد": reply, "إلى": sender, "شخصية": persona.get("name")})


@whatsapp_bp.route("/send", methods=["POST"])
def send_message():
    data = request.get_json(silent=True) or {}
    to = data.get("إلى", data.get("to", ""))
    text = data.get("رسالة", data.get("message", ""))
    if not to or not text:
        return jsonify({"خطأ": "يجب تحديد المستلم والرسالة."}), 400
    return jsonify({"حالة": "تم الإرسال", "إلى": to})


@whatsapp_bp.route("/user/<user_id>/memory", methods=["GET"])
def user_memory(user_id: str):
    summary = get_user_summary(PLATFORM, user_id)
    return jsonify(summary) if summary else (jsonify({"رسالة": "لا بيانات."}), 404)


@whatsapp_bp.route("/user/<user_id>/clear", methods=["POST"])
def user_clear(user_id: str):
    deleted = clear_history(PLATFORM, user_id)
    return jsonify({"حالة": "تم المسح", "عدد_المحذوف": deleted})


def get_whatsapp_blueprint() -> Blueprint:
    logger.info("✅ تم إعداد بوت واتساب بنجاح.")
    return whatsapp_bp
