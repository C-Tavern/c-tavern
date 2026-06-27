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

logger = logging.getLogger(__name__)

user_histories: dict[int, list[dict]] = {}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.first_name if user else "صديقي"
    await update.message.reply_text(
        f"👋 مرحباً {name}! أنا كلافو، رفيقك الذكي.\n\n"
        "يمكنك الحديث معي في أي وقت، وسأكون هنا دائماً للاستماع والمساعدة. 💬\n\n"
        "أوامر متاحة:\n"
        "/start — بدء المحادثة\n"
        "/clear — مسح سجل المحادثة\n"
        "/help — المساعدة"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 *مساعد كلافو*\n\n"
        "أنا رفيقك الذكي القادر على:\n"
        "• الدردشة والنقاش في أي موضوع\n"
        "• تذكّر محادثاتنا السابقة\n"
        "• دعمك عاطفياً ومساعدتك\n"
        "• تمثيل الشخصيات (TavernAI)\n\n"
        "فقط اكتب رسالتك وسأرد عليك! ✨",
        parse_mode="Markdown",
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_histories.pop(user_id, None)
    await update.message.reply_text("🗑️ تم مسح سجل المحادثة. لنبدأ من جديد! 😊")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    logger.info("رسالة واردة من المستخدم %d: %s", user_id, user_text[:50])
    reply = ask_ollama(user_text, user_histories[user_id])

    user_histories[user_id].append({"role": "user", "content": user_text})
    user_histories[user_id].append({"role": "assistant", "content": reply})

    if len(user_histories[user_id]) > 40:
        user_histories[user_id] = user_histories[user_id][-40:]

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(handle_error)

    logger.info("✅ تم إعداد بوت تيليغرام بنجاح.")
    return app
