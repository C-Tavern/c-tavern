import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from ai.ollama_client import ask_ollama
from utils.config import TELEGRAM_TOKEN
from db.memory import get_history, save_message, clear_history, get_user_summary

logger = logging.getLogger(__name__)

PLATFORM = "telegram"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.first_name if user else "صديقي"
    await update.message.reply_text(
        f"👋 مرحباً {name}! أنا كلافو، رفيقك الذكي.\n\n"
        "يمكنك الحديث معي في أي وقت، وسأكون هنا دائماً للاستماع والمساعدة. 💬\n\n"
        "أوامر متاحة:\n"
        "/start — بدء المحادثة\n"
        "/clear — مسح سجل المحادثة\n"
        "/memory — عرض إحصائيات ذاكرتنا\n"
        "/help — المساعدة"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 *مساعد كلافو*\n\n"
        "أنا رفيقك الذكي القادر على:\n"
        "• الدردشة والنقاش في أي موضوع\n"
        "• تذكّر محادثاتنا السابقة حتى بعد إعادة التشغيل 🧠\n"
        "• دعمك عاطفياً ومساعدتك\n"
        "• تمثيل الشخصيات (TavernAI)\n\n"
        "فقط اكتب رسالتك وسأرد عليك! ✨",
        parse_mode="Markdown",
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    deleted = clear_history(PLATFORM, user_id)
    await update.message.reply_text(
        f"🗑️ تم مسح {deleted} رسالة من ذاكرتي. لنبدأ من جديد! 😊"
    )


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    summary = get_user_summary(PLATFORM, user_id)
    if not summary:
        await update.message.reply_text("🧠 لا توجد ذكريات مسجّلة بعد. ابدأ محادثتنا!")
        return
    await update.message.reply_text(
        f"🧠 *ذاكرتي عنك*\n\n"
        f"• الاسم: {summary['الاسم']}\n"
        f"• عدد رسائلك: {summary['عدد_الرسائل']}\n"
        f"• أول محادثة: {summary['أول_ظهور']}\n"
        f"• آخر محادثة: {summary['آخر_ظهور']}",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = str(user.id)
    user_text = update.message.text
    display_name = user.first_name or ""

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    history = get_history(PLATFORM, user_id)
    logger.info("رسالة تيليغرام من %s (%s): %s", display_name, user_id, user_text[:60])

    reply = ask_ollama(user_text, history)

    save_message(PLATFORM, user_id, "user", user_text)
    save_message(PLATFORM, user_id, "assistant", reply)

    if display_name:
        from db.memory import upsert_profile
        upsert_profile(PLATFORM, user_id, display_name)

    await update.message.reply_text(reply)


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("خطأ في بوت تيليغرام: %s", context.error)


def build_telegram_app():
    if not TELEGRAM_TOKEN:
        logger.warning("⚠️  TELEGRAM_TOKEN غير محدد — بوت تيليغرام مُعطَّل.")
        return None

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(handle_error)

    logger.info("✅ تم إعداد بوت تيليغرام بنجاح.")
    return app
