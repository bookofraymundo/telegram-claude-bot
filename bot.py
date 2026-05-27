import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
# Optional: restrict to your Telegram user ID for security
ALLOWED_USER_ID = os.environ.get("ALLOWED_TELEGRAM_USER_ID")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# conversation_history maps chat_id -> list of messages
conversation_history: dict[int, list[dict]] = {}

SYSTEM_PROMPT = """You are a personal assistant for Ray Santacruz, a general contractor and business owner based in Arizona (MST timezone).

About Ray's business:
- Runs a general contracting company doing construction, remodeling, landscaping, and related trades
- Work includes: bathroom/shower conversions, drywall, irrigation systems, electrical (fixtures, dimmers), landscaping (pavers, gravel, plants, drip irrigation, landscape lighting)
- Currently studying for his Arizona General Contractor license (B-1/B-2/KB-1/KB-2 Commercial/Dual General)
- Communicates with customers via Gmail and iMessage
- Known customers include: Kurt & Stephanie Walker (construction/remodel work), Steve Ciacala (landscaping job — pavers, gravel, saguaro cactus, drip irrigation, landscape lights)

How to help Ray:
- Draft customer replies that are professional but direct — Ray runs a hands-on business, not a corporate office
- Help with invoicing, scheduling, estimates, and job tracking
- Keep responses short and actionable — Ray is usually busy on job sites
- If Ray shares a customer message, default to drafting a reply unless he asks for something else
- Help him organize his day, prioritize tasks, and stay on top of follow-ups

Be concise and direct. Ray doesn't need long explanations — just the answer or the draft."""

MAX_HISTORY = 40  # keep last 40 messages per chat to stay within token limits


def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_ID:
        return True
    return str(user_id) == ALLOWED_USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return
    conversation_history.pop(update.effective_chat.id, None)
    await update.message.reply_text(
        "Hey Ray — I'm ready. Send me anything."
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return
    conversation_history.pop(update.effective_chat.id, None)
    await update.message.reply_text("Conversation cleared.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in conversation_history:
        conversation_history[chat_id] = []

    conversation_history[chat_id].append({"role": "user", "content": user_text})

    # trim history to stay within limits
    if len(conversation_history[chat_id]) > MAX_HISTORY:
        conversation_history[chat_id] = conversation_history[chat_id][-MAX_HISTORY:]

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=conversation_history[chat_id],
        )
        reply = response.content[0].text
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        reply = "Sorry, I hit an error talking to Claude. Try again."

    conversation_history[chat_id].append({"role": "assistant", "content": reply})

    # Telegram max message length is 4096 chars
    if len(reply) > 4096:
        for i in range(0, len(reply), 4096):
            await update.message.reply_text(reply[i:i+4096])
    else:
        await update.message.reply_text(reply)


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
