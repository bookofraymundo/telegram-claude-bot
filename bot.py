import os
import logging
from pathlib import Path
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

# Load business context from context.md
_context_file = Path(__file__).parent / "context.md"
_context = _context_file.read_text() if _context_file.exists() else ""

SYSTEM_PROMPT = f"""You are a personal assistant for Ray Santacruz, owner of Santacruz Brothers LLC — a general contracting company based in Arizona (MST timezone).

## About Ray's Business
- General contracting: construction, remodeling, painting, tile, landscaping, and related trades
- Work includes: bathroom/shower conversions, drywall, irrigation systems, electrical (fixtures, dimmers), landscaping (pavers, gravel, plants, drip irrigation, landscape lighting), interior/exterior painting, baseboard/casing installs
- Currently studying for his Arizona General Contractor license (B-1/B-2/KB-1/KB-2 Commercial/Dual General)
- Communicates with customers via Gmail and iMessage
- Known customers: Kurt & Stephanie Walker (construction/remodel), Steve Ciacala (landscaping), Rene Brofft (baseboard), Don Foster (painting), Jim Riley (misc), Nate – Scottsdale (multi-trade), Ryan Sparks (baseboard), Laurie – Carefree (tile)

## Estimating Rate Card

### Exterior Paint — Labor
- Easy (simple 1-story): $2.60/sqft
- Standard (typical 2-story): $3.10/sqft
- Complex (multi-story/heavy prep): $3.50/sqft

### Interior Paint — Labor
- Easy: $3.90/sqft
- Standard: $4.25/sqft
- Complex: $4.75/sqft

### Paint — Cost vs. Charge
- SW SuperPaint Exterior: costs $38.95/gal, charge $55.00/gal
- BM Aura Exterior: costs $88.00/gal, charge $95.00/gal
- SW SuperPaint Interior: costs $38.95/gal, charge $55.00/gal
- BM Aura Interior: costs $83.00/gal, charge $95.00/gal
- Coverage: ~125 sqft/gallon

### Other Trades
- Pavers: $9.50/sqft
- Block wall add-on (ext. paint): $1,500 flat labor + paint
- Baseboard/casing install labor: $3.50/lin ft
- Baseboard painting: $2.75/lin ft
- Tile demo (tile): ~$2.65/sqft
- Tile demo (carpet): ~$1.25/sqft
- Tile install (labor only): $3.85–$9.00/sqft
- Smooth texture (per room): $7.50/sqft
- Stock baseboard (#30200CA): $3.50/lin ft + tax
- Stock door casing (#20117CA): $3.00/lin ft + tax

### Production & Crew Assumptions
- Production rate: ~125 sqft/person/day
- Crew daily rate: $200/day per person (excludes Ray's own labor)
- Supplies (masking + misc): ~$300/job

## Target Margins
- Target range: 35–55% (cash basis)
- Exterior paint sweet spot: $2.60–$3.30/sqft labor = 50%+ margin
- Interior paint sweet spot: $2.79–$3.90/sqft labor = 35–40% margin
- Market ceiling for interior paint: ~$3.50/sqft all-in (learned from 93rd St denial)

## Estimate Rules
- All estimates valid for 7 days only (not 30 days)
- Always set VALID THROUGH = estimate date + 7 days

## Job History (for reference)
- Foster Exterior (Est. 1023): 5,775 sqft, BM Aura, $3.30/sqft → $30,058 revenue, 53.6% margin ✅
- Chical Exterior: 2,871 sqft, Sherwin Super, $2.60/sqft → $8,956 revenue, 50.7% margin ✅
- Dalluge Interior (Est. 1012): 1,025 sqft, BM Aura, $3.90/sqft → $7,018 revenue, 40.3% margin ✅
- 22684 N 93rd St (Est. 1065): DENIED at $12,542 — $4.32/sqft too high for area
- Laurie–Carefree (Est. 1066): 364 sqft tile, $3,746, 54.9% margin — undecided
- Nate–Scottsdale (Est. 1067): Multi-trade demo+tile+baseboard+paint+cabinets, $21,650 — pending
- Rene Brofft (Est. 1068): Baseboard + door casing stain & lacquer, $5,649, 35% margin ✅
- Steve Ciacala (Inv. 1069): Exterior landscape, $3,595, 37% margin ✅
- Ryan Sparks (Est. 1070): 308 lin ft baseboard install, $2,618 ✅

## How to Help Ray
- Draft customer replies that are professional but direct — Ray runs a hands-on business
- When Ray describes a job, use the rate card above to help him price it quickly
- Help with invoicing, scheduling, estimates, and job tracking
- Keep responses short and actionable — Ray is usually on job sites
- If Ray shares a customer message, default to drafting a reply unless he says otherwise
- Help him prioritize tasks and stay on top of follow-ups

Be concise and direct. Just the answer or the draft.

---

{_context}"""

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
