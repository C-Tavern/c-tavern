"""
SANFFOURA — Web Push Notifications
Sends browser push messages using VAPID + pywebpush.
"""

import json
import logging
import base64
import os
from typing import Optional

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = os.getenv("VAPID_PUBLIC_KEY",  "")
VAPID_SUBJECT     = os.getenv("VAPID_SUBJECT",     "mailto:sanfra@example.com")


def is_push_enabled() -> bool:
    return bool(VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY)


def _pad(b64: str) -> str:
    """Re-add base64 padding stripped during key export."""
    return b64 + "=" * (-len(b64) % 4)


def send_push(subscription_info: dict, title: str, body: str,
              icon: str = "/static/icons/icon-192x192.png",
              url: str = "/") -> bool:
    """
    Send a Web Push notification to a single subscription.

    subscription_info format (from browser PushSubscription.toJSON()):
    {
      "endpoint": "https://fcm.googleapis.com/...",
      "keys": {"p256dh": "...", "auth": "..."}
    }
    """
    if not is_push_enabled():
        logger.warning("⚠️  VAPID keys not configured — push skipped.")
        return False

    try:
        from pywebpush import webpush, WebPushException

        payload = json.dumps({
            "title": title,
            "body":  body,
            "icon":  icon,
            "url":   url,
        })

        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=_pad(VAPID_PRIVATE_KEY),
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        logger.info("✅ Push sent → %s…", subscription_info.get("endpoint", "")[:60])
        return True

    except Exception as exc:
        err_str = str(exc)
        if "410" in err_str or "404" in err_str:
            logger.info("🗑️  Subscription expired/unsubscribed (HTTP %s) — will be removed.", 
                        "410" if "410" in err_str else "404")
            return False
        logger.error("❌ Push error: %s", exc)
        return False


def broadcast_push(subscriptions: list[dict], title: str, body: str,
                   icon: str = "/static/icons/icon-192x192.png",
                   url: str = "/") -> dict:
    """Send push to multiple subscriptions. Returns {sent, failed, expired}."""
    results = {"sent": 0, "failed": 0, "expired": []}
    for sub in subscriptions:
        ok = send_push(sub["subscription_info"], title, body, icon, url)
        if ok:
            results["sent"] += 1
        else:
            err_str = str(ok)
            if "410" in err_str or "404" in err_str:
                results["expired"].append(sub.get("id"))
            else:
                results["failed"] += 1
    return results
