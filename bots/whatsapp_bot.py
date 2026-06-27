import os
import io
import json
import uuid
import hmac
import hashlib
import logging
import threading
import time
import qrcode
from flask import Blueprint, request, jsonify, send_file, abort
from ai.ollama_client import ask_ollama

logger = logging.getLogger(__name__)

whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/whatsapp")

session_store: dict[str, dict] = {}
user_histories: dict[str, list[dict]] = {}
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
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#6d28d9", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


@whatsapp_bp.route("/qr", methods=["GET"])
def get_qr():
    global _qr_session_id
    if _session_connected:
        return jsonify({
            "حالة": "متصل",
            "رسالة": "الجلسة نشطة بالفعل.",
            "هاتف": _session_phone,
        })
    img_buf = generate_qr_image(_qr_session_id)
    return send_file(img_buf, mimetype="image/png")


@whatsapp_bp.route("/qr/status", methods=["GET"])
def qr_status():
    return jsonify({
        "متصل": _session_connected,
        "معرف_الجلسة": _qr_session_id,
        "هاتف": _session_phone,
    })


@whatsapp_bp.route("/connect", methods=["POST"])
def connect_session():
    global _session_connected, _session_phone, _qr_session_id
    data = request.get_json(silent=True) or {}
    provided_id = data.get("session_id", "")
    phone = data.get("phone", "")

    expected = _generate_qr_payload(_qr_session_id)
    if provided_id != _qr_session_id:
        abort(403, description="معرّف الجلسة غير صالح.")

    _session_connected = True
    _session_phone = phone
    logger.info("✅ تم ربط جلسة واتساب — الهاتف: %s", phone)

    return jsonify({
        "حالة": "تم الاتصال بنجاح",
        "هاتف": phone,
        "رسالة": "مرحباً! تم ربط واتساب بكلافو. ابدأ محادثتك الآن. 🎉",
    })


@whatsapp_bp.route("/disconnect", methods=["POST"])
def disconnect_session():
    global _session_connected, _session_phone, _qr_session_id
    _session_connected = False
    _session_phone = ""
    _qr_session_id = str(uuid.uuid4())
    logger.info("تم قطع اتصال واتساب وإعادة توليد رمز QR.")
    return jsonify({"حالة": "تم قطع الاتصال", "رسالة": "تم إنهاء الجلسة."})


@whatsapp_bp.route("/webhook", methods=["POST"])
def webhook():
    if not _session_connected:
        return jsonify({"خطأ": "لا توجد جلسة نشطة."}), 403

    data = request.get_json(silent=True) or {}
    sender = data.get("من", data.get("from", "مجهول"))
    message_text = data.get("رسالة", data.get("message", "")).strip()

    if not message_text:
        return jsonify({"خطأ": "الرسالة فارغة."}), 400

    logger.info("رسالة واتساب من %s: %s", sender, message_text[:60])

    history = user_histories.setdefault(sender, [])
    reply = ask_ollama(message_text, history)

    history.append({"role": "user", "content": message_text})
    history.append({"role": "assistant", "content": reply})
    if len(history) > 40:
        user_histories[sender] = history[-40:]

    return jsonify({"رد": reply, "إلى": sender})


@whatsapp_bp.route("/send", methods=["POST"])
def send_message():
    data = request.get_json(silent=True) or {}
    to = data.get("إلى", data.get("to", ""))
    text = data.get("رسالة", data.get("message", ""))
    if not to or not text:
        return jsonify({"خطأ": "يجب تحديد المستلم والرسالة."}), 400
    logger.info("إرسال رسالة واتساب إلى %s", to)
    return jsonify({
        "حالة": "تم الإرسال",
        "إلى": to,
        "رسالة": text,
    })


def get_whatsapp_blueprint() -> Blueprint:
    logger.info("✅ تم إعداد بوت واتساب بنجاح.")
    return whatsapp_bp
