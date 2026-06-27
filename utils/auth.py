"""
نظام المصادقة — لوحة تحكم كلافو
يحمي لوحة التحكم بكلمة مرور بسيطة.
"""

import functools
import logging
from flask import session, redirect, url_for, request, jsonify
from utils.config import ADMIN_USERNAME, ADMIN_PASSWORD

logger = logging.getLogger(__name__)


def is_authenticated() -> bool:
    return session.get("clavo_auth") is True


def login(username: str, password: str) -> bool:
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        logger.warning("⚠️  بيانات المشرف غير محددة — تسجيل الدخول مفتوح.")
        return True
    ok = username == ADMIN_USERNAME and password == ADMIN_PASSWORD
    if ok:
        session["clavo_auth"] = True
        session.permanent = True
        logger.info("✅ تسجيل دخول ناجح.")
    else:
        logger.warning("❌ محاولة دخول فاشلة للمستخدم: %s", username)
    return ok


def logout() -> None:
    session.pop("clavo_auth", None)


def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not ADMIN_USERNAME:
            return f(*args, **kwargs)
        if not is_authenticated():
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"خطأ": "غير مصرح. سجّل الدخول أولاً."}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated
