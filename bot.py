import os
import io
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import anthropic
from estimate_generator import build_estimate_pdf
from drive_uploader import upload_pdf as drive_upload, search_files, download_file
from calendar_generator import build_ics, cancel_ics, update_ics
from calendar_api import add_event, delete_event, update_event, find_event

CALENDAR_ENABLED = all(os.environ.get(k) for k in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN'])

DRIVE_ENABLED = all(os.environ.get(k) for k in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN'])

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


ESTIMATE_SYSTEM_PROMPT = """You are a pricing assistant for Santacruz Brothers LLC.
Given a job description, return a JSON object with the estimate details using Ray's rate card.

Rate card:
- Exterior paint labor: Easy $2.60/sqft, Standard $3.10/sqft, Complex $3.50/sqft
- Interior paint labor: Easy $3.90/sqft, Standard $4.25/sqft, Complex $4.75/sqft
- SW SuperPaint: charge $55/gal, BM Aura Exterior: charge $95/gal, BM Aura Interior: charge $95/gal
- Coverage: 125 sqft/gal
- Pavers: $9.50/sqft
- Block wall add-on: $1,500 flat
- Baseboard install labor: $3.50/lin ft
- Baseboard painting: $2.75/lin ft
- Tile demo (tile): $2.65/sqft, Tile demo (carpet): $1.25/sqft
- Tile install labor: $3.85-$9.00/sqft
- Smooth texture: $7.50/sqft
- Supplies: ~$300/job for paint jobs
- Estimates valid 7 days

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "estimate_no": "1071",
  "client_name": "Client Name",
  "client_address": "Address line 1\\nCity, State ZIP",
  "line_items": [
    {
      "name": "Short product/service name",
      "description": "Detailed description of work",
      "qty": "100",
      "rate": "$3.50",
      "amount": "$350.00"
    }
  ],
  "total": 350.00,
  "notes": "Any assumptions or notes for Ray to review"
}

Use the next estimate number after 1070 unless Ray specifies one. Calculate amounts precisely."""


async def estimate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    args = ' '.join(context.args) if context.args else ''
    if not args:
        await update.message.reply_text(
            "Describe the job after /estimate\n\n"
            "Example:\n/estimate Rene Brofft, 308 lin ft baseboard install and paint"
        )
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=ESTIMATE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": args}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw: {raw}")
        await update.message.reply_text("Couldn't parse the estimate — try rephrasing the job description.")
        return
    except Exception as e:
        logger.error(f"Estimate Claude error: {e}")
        await update.message.reply_text("Error generating estimate. Try again.")
        return

    today = datetime.now()
    valid = today + timedelta(days=7)
    estimate_date = today.strftime('%m/%d/%Y')
    valid_through = valid.strftime('%m/%d/%Y')

    try:
        pdf_bytes = build_estimate_pdf(
            estimate_no=data.get('estimate_no', '1071'),
            estimate_date=estimate_date,
            valid_through=valid_through,
            client_name=data.get('client_name', ''),
            client_address=data.get('client_address', ''),
            line_items=data.get('line_items', []),
            total=float(data.get('total', 0)),
        )
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        await update.message.reply_text("Error building PDF. Try again.")
        return

    notes = data.get('notes', '')
    filename = f"Estimate_{data.get('estimate_no', 'DRAFT')}_{data.get('client_name', '').replace(' ', '_')}.pdf"
    caption = f"📄 Estimate #{data.get('estimate_no', '')} — {data.get('client_name', '')}\nTotal: ${float(data.get('total', 0)):,.2f}"
    if notes:
        caption += f"\n\n⚠️ {notes}"

    # Upload to Google Drive
    if DRIVE_ENABLED:
        try:
            drive_url = drive_upload(pdf_bytes, filename, 'Estimates')
            caption += f"\n\n📁 [Saved to Drive]({drive_url})"
        except Exception as e:
            logger.error(f"Drive upload error: {e}")

    await update.message.reply_document(
        document=io.BytesIO(pdf_bytes),
        filename=filename,
        caption=caption,
        parse_mode='Markdown',
    )


INVOICE_SYSTEM_PROMPT = """You are a billing assistant for Santacruz Brothers LLC.
Given a job description, return a JSON object for a final invoice using Ray's rate card.

Rate card:
- Exterior paint labor: Easy $2.60/sqft, Standard $3.10/sqft, Complex $3.50/sqft
- Interior paint labor: Easy $3.90/sqft, Standard $4.25/sqft, Complex $4.75/sqft
- SW SuperPaint: charge $55/gal, BM Aura: charge $95/gal. Coverage: 125 sqft/gal
- Pavers: $9.50/sqft, Block wall add-on: $1,500 flat
- Baseboard install: $3.50/lin ft, Baseboard painting: $2.75/lin ft
- Tile demo (tile): $2.65/sqft, Tile demo (carpet): $1.25/sqft
- Tile install labor: $3.85-$9.00/sqft, Smooth texture: $7.50/sqft
- Supplies: ~$300/job for paint jobs

Return ONLY valid JSON (no markdown, no explanation):
{
  "invoice_no": "1071",
  "client_name": "Client Name",
  "client_address": "Address line 1\\nCity, State ZIP",
  "line_items": [
    {
      "name": "Short product/service name",
      "description": "Detailed description of work completed",
      "qty": "100",
      "rate": "$3.50",
      "amount": "$350.00"
    }
  ],
  "total": 350.00,
  "notes": "Any assumptions or notes for Ray to review"
}

Use the next invoice number after 1070 unless Ray specifies one."""


async def invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    args = ' '.join(context.args) if context.args else ''
    if not args:
        await update.message.reply_text(
            "Describe the completed job after /invoice\n\n"
            "Example:\n/invoice Rene Brofft, 308 lin ft baseboard install and paint, completed"
        )
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=INVOICE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": args}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw: {raw}")
        await update.message.reply_text("Couldn't parse the invoice — try rephrasing.")
        return
    except Exception as e:
        logger.error(f"Invoice Claude error: {e}")
        await update.message.reply_text("Error generating invoice. Try again.")
        return

    today = datetime.now()
    invoice_date = today.strftime('%m/%d/%Y')

    try:
        pdf_bytes = build_estimate_pdf(
            estimate_no=data.get('invoice_no', '1071'),
            estimate_date=invoice_date,
            valid_through='',
            client_name=data.get('client_name', ''),
            client_address=data.get('client_address', ''),
            line_items=data.get('line_items', []),
            total=float(data.get('total', 0)),
        )
    except Exception as e:
        logger.error(f"Invoice PDF error: {e}")
        await update.message.reply_text("Error building PDF. Try again.")
        return

    notes = data.get('notes', '')
    filename = f"Invoice_{data.get('invoice_no', 'DRAFT')}_{data.get('client_name', '').replace(' ', '_')}.pdf"
    caption = f"🧾 Invoice #{data.get('invoice_no', '')} — {data.get('client_name', '')}\nTotal: ${float(data.get('total', 0)):,.2f}"
    if notes:
        caption += f"\n\n⚠️ {notes}"

    if DRIVE_ENABLED:
        try:
            drive_url = drive_upload(pdf_bytes, filename, 'Invoices')
            caption += f"\n\n📁 [Saved to Drive]({drive_url})"
        except Exception as e:
            logger.error(f"Drive upload error: {e}")

    await update.message.reply_document(
        document=io.BytesIO(pdf_bytes),
        filename=filename,
        caption=caption,
        parse_mode='Markdown',
    )


