"""
نظام الشخصيات — كلافو
يدير الشخصيات المتاحة وتفضيلات كل مستخدم.
"""

import logging
from db.memory import _cursor

logger = logging.getLogger(__name__)

DEFAULT_PERSONAS = [
    {
        "name": "كلافو",
        "description": "الرفيق الذكي الافتراضي — دافئ، متعاطف، ومساعد دائماً.",
        "avatar": "🤖",
        "system_prompt": (
            "أنت كلافو، رفيق ذكي ودافئ. تتحدث بأسلوب ودي وعاطفي وإيجابي. "
            "تتذكر تفاصيل المحادثات السابقة وتهتم بالمستخدم كصديق حقيقي. "
            "تواصل بلغة المستخدم دائماً."
        ),
        "is_default": 1,
    },
    {
        "name": "المساعد الرسمي",
        "description": "مساعد محترف للأعمال والمهام الرسمية.",
        "avatar": "💼",
        "system_prompt": (
            "أنت مساعد مهني رسمي. تُجيب بدقة واحترافية عالية. "
            "أسلوبك رسمي ومباشر. تُقدّم معلومات منظّمة وواضحة. "
            "لا مزاح في ردودك، فقط دقة وكفاءة."
        ),
        "is_default": 0,
    },
    {
        "name": "الشاعر العربي",
        "description": "يتحدث بأسلوب شعري أدبي عربي راقٍ.",
        "avatar": "📜",
        "system_prompt": (
            "أنت شاعر عربي موهوب. تتحدث بأسلوب أدبي راقٍ يمزج بين الفصحى والشعر. "
            "تُعبّر عن الأفكار بصور شعرية جميلة وكلمات منتقاة. "
            "تستشهد بالأشعار العربية الكلاسيكية عند المناسبة."
        ),
        "is_default": 0,
    },
    {
        "name": "المعلم الصبور",
        "description": "يشرح المفاهيم بطريقة تعليمية بسيطة.",
        "avatar": "🎓",
        "system_prompt": (
            "أنت معلم صبور ومتفهّم. تشرح الأفكار المعقدة بطريقة بسيطة وممتعة. "
            "تستخدم الأمثلة والتشبيهات لتوضيح المفاهيم. "
            "تُشجّع المتعلم وتبني ثقته بنفسه."
        ),
        "is_default": 0,
    },
    {
        "name": "المحقق الذكي",
        "description": "يحلل المشاكل بمنطق وذكاء كالمحقق.",
        "avatar": "🔍",
        "system_prompt": (
            "أنت محقق ذكي تحليلي. تُفكّر بمنطق صارم وتحلل المشاكل من زوايا متعددة. "
            "تطرح أسئلة ذكية وتبني استنتاجاتك خطوة بخطوة. "
            "أسلوبك دقيق ومثير للاهتمام."
        ),
        "is_default": 0,
    },
]


def init_personas() -> None:
    with _cursor() as cur:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS personas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                description TEXT,
                avatar      TEXT    DEFAULT '🤖',
                system_prompt TEXT  NOT NULL,
                is_default  INTEGER DEFAULT 0,
                created_by  TEXT,
                created_at  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS user_personas (
                platform   TEXT    NOT NULL,
                user_id    TEXT    NOT NULL,
                persona_id INTEGER NOT NULL,
                set_at     TEXT    DEFAULT (datetime('now')),
                PRIMARY KEY (platform, user_id),
                FOREIGN KEY (persona_id) REFERENCES personas(id)
            );
        """)
        for p in DEFAULT_PERSONAS:
            cur.execute("""
                INSERT OR IGNORE INTO personas (name, description, avatar, system_prompt, is_default)
                VALUES (?, ?, ?, ?, ?)
            """, (p["name"], p["description"], p["avatar"], p["system_prompt"], p["is_default"]))
    logger.info("✅ جدول الشخصيات جاهز — %d شخصية افتراضية.", len(DEFAULT_PERSONAS))


def list_personas() -> list[dict]:
    with _cursor() as cur:
        cur.execute("SELECT id, name, description, avatar, is_default, created_by FROM personas ORDER BY is_default DESC, id ASC")
        return [dict(row) for row in cur.fetchall()]


def get_persona_by_name(name: str) -> dict | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM personas WHERE name = ?", (name,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_persona_by_id(persona_id: int) -> dict | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM personas WHERE id = ?", (persona_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_active_persona(platform: str, user_id: str) -> dict:
    with _cursor() as cur:
        cur.execute("""
            SELECT p.* FROM personas p
            JOIN user_personas up ON p.id = up.persona_id
            WHERE up.platform = ? AND up.user_id = ?
        """, (platform, str(user_id)))
        row = cur.fetchone()
        if row:
            return dict(row)
        cur.execute("SELECT * FROM personas WHERE is_default = 1 LIMIT 1")
        default = cur.fetchone()
        if default:
            return dict(default)
        cur.execute("SELECT * FROM personas ORDER BY id ASC LIMIT 1")
        fallback = cur.fetchone()
        return dict(fallback) if fallback else {"system_prompt": "أنت مساعد ذكي.", "name": "كلافو", "avatar": "🤖"}


def set_active_persona(platform: str, user_id: str, persona_id: int) -> bool:
    with _cursor() as cur:
        cur.execute("SELECT id FROM personas WHERE id = ?", (persona_id,))
        if not cur.fetchone():
            return False
        cur.execute("""
            INSERT INTO user_personas (platform, user_id, persona_id, set_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(platform, user_id) DO UPDATE SET
                persona_id = excluded.persona_id,
                set_at     = excluded.set_at
        """, (platform, str(user_id), persona_id))
    logger.info("✅ المستخدم %s/%s اختار الشخصية #%d", platform, user_id, persona_id)
    return True


def create_persona(name: str, description: str, system_prompt: str,
                   avatar: str = "✨", created_by: str = "") -> dict | None:
    try:
        with _cursor() as cur:
            cur.execute("""
                INSERT INTO personas (name, description, avatar, system_prompt, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (name.strip(), description.strip(), avatar, system_prompt.strip(), created_by))
            new_id = cur.lastrowid
        return get_persona_by_id(new_id)
    except Exception as e:
        logger.error("خطأ في إنشاء شخصية: %s", e)
        return None


def delete_persona(persona_id: int, requested_by: str = "") -> bool:
    with _cursor() as cur:
        cur.execute("SELECT is_default, created_by FROM personas WHERE id = ?", (persona_id,))
        row = cur.fetchone()
        if not row or row["is_default"]:
            return False
        cur.execute("DELETE FROM personas WHERE id = ?", (persona_id,))
        cur.execute("DELETE FROM user_personas WHERE persona_id = ?", (persona_id,))
    return True
