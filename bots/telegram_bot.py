import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from ai.ollama_client import ask_ollama
from ai.image_gen import generate_image
from ai.tts import text_to_speech
from utils.config import TELEGRAM_TOKEN
from db.memory import get_history, save_message, clear_history, get_user_summary
from db.personas import (
    list_personas, get_active_persona, set_active_persona,
    create_persona, delete_persona,
)
from db.memory import upsert_profile

logger = logging.getLogger(__name__)
PLATFORM = "telegram"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.first_name if user else "صديقي"
    if user:
        upsert_profile(PLATFORM, str(user.id), user.first_name or "")
    await update.message.reply_text(
        f"👋 مرحباً {name}! أنا كلافو، رفيقك الذكي.\n\n"
        "🧠 أتذكر محادثاتنا حتى بعد إعادة التشغيل\n"
        "🎭 يمكنني تغيير شخصيتي بأمر /personas\n"
        "🎨 أرسم لك صوراً بأمر /image\n"
        "🔊 أتكلم بصوت بأمر /tts\n\n"
        "الأوامر الكاملة: /help"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 *أوامر كلافو*\n\n"
        "*المحادثة:*\n"
        "/start — بدء المحادثة\n"
        "/clear — مسح سجل المحادثة\n"
        "/memory — إحصائيات ذاكرتنا\n\n"
        "*الشخصيات:*\n"
        "/personas — عرض الشخصيات المتاحة\n"
        "/persona <الاسم> — تغيير الشخصية\n"
        "/newpersona — إنشاء شخصية جديدة\n\n"
        "*الوسائط (مجاناً):*\n"
        "/image <وصف> — توليد صورة\n"
        "/tts <نص> — تحويل نص إلى صوت\n\n"
        "فقط اكتب رسالتك وسأرد فوراً! ✨",
        parse_mode="Markdown",
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    deleted = clear_history(PLATFORM, user_id)
    await update.message.reply_text(
        f"🗑️ تم مسح {deleted} رسالة من ذاكرتي. لنبدأ صفحة جديدة! 😊"
    )


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    summary = get_user_summary(PLATFORM, user_id)
    if not summary:
        await update.message.reply_text("🧠 لا توجد ذكريات مسجّلة بعد. ابدأ محادثتنا!")
        return
    persona = get_active_persona(PLATFORM, user_id)
    await update.message.reply_text(
        f"🧠 *ذاكرتي عنك*\n\n"
        f"• الاسم: {summary['الاسم']}\n"
        f"• عدد رسائلك: {summary['عدد_الرسائل']}\n"
        f"• أول محادثة: {summary['أول_ظهور']}\n"
        f"• آخر محادثة: {summary['آخر_ظهور']}\n"
        f"• شخصيتي الحالية: {persona.get('avatar','🤖')} {persona.get('name','كلافو')}",
        parse_mode="Markdown",
    )


async def cmd_personas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    personas = list_personas()
    user_id = str(update.effective_user.id)
    active = get_active_persona(PLATFORM, user_id)
    active_id = active.get("id", -1)

    keyboard = []
    for p in personas:
        is_active = p["id"] == active_id
        label = f"{'✅ ' if is_active else ''}{p['avatar']} {p['name']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"persona:{p['id']}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🎭 *الشخصيات المتاحة*\n\n"
        f"شخصيتي الحالية: {active.get('avatar','🤖')} *{active.get('name','كلافو')}*\n\n"
        "اختر شخصية لتفعيلها:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def callback_persona(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    persona_id = int(query.data.split(":")[1])
    ok = set_active_persona(PLATFORM, user_id, persona_id)
    if ok:
        from db.personas import get_persona_by_id
        p = get_persona_by_id(persona_id)
        await query.edit_message_text(
            f"✅ تم تفعيل شخصية *{p['avatar']} {p['name']}*\n\n"
            f"_{p['description']}_\n\n"
            "ابدأ محادثتك الآن! 🚀",
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text("❌ لم يتم العثور على الشخصية.")


async def cmd_persona(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await cmd_personas(update, context)
        return
    name = " ".join(context.args).strip()
    from db.personas import get_persona_by_name
    p = get_persona_by_name(name)
    if not p:
        personas = list_personas()
        names = ", ".join(f"{x['avatar']} {x['name']}" for x in personas)
        await update.message.reply_text(
            f"❌ لم أجد شخصية باسم «{name}».\n\n"
            f"الشخصيات المتاحة: {names}\n\n"
            "استخدم /personas لعرض قائمة التفاعلية."
        )
        return
    user_id = str(update.effective_user.id)
    set_active_persona(PLATFORM, user_id, p["id"])
    await update.message.reply_text(
        f"✅ تم التبديل إلى {p['avatar']} *{p['name']}*\n_{p['description']}_",
        parse_mode="Markdown",
    )


async def cmd_newpersona(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "🎭 *إنشاء شخصية جديدة*\n\n"
            "الصيغة:\n"
            "`/newpersona الاسم | الوصف | تعليمات الشخصية`\n\n"
            "مثال:\n"
            "`/newpersona الطبيب | طبيب خبير ومتفهم | أنت طبيب ذو خبرة واسعة تُجيب بدقة علمية وبأسلوب إنساني.`",
            parse_mode="Markdown",
        )
        return
    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ الصيغة غير صحيحة. يجب فصل الأجزاء الثلاثة بـ `|`\n"
            "مثال: `/newpersona الاسم | الوصف | التعليمات`",
            parse_mode="Markdown",
        )
        return
    name, description, prompt = parts[0], parts[1], parts[2]
    user_id = str(update.effective_user.id)
    p = create_persona(name, description, prompt, created_by=f"telegram:{user_id}")
    if not p:
        await update.message.reply_text(f"❌ اسم الشخصية «{name}» مستخدم بالفعل. اختر اسماً آخر.")
        return
    set_active_persona(PLATFORM, user_id, p["id"])
    await update.message.reply_text(
        f"✨ تم إنشاء شخصية *{p['name']}* وتفعيلها!\n\n"
        f"_{p['description']}_",
        parse_mode="Markdown",
    )


async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "🎨 أرسل لي وصفاً للصورة:\n`/image غروب الشمس على البحر`",
            parse_mode="Markdown",
        )
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🎨 جاري توليد الصورة، لحظة...")
    img_buf = generate_image(prompt)
    if img_buf:
        await update.message.reply_photo(photo=img_buf, caption=f"🎨 {prompt}")
        await msg.delete()
    else:
        await msg.edit_text("⚠️ تعذّر توليد الصورة. حاول مجدداً.")


async def cmd_tts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "🔊 أرسل لي النص لتحويله إلى صوت:\n`/tts مرحباً، كيف حالك اليوم؟`",
            parse_mode="Markdown",
        )
        return
    text = " ".join(context.args)
    msg = await update.message.reply_text("🔊 جاري توليد الصوت...")
    audio_buf = text_to_speech(text)
    if audio_buf:
        await update.message.reply_voice(voice=audio_buf)
        await msg.delete()
    else:
        await msg.edit_text("⚠️ تعذّر توليد الصوت. حاول مجدداً.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = str(user.id)
    user_text = update.message.text
    display_name = user.first_name or ""

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    history = get_history(PLATFORM, user_id)
    persona = get_active_persona(PLATFORM, user_id)
    system_prompt = persona.get("system_prompt")

    logger.info("رسالة تيليغرام من %s: %s", display_name or user_id, user_text[:60])
    reply = ask_ollama(user_text, history, system_prompt=system_prompt)

    save_message(PLATFORM, user_id, "user", user_text)
    save_message(PLATFORM, user_id, "assistant", reply)
    if display_name:
        upsert_profile(PLATFORM, user_id, display_name)

    await update.message.reply_text(reply)


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("خطأ في بوت تيليغرام: %s", context.error)


def build_telegram_app():
    if not TELEGRAM_TOKEN:
        logger.warning("⚠️  TELEGRAM_TOKEN غير محدد — بوت تيليغرام مُعطَّل.")
        return None

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("personas", cmd_personas))
    app.add_handler(CommandHandler("persona", cmd_persona))
    app.add_handler(CommandHandler("newpersona", cmd_newpersona))
    app.add_handler(CommandHandler("image", cmd_image))
    app.add_handler(CommandHandler("tts", cmd_tts))
    app.add_handler(CallbackQueryHandler(callback_persona, pattern=r"^persona:\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(handle_error)

    logger.info("✅ تم إعداد بوت تيليغرام بنجاح.")
    return app