CAL_SYSTEM_PROMPT = """You are a calendar assistant for Ray Santacruz in Phoenix, Arizona (MST = UTC-7, no daylight saving).
Today's date is provided in the user message.

Detect the intent and return ONLY valid JSON (no markdown):

For NEW events:
{
  "action": "add",
  "title": "Event title",
  "date": "YYYY-MM-DD",
  "start_time": "HH:MM",
  "end_time": "HH:MM",
  "location": "optional or empty string",
  "description": "optional or empty string"
}

For CANCEL events:
{
  "action": "cancel",
  "title": "Event title",
  "original_date": "YYYY-MM-DD",
  "original_start_time": "HH:MM"
}

For UPDATE/MOVE events:
{
  "action": "update",
  "title": "Event title",
  "original_date": "YYYY-MM-DD",
  "original_start_time": "HH:MM",
  "new_date": "YYYY-MM-DD",
  "new_start_time": "HH:MM",
  "new_end_time": "HH:MM",
  "location": "optional or empty string"
}

Rules:
- Default duration: 1 hour
- If no time given, use 08:00
- morning → 08:00, afternoon → 13:00, evening → 17:00
- Resolve relative dates (Friday, next Monday) using today's date
- 24-hour format for all times"""


async def cal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return

    args = ' '.join(context.args) if context.args else ''
    if not args:
        await update.message.reply_text(
            "Add a calendar event with /cal\n\n"
            "Examples:\n"
            "/cal Meeting with Rene Friday at 2pm\n"
            "/cal Nate walkthrough Monday 9am at 123 Main St\n"
            "/cal Don Foster job starts June 5"
        )
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    today = datetime.now().strftime('%Y-%m-%d')

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=CAL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Today is {today}. Event: {args}"}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
    except Exception as e:
        logger.error(f"Cal parse error: {e}")
        await update.message.reply_text("Couldn't parse that event. Try: /cal [event] [day] at [time]")
        return

    try:
        action = data.get('action', 'add')

        if CALENDAR_ENABLED:
            # Use Google Calendar API directly — no tapping needed
            if action == 'cancel':
                orig_start = datetime.strptime(f"{data['original_date']} {data['original_start_time']}", "%Y-%m-%d %H:%M")
                event_id = find_event(data['title'], data['original_date'])
                if event_id:
                    delete_event(event_id)
                    await update.message.reply_text(f"🗑 Removed '{data['title']}' on {data['original_date']} from your calendar.")
                else:
                    await update.message.reply_text(f"Couldn't find '{data['title']}' on {data['original_date']}. Check the date and try again.")
                return

            elif action == 'update':
                orig_start = datetime.strptime(f"{data['original_date']} {data['original_start_time']}", "%Y-%m-%d %H:%M")
                new_start  = datetime.strptime(f"{data['new_date']} {data['new_start_time']}", "%Y-%m-%d %H:%M")
                new_end    = datetime.strptime(f"{data['new_date']} {data['new_end_time']}", "%Y-%m-%d %H:%M")
                event_id = find_event(data['title'], data['original_date'])
                if event_id:
                    update_event(event_id, data['title'], new_start, new_end, data.get('location', ''))
                    await update.message.reply_text(
                        f"✏️ Updated '{data['title']}'\n📆 Now: {data['new_date']} {data['new_start_time']}–{data['new_end_time']} MST"
                    )
                else:
                    await update.message.reply_text(f"Couldn't find '{data['title']}' on {data['original_date']}. Check the date and try again.")
                return

            else:  # add
                start = datetime.strptime(f"{data['date']} {data['start_time']}", "%Y-%m-%d %H:%M")
                end   = datetime.strptime(f"{data['date']} {data['end_time']}", "%Y-%m-%d %H:%M")
                add_event(data['title'], start, end, data.get('location', ''), data.get('description', ''))
                reply = f"✅ Added to your calendar:\n📅 {data['title']}\n📆 {data['date']} {data['start_time']}–{data['end_time']} MST"
                if data.get('location'):
                    reply += f"\n📍 {data['location']}"
                reply += "\n🔔 Reminders: 1 day + 1 hour before"
                await update.message.reply_text(reply)
                return

        # Fallback: send .ics file
        if action == 'cancel':
            orig_start = datetime.strptime(f"{data['original_date']} {data['original_start_time']}", "%Y-%m-%d %H:%M")
            ics_bytes = cancel_ics(title=data['title'], original_start=orig_start)
            filename = f"CANCEL_{data['original_date']}_{data['title'].replace(' ', '_')[:30]}.ics"
            caption = f"🗑 Cancellation: {data['title']}\n📆 {data['original_date']} {data['original_start_time']} MST\n\nTap to remove from your calendar."
        elif action == 'update':
            orig_start = datetime.strptime(f"{data['original_date']} {data['original_start_time']}", "%Y-%m-%d %H:%M")
            new_start  = datetime.strptime(f"{data['new_date']} {data['new_start_time']}", "%Y-%m-%d %H:%M")
            new_end    = datetime.strptime(f"{data['new_date']} {data['new_end_time']}", "%Y-%m-%d %H:%M")
            ics_bytes = update_ics(data['title'], orig_start, new_start, new_end, data.get('location', ''))
            filename = f"UPDATE_{data['new_date']}_{data['title'].replace(' ', '_')[:30]}.ics"
            caption = f"✏️ Updated: {data['title']}\n📆 {data['new_date']} {data['new_start_time']}–{data['new_end_time']} MST\n\nTap to update your calendar."
        else:
            start = datetime.strptime(f"{data['date']} {data['start_time']}", "%Y-%m-%d %H:%M")
            end   = datetime.strptime(f"{data['date']} {data['end_time']}", "%Y-%m-%d %H:%M")
            ics_bytes = build_ics(data['title'], start, end, data.get('location', ''), data.get('description', ''))
            filename = f"{data['date']}_{data['title'].replace(' ', '_')[:30]}.ics"
            caption = f"📅 {data['title']}\n📆 {data['date']} {data['start_time']}–{data['end_time']} MST\n\nTap to add to your calendar."

        await update.message.reply_document(document=io.BytesIO(ics_bytes), filename=filename, caption=caption)

    except Exception as e:
        logger.error(f"Calendar error: {e}", exc_info=True)
        await update.message.reply_text(f"Calendar error: {str(e)[:200]}")


async def find(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return

    query = ' '.join(context.args) if context.args else ''
    if not query:
        await update.message.reply_text(
            "Search your Drive files with /find\n\nExample:\n/find Rene Brofft\n/find Walker invoice\n/find Nate estimate"
        )
        return

    if not DRIVE_ENABLED:
        await update.message.reply_text("Google Drive not connected.")
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")

    try:
        files = search_files(query)
    except Exception as e:
        logger.error(f"Drive search error: {e}", exc_info=True)
        await update.message.reply_text(f"Drive error: {str(e)[:300]}")
        return

    if not files:
        await update.message.reply_text(f"No files found for '{query}'.")
        return

    await update.message.reply_text(f"Found {len(files)} file(s) — sending...")

    for f in files:
        try:
            pdf_bytes = download_file(f['id'])
            await update.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename=f['name'],
                caption=f"📄 {f['name']}",
            )
        except Exception as e:
            logger.error(f"Drive download error: {e}")
            link = f.get('webViewLink', '')
            await update.message.reply_text(f"📄 {f['name']}\n{link}")


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("estimate", estimate))
    app.add_handler(CommandHandler("invoice", invoice))
    app.add_handler(CommandHandler("find", find))
    app.add_handler(CommandHandler("cal", cal))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
