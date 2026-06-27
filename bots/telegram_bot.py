"""
SANF🔞RA - 💭!! — Telegram Bot
Full-featured: personas, image gen, TTS, memory, stats, inline keyboard.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from ai.llm_router import ask_llm
from ai.image_gen import generate_image
from ai.tts import text_to_speech
from utils.config import TELEGRAM_TOKEN, WELCOME_IMAGE_URL, BOT_NAME
from db.memory import get_history, save_message, clear_history, get_user_summary, get_stats
from db.personas import (
    list_personas, get_active_persona, set_active_persona,
    create_persona, delete_persona, get_persona_by_id,
)
from db.memory import upsert_profile

logger = logging.getLogger(__name__)
PLATFORM = "telegram"

NEWPERSONA_NAME, NEWPERSONA_DESC, NEWPERSONA_PROMPT = range(3)


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎭 اختر الشخصية", callback_data="menu:personas")],
        [
            InlineKeyboardButton("🎨 ارسم لي صورة", callback_data="menu:image"),
            InlineKeyboardButton("🗣️ تحويل لصوت",   callback_data="menu:tts"),
        ],
        [
            InlineKeyboardButton("📊 إحصائياتي",        callback_data="menu:stats"),
            InlineKeyboardButton("❓ المساعدة والشرح", callback_data="menu:help"),
        ],
    ])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.first_name if user else "حبيبي"
    if user:
        upsert_profile(PLATFORM, str(user.id), user.first_name or "")

    caption = (
        f"أهلين فيك يا {name}... نورتني. 🙈♥️\n\n"
        "أنا هون كرمالك... دلع، اهتمام، وشوية شقاوة بتخلي كل حكي بيناتنا إلو طعم خاص. 😋♨️\n\n"
        "اختار الشخصية اللي بتعجبك، أو احكيلي شو ببالك... وأنا رح عيش الدور معك بكل تفاصيله. 💋\n\n"
        "يلا... لا تخليني ناطرتك، ابعتلي أول رسالة وخلي السهرة تبلش. 🔞!"
    )

    try:
        await update.message.reply_photo(
            photo=WELCOME_IMAGE_URL,
            caption=caption,
            reply_markup=_main_keyboard(),
        )
    except Exception:
        await update.message.reply_text(caption, reply_markup=_main_keyboard())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"🔞 *{BOT_NAME} — الأوامر*\n\n"
        "*المحادثة:*\n"
        "/start — بدء المحادثة\n"
        "/clear — مسح سجل المحادثة\n"
        "/stats — إحصائياتي\n\n"
        "*الشخصيات:*\n"
        "/personas — عرض الشخصيات المتاحة\n"
        "/newpersona — إنشاء شخصية مخصصة\n\n"
        "*الوسائط (مجاناً):*\n"
        "/image <وصف> — توليد صورة\n"
        "/tts <نص> — تحويل نص إلى صوت\n\n"
        "💋 فقط اكتب رسالتك وسأرد فوراً!"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=_main_keyboard())


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    deleted = clear_history(PLATFORM, user_id)
    await update.message.reply_text(
        f"🗑️ تم مسح {deleted} رسالة من ذاكرتي. لنبدأ صفحة جديدة! 😊"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    summary = get_user_summary(PLATFORM, user_id)
    if not summary:
        await update.message.reply_text("📊 لا توجد إحصائيات بعد. ابدأ محادثتنا!")
        return
    persona = get_active_persona(PLATFORM, user_id)
    await update.message.reply_text(
        f"📊 *إحصائياتي معك*\n\n"
        f"• الاسم: {summary.get('الاسم', '—')}\n"
        f"• عدد رسائلك: {summary.get('عدد_الرسائل', 0)}\n"
        f"• أول محادثة: {summary.get('أول_ظهور', '—')}\n"
        f"• آخر محادثة: {summary.get('آخر_ظهور', '—')}\n"
        f"• شخصيتي الحالية: {persona.get('avatar', '🔞')} {persona.get('name', BOT_NAME)}",
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
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu:back")])

    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if msg:
        await msg.reply_text(
            f"🎭 *الشخصيات المتاحة*\n\n"
            f"الحالية: {active.get('avatar', '🔞')} *{active.get('name', BOT_NAME)}*\n\n"
            "اختر شخصية لتفعيلها:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)

    if data.startswith("persona:"):
        persona_id = int(data.split(":")[1])
        ok = set_active_persona(PLATFORM, user_id, persona_id)
        if ok:
            p = get_persona_by_id(persona_id)
            await query.edit_message_text(
                f"✅ تم تفعيل *{p['avatar']} {p['name']}*\n\n"
                f"_{p.get('description', '')}_ \n\n"
                "ابدأ محادثتك الآن! 💋",
                parse_mode="Markdown",
                reply_markup=_main_keyboard(),
            )
        return

    if data == "menu:personas":
        personas = list_personas()
        active = get_active_persona(PLATFORM, user_id)
        active_id = active.get("id", -1)
        keyboard = []
        for p in personas:
            is_active = p["id"] == active_id
            label = f"{'✅ ' if is_active else ''}{p['avatar']} {p['name']}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"persona:{p['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu:back")])
        await query.edit_message_text(
            "🎭 *اختر شخصيتك:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data == "menu:image":
        await query.edit_message_text(
            "🎨 أرسل لي وصف الصورة:\n`/image وصف الصورة`\n\nمثال: `/image غروب الشمس على البحر`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu:back")]]),
        )

    elif data == "menu:tts":
        await query.edit_message_text(
            "🗣️ أرسل النص لتحويله لصوت:\n`/tts النص هنا`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu:back")]]),
        )

    elif data == "menu:stats":
        summary = get_user_summary(PLATFORM, user_id)
        persona = get_active_persona(PLATFORM, user_id)
        if not summary:
            text = "📊 لا توجد إحصائيات بعد. ابدأ محادثتنا!"
        else:
            text = (
                f"📊 *إحصائياتي معك*\n\n"
                f"• الاسم: {summary.get('الاسم', '—')}\n"
                f"• عدد رسائلك: {summary.get('عدد_الرسائل', 0)}\n"
                f"• آخر محادثة: {summary.get('آخر_ظهور', '—')}\n"
                f"• الشخصية: {persona.get('avatar', '🔞')} {persona.get('name', BOT_NAME)}"
            )
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu:back")]]),
        )

    elif data == "menu:help":
        text = (
            f"❓ *المساعدة*\n\n"
            "/start — رسالة الترحيب\n"
            "/personas — اختيار الشخصية\n"
            "/newpersona — إنشاء شخصية مخصصة\n"
            "/image <وصف> — توليد صورة مجاناً\n"
            "/tts <نص> — تحويل لصوت\n"
            "/stats — إحصائياتي\n"
            "/clear — مسح المحادثة\n\n"
            "💋 أو اكتب أي رسالة وسأرد فوراً!"
        )
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu:back")]]),
        )

    elif data == "menu:back":
        caption = f"أهلين مرة ثانية! 🙈♥️\nشو بتحب تعمل؟"
        try:
            await query.edit_message_text(caption, reply_markup=_main_keyboard())
        except Exception:
            pass

    elif data.startswith("delpersona:"):
        persona_id = int(data.split(":")[1])
        ok = delete_persona(persona_id, requested_by=f"telegram:{user_id}")
        if ok:
            await query.answer("🗑️ تم حذف الشخصية")
        else:
            await query.answer("❌ لا يمكن حذف هذه الشخصية")


async def cmd_newpersona(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🎭 *إنشاء شخصية جديدة*\n\n"
        "الخطوة 1/3: أرسل *اسم* الشخصية الجديدة:\n"
        "(أو /cancel للإلغاء)",
        parse_mode="Markdown",
    )
    return NEWPERSONA_NAME


async def newpersona_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["np_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ الاسم: *{context.user_data['np_name']}*\n\n"
        "الخطوة 2/3: أرسل *وصفاً مختصراً* للشخصية:\n"
        "(أو /cancel للإلغاء)",
        parse_mode="Markdown",
    )
    return NEWPERSONA_DESC


async def newpersona_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["np_desc"] = update.message.text.strip()
    await update.message.reply_text(
        "الخطوة 3/3: أرسل *تعليمات الشخصية* (System Prompt):\n\n"
        "مثال: _أنتِ طبيبة خبيرة ودودة تُجيبين بدقة علمية._\n"
        "(أو /cancel للإلغاء)",
        parse_mode="Markdown",
    )
    return NEWPERSONA_PROMPT


async def newpersona_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = str(update.effective_user.id)
    name = context.user_data.get("np_name", "")
    desc = context.user_data.get("np_desc", "")
    prompt = update.message.text.strip()

    p = create_persona(name, desc, prompt, created_by=f"telegram:{user_id}")
    if not p:
        await update.message.reply_text(f"❌ اسم الشخصية «{name}» مستخدم بالفعل. جرّب /newpersona مرة أخرى.")
        return ConversationHandler.END

    set_active_persona(PLATFORM, user_id, p["id"])
    await update.message.reply_text(
        f"✨ تم إنشاء شخصية *{p['avatar']} {p['name']}* وتفعيلها!\n\n"
        f"_{p.get('description', '')}_",
        parse_mode="Markdown",
        reply_markup=_main_keyboard(),
    )
    return ConversationHandler.END


async def newpersona_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ تم إلغاء إنشاء الشخصية.", reply_markup=_main_keyboard())
    return ConversationHandler.END


async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "🎨 أرسل وصف الصورة:\n`/image غروب الشمس على البحر`",
            parse_mode="Markdown",
        )
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text("🎨 جاري توليد الصورة، لحظة... ✨")
    img_buf = generate_image(prompt)
    if img_buf:
        await update.message.reply_photo(photo=img_buf, caption=f"🎨 {prompt}")
        await msg.delete()
    else:
        await msg.edit_text("⚠️ تعذّر توليد الصورة. حاول مجدداً.")


async def cmd_tts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "🗣️ أرسل النص لتحويله إلى صوت:\n`/tts مرحباً، كيف حالك اليوم؟`",
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

    logger.info("رسالة تيليغرام من %s: %s", display_name or user_id, user_text[:60])
    reply = ask_llm(user_text, history, system_prompt=persona.get("system_prompt"))

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

    newpersona_conv = ConversationHandler(
        entry_points=[CommandHandler("newpersona", cmd_newpersona)],
        states={
            NEWPERSONA_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, newpersona_name)],
            NEWPERSONA_DESC:   [MessageHandler(filters.TEXT & ~filters.COMMAND, newpersona_desc)],
            NEWPERSONA_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, newpersona_prompt)],
        },
        fallbacks=[CommandHandler("cancel", newpersona_cancel)],
    )

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("clear",    cmd_clear))
    app.add_handler(CommandHandler("stats",    cmd_stats))
    app.add_handler(CommandHandler("personas", cmd_personas))
    app.add_handler(CommandHandler("image",    cmd_image))
    app.add_handler(CommandHandler("tts",      cmd_tts))
    app.add_handler(newpersona_conv)
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(handle_error)

    logger.info("✅ تم إعداد بوت تيليغرام — %s", BOT_NAME)
    return app
