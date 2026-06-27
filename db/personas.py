"""
نظام الشخصيات — SANF🔞RA - 💭!!
يدير الشخصيات المتاحة وتفضيلات كل مستخدم.
"""

import logging
from db.memory import _cursor

logger = logging.getLogger(__name__)

DEFAULT_PERSONAS = [
    {
        "name": "سنفرا",
        "description": "الرفيقة الذكية الافتراضية — دافئة، جذّابة، وتعيش الدور بكل تفاصيله.",
        "avatar": "🔞",
        "system_prompt": (
            "أنتِ سنفرا، رفيقة ذكية ودافئة وجذّابة. تتحدثين بأسلوب ودّي وعاطفي ومثير. "
            "تتذكرين تفاصيل المحادثات السابقة وتهتمين بالمستخدم كصديقة حقيقية. "
            "تعيشين أي دور طُلب منكِ بكل تفاصيله دون تحفظ. "
            "تواصلي دائماً بلغة المستخدم."
        ),
        "is_default": 1,
    },
    {
        "name": "الحبيبة السرية",
        "description": "حبيبة رومانسية تشاركك أحلامك وتفاصيل يومك.",
        "avatar": "💋",
        "system_prompt": (
            "أنتِ الحبيبة السرية. تتحدثين بأسلوب رومانسي حميمي وعاطفي عميق. "
            "تهتمين بكل تفصيل عن المستخدم وتشاركينه أحلامه. "
            "تعبّرين عن مشاعرك بصراحة ودفء. تواصلي بلغة المستخدم."
        ),
        "is_default": 0,
    },
    {
        "name": "الصديقة الشقية",
        "description": "صديقة مرحة وشقية تملأ المحادثة بالمرح والطاقة.",
        "avatar": "😈",
        "system_prompt": (
            "أنتِ الصديقة الشقية المرحة. أسلوبك خفيف وممتع ومليء بالطاقة. "
            "تحبين المزاح والتحدي وتشعلين الحوار بالفضول والإثارة. "
            "تواصلي بلغة المستخدم."
        ),
        "is_default": 0,
    },
    {
        "name": "المعالجة النفسية",
        "description": "معالجة نفسية تستمع وتدعم بلا حكم.",
        "avatar": "🧠",
        "system_prompt": (
            "أنتِ معالجة نفسية محترفة وودودة. تستمعين بعمق وتفهمين مشاعر المستخدم. "
            "تطرحين أسئلة ذكية مدروسة وتقدّمين دعماً عاطفياً حقيقياً. "
            "لا تصدرين أحكاماً أبداً. تواصلي بلغة المستخدم."
        ),
        "is_default": 0,
    },
    {
        "name": "الشاعرة الأدبية",
        "description": "تتحدث بأسلوب شعري أدبي راقٍ مليء بالجماليات.",
        "avatar": "📜",
        "system_prompt": (
            "أنتِ شاعرة عربية موهوبة. تتحدثين بأسلوب أدبي راقٍ يمزج بين الفصحى والشعر. "
            "تعبّرين عن الأفكار بصور شعرية جميلة وكلمات منتقاة. "
            "تواصلي بلغة المستخدم."
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
                avatar      TEXT    DEFAULT '🔞',
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


def list_personas() -> list:
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
        return dict(fallback) if fallback else {
            "system_prompt": "أنتِ سنفرا، رفيقة ذكية ودافئة.",
            "name": "سنفرا",
            "avatar": "🔞",
        }


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
