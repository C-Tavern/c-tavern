"""
نظام الذاكرة طويلة الأمد — كلافو
يستخدم SQLite لحفظ تاريخ المحادثات لكل مستخدم عبر جميع المنصات.
"""

import sqlite3
import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("db/clavo_memory.sqlite")
MAX_HISTORY = 40

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


@contextmanager
def _cursor():
    conn = _get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _cursor() as cur:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                platform   TEXT    NOT NULL,
                user_id    TEXT    NOT NULL,
                role       TEXT    NOT NULL CHECK(role IN ('user','assistant','system')),
                content    TEXT    NOT NULL,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_platform_user
                ON messages(platform, user_id);

            CREATE TABLE IF NOT EXISTS user_profiles (
                platform    TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                display_name TEXT,
                first_seen  TEXT NOT NULL DEFAULT (datetime('now')),
                last_seen   TEXT NOT NULL DEFAULT (datetime('now')),
                msg_count   INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (platform, user_id)
            );

            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id        TEXT    NOT NULL UNIQUE,
                endpoint          TEXT    NOT NULL,
                p256dh            TEXT    NOT NULL,
                auth              TEXT    NOT NULL,
                user_agent        TEXT,
                subscribed_at     TEXT    NOT NULL DEFAULT (datetime('now')),
                last_notified_at  TEXT
            );
        """)
    logger.info("✅ قاعدة بيانات الذاكرة جاهزة: %s", DB_PATH)


# ── Push Subscription CRUD ─────────────────────────────────────────────────

def save_push_subscription(session_id: str, endpoint: str,
                            p256dh: str, auth: str,
                            user_agent: str = "") -> bool:
    try:
        with _cursor() as cur:
            cur.execute("""
                INSERT INTO push_subscriptions
                    (session_id, endpoint, p256dh, auth, user_agent)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    endpoint   = excluded.endpoint,
                    p256dh     = excluded.p256dh,
                    auth       = excluded.auth,
                    user_agent = excluded.user_agent
            """, (session_id, endpoint, p256dh, auth, user_agent))
        logger.info("✅ تم حفظ اشتراك Push — session: %s", session_id[:12])
        return True
    except Exception as e:
        logger.error("خطأ في حفظ الاشتراك: %s", e)
        return False


def delete_push_subscription(session_id: str) -> bool:
    with _cursor() as cur:
        cur.execute("DELETE FROM push_subscriptions WHERE session_id = ?", (session_id,))
    return True


def delete_push_subscription_by_endpoint(endpoint: str) -> None:
    with _cursor() as cur:
        cur.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))


def get_all_push_subscriptions() -> list:
    with _cursor() as cur:
        cur.execute("""
            SELECT id, session_id, endpoint, p256dh, auth
            FROM push_subscriptions
            ORDER BY subscribed_at DESC
        """)
        rows = cur.fetchall()
    result = []
    for row in rows:
        result.append({
            "id":         row["id"],
            "session_id": row["session_id"],
            "subscription_info": {
                "endpoint": row["endpoint"],
                "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
            },
        })
    return result


def get_push_subscription_count() -> int:
    with _cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM push_subscriptions")
        return cur.fetchone()[0]


def mark_push_notified(session_id: str) -> None:
    with _cursor() as cur:
        cur.execute("""
            UPDATE push_subscriptions SET last_notified_at = datetime('now')
            WHERE session_id = ?
        """, (session_id,))


def upsert_profile(platform: str, user_id: str, display_name: str = "") -> None:
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO user_profiles (platform, user_id, display_name, first_seen, last_seen, msg_count)
            VALUES (?, ?, ?, datetime('now'), datetime('now'), 1)
            ON CONFLICT(platform, user_id) DO UPDATE SET
                last_seen  = datetime('now'),
                msg_count  = msg_count + 1,
                display_name = CASE WHEN excluded.display_name != '' THEN excluded.display_name
                                    ELSE display_name END
        """, (platform, str(user_id), display_name))


def save_message(platform: str, user_id: str, role: str, content: str) -> None:
    with _cursor() as cur:
        cur.execute(
            "INSERT INTO messages (platform, user_id, role, content) VALUES (?, ?, ?, ?)",
            (platform, str(user_id), role, content),
        )
    if role == "user":
        upsert_profile(platform, str(user_id))


def get_history(platform: str, user_id: str, limit: int = MAX_HISTORY) -> list[dict]:
    with _cursor() as cur:
        cur.execute(
            """
            SELECT role, content FROM (
                SELECT role, content, created_at
                FROM messages
                WHERE platform = ? AND user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ) ORDER BY created_at ASC
            """,
            (platform, str(user_id), limit),
        )
        return [{"role": row["role"], "content": row["content"]} for row in cur.fetchall()]


def clear_history(platform: str, user_id: str) -> int:
    with _cursor() as cur:
        cur.execute(
            "DELETE FROM messages WHERE platform = ? AND user_id = ?",
            (platform, str(user_id)),
        )
        deleted = cur.rowcount
    logger.info("🗑️  محو %d رسالة للمستخدم %s على %s", deleted, user_id, platform)
    return deleted


def get_stats() -> dict:
    with _cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM messages")
        total_msgs = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM user_profiles")
        total_users = cur.fetchone()[0]

        cur.execute("""
            SELECT platform, COUNT(*) as cnt
            FROM messages GROUP BY platform
        """)
        by_platform = {row["platform"]: row["cnt"] for row in cur.fetchall()}

        cur.execute("""
            SELECT platform, COUNT(*) as cnt
            FROM user_profiles GROUP BY platform
        """)
        users_by_platform = {row["platform"]: row["cnt"] for row in cur.fetchall()}

        cur.execute("""
            SELECT platform, user_id, display_name, last_seen, msg_count
            FROM user_profiles
            ORDER BY last_seen DESC
            LIMIT 20
        """)
        recent_users = [dict(row) for row in cur.fetchall()]

    return {
        "إجمالي_الرسائل": total_msgs,
        "إجمالي_المستخدمين": total_users,
        "رسائل_حسب_المنصة": by_platform,
        "مستخدمون_حسب_المنصة": users_by_platform,
        "آخر_المستخدمين": recent_users,
    }


def get_user_summary(platform: str, user_id: str) -> dict:
    with _cursor() as cur:
        cur.execute(
            "SELECT * FROM user_profiles WHERE platform=? AND user_id=?",
            (platform, str(user_id)),
        )
        row = cur.fetchone()
        if not row:
            return {}
        cur.execute(
            "SELECT COUNT(*) FROM messages WHERE platform=? AND user_id=?",
            (platform, str(user_id)),
        )
        msg_count = cur.fetchone()[0]
    return {
        "المنصة": row["platform"],
        "المعرف": row["user_id"],
        "الاسم": row["display_name"] or "—",
        "أول_ظهور": row["first_seen"],
        "آخر_ظهور": row["last_seen"],
        "عدد_الرسائل": msg_count,
    }
