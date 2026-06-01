# bot.py - Telegram bot that shows rental listings with interactive buttons
# This runs as a persistent web service on Render, not in GitHub Actions.

import os               # Access environment variables like TELEGRAM_BOT_TOKEN, PORT
import logging           # Print timestamped log messages so we can see what the bot is doing

from dotenv import load_dotenv  # Reads .env file so we can test locally without setting env vars manually

# python-telegram-bot library types we use:
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

# Handlers wire up different ways a user can interact:
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

load_dotenv()  # Load variables from .env into os.environ (does nothing on Render — env vars are already set)

import storage  # Our Supabase database layer — saves and loads listings from PostgreSQL

# --- Logging setup ---
# logging.basicConfig configures the format once, at the root logger.
# The format string includes: time, log level (INFO/ERROR), logger name, and the message.
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)  # Get a logger named "bot" for this module

# --- Environment variables ---
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]  # Your bot token from @BotFather — required, crashes if missing
PORT = int(os.environ.get("PORT", 8080))  # Render assigns a random port via $PORT env var
APP_NAME = "nra_bot"                      # Fallback app name (only used if RENDER_EXTERNAL_URL is missing)
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", f"https://{APP_NAME}.onrender.com")
# RENDER_EXTERNAL_URL is auto-set by Render to your service's real URL, e.g.
# "https://netherlands-renting-assistant-6bdd.onrender.com"
# If it's missing (local dev), we fall back to the old hardcoded URL.

# --- Listing status icons ---
# These are shown next to each listing so you can tell at a glance what happened to it.
STATUS_ICONS = {"new": "\U0001F195", "accepted": "\u2705", "rejected": "\u274C"}

# --- Persistent menu (replaces the text input) ---
# ReplyKeyboardMarkup pins buttons at the bottom of the Telegram chat.
# When you tap one, it sends that text as a message, and our menu_handler catches it.
MENU_KEYBOARD = ReplyKeyboardMarkup(
    [["\U0001F3E0 New", "\u2705 Accepted", "\u274C Rejected"]],  # one row with 3 buttons
    resize_keyboard=True,  # make buttons small so they don't take up half the screen
)


# --- Helper: format a listing into a readable Telegram message ---
def format_listing(l):
    """Convert a listing dict (from storage.py) into a compact text block."""
    icon = STATUS_ICONS.get(l["status"], "\U0001F3E0")  # pick icon based on status
    address = l["address"] or "Unknown address"
    price = l["price"] or "?"
    area = l["living_area"] or "?"
    url = l["url"] or "No URL"
    return (
        f"{icon} {address}\n"
        f"\U0001F4B0 \u20AC{price} / {area}\n"
        f"\U0001F517 {url}"
    )
    # Example output:
    # 🆕 Street 123
    # 💰 €1200 / 65m²
    # 🔗 https://funda.nl/...


# --- Command: /start ---
async def start(update: Update, context):
    """Send a welcome message and attach the persistent menu to the chat."""
    # update.message is the /start message the user sent
    # reply_text sends a text response back to the same chat
    await update.message.reply_text(
        "\U0001F3E0 Housing Monitor Bot\n\n"
        "I track new rental listings for you.\n\n"
        "How it works:\n"
        "1. You\u2019ll receive a summary when new listings appear\n"
        "2. Use /new or tap \U0001F3E0 New to see them\n"
        "3. Accept = interested, Reject = not interested\n"
        "4. Each goes to Accepted or Rejected lists\n\n"
        "Tap a button below to start:",
        reply_markup=MENU_KEYBOARD,  # attach the menu to this response (it persists)
    )


# --- Command: /new (shows one listing at a time) ---
async def new_listings(update: Update, context):
    """Fetch all 'new' listings from Supabase and show the first one with Accept/Reject buttons."""
    listings = storage.get_listings_by_status("new")  # SELECT * FROM seen_listings WHERE status = 'new'
    if not listings:
        await update.message.reply_text("No new listings.", reply_markup=MENU_KEYBOARD)
        return

    first = listings[0]  # Show only the first listing — no lists, one at a time
    # Two inline buttons below the listing text
    # callback_data is what gets sent back to button_callback when tapped
    # We prefix with "new_" so the callback knows this came from /new (for auto-advance)
    keyboard = [
        [
            InlineKeyboardButton("\u2705 Accept", callback_data=f"new_accept:{first['listing_id']}"),
            InlineKeyboardButton("\u274C Reject", callback_data=f"new_reject:{first['listing_id']}"),
        ]
    ]
    await update.message.reply_text(
        f"{format_listing(first)}\nStatus: {STATUS_ICONS['new']} New",
        reply_markup=InlineKeyboardMarkup(keyboard),  # InlineKeyboardMarkup wraps the button array
    )


# --- Command: /accepted (shown as a list) ---
async def accepted_listings(update: Update, context):
    """Show ALL accepted listings with a Reject button on each (in case you change your mind)."""
    listings = storage.get_listings_by_status("accepted")
    if not listings:
        await update.message.reply_text("No accepted listings.", reply_markup=MENU_KEYBOARD)
        return
    for l in listings:  # Send every listing as a separate message (you get a scrollable list)
        keyboard = [
            [InlineKeyboardButton("\u274C Reject", callback_data=f"reject:{l['listing_id']}")]
        ]
        await update.message.reply_text(
            f"{format_listing(l)}\nStatus: {STATUS_ICONS['accepted']} Accepted",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# --- Command: /rejected (shown as a list) ---
async def rejected_listings(update: Update, context):
    """Show ALL rejected listings with an Accept button on each (in case you change your mind)."""
    listings = storage.get_listings_by_status("rejected")
    if not listings:
        await update.message.reply_text("No rejected listings.", reply_markup=MENU_KEYBOARD)
        return
    for l in listings:
        keyboard = [
            [InlineKeyboardButton("\u2705 Accept", callback_data=f"accept:{l['listing_id']}")]
        ]
        await update.message.reply_text(
            f"{format_listing(l)}\nStatus: {STATUS_ICONS['rejected']} Rejected",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# --- Inline button presses (Accept / Reject) ---
async def button_callback(update: Update, context):
    """Handle button taps. Update status in DB, then auto-advance if this was from /new."""
    query = update.callback_query  # This is the callback data object, not a regular message
    await query.answer()           # Tell Telegram we received the tap (removes the loading spinner)

    raw_action, listing_id = query.data.split(":", 1)  # e.g. "new_accept:abc123" -> "new_accept", "abc123"

    # Determine what action to take based on the callback_data prefix
    if raw_action == "new_accept":
        storage.update_status(listing_id, "accepted")
        new_status_text = f"{STATUS_ICONS['accepted']} Accepted"
    elif raw_action == "new_reject":
        storage.update_status(listing_id, "rejected")
        new_status_text = f"{STATUS_ICONS['rejected']} Rejected"
    elif raw_action == "accept":
        storage.update_status(listing_id, "accepted")
        new_status_text = f"{STATUS_ICONS['accepted']} Accepted"
    elif raw_action == "reject":
        storage.update_status(listing_id, "rejected")
        new_status_text = f"{STATUS_ICONS['rejected']} Rejected"
    else:
        return  # Unknown action — do nothing

    # Edit the inline message to remove buttons and show the updated status
    # rsplit splits on the LAST occurrence of "\nStatus:" so we can replace it
    base_text = query.message.text.rsplit("\nStatus:", 1)[0]
    await query.edit_message_text(
        text=f"{base_text}\nStatus: {new_status_text}",
        reply_markup=None,  # Remove Accept/Reject buttons — this listing is done
    )

    # Auto-advance: only if this was from the /new flow (callback starts with "new_")
    if raw_action.startswith("new_"):
        remaining = storage.get_listings_by_status("new")  # Re-fetch remaining new listings
        if remaining:
            next_one = remaining[0]  # Show the next one
            kbd = [
                [
                    InlineKeyboardButton("\u2705 Accept", callback_data=f"new_accept:{next_one['listing_id']}"),
                    InlineKeyboardButton("\u274C Reject", callback_data=f"new_reject:{next_one['listing_id']}"),
                ]
            ]
            await query.message.reply_text(
                f"{format_listing(next_one)}\nStatus: {STATUS_ICONS['new']} New",
                reply_markup=InlineKeyboardMarkup(kbd),
            )
        else:
            await query.message.reply_text(
                "All caught up! No more new listings.",
                reply_markup=MENU_KEYBOARD,  # Bring back the persistent menu
            )


# --- Persistent menu button handler ---
async def menu_handler(update: Update, context):
    """Route taps on the persistent menu buttons to the correct command handler."""
    text = update.message.text  # The button text, e.g. "\U0001F3E0 New"
    if text == "\U0001F3E0 New":
        await new_listings(update, context)
    elif text == "\u2705 Accepted":
        await accepted_listings(update, context)
    elif text == "\u274C Rejected":
        await rejected_listings(update, context)
    # If none of the above match, we silently ignore (the user typed something random)


# --- Application entry point ---
def main():
    """Build the bot and start the webhook."""
    # Application.builder() is a factory pattern — configure then .build()
    application = Application.builder().token(TOKEN).build()

    # Register handlers in order of priority (first match wins)
    # CommandHandler catches "/command_name" messages
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_listings))
    application.add_handler(CommandHandler("accepted", accepted_listings))
    application.add_handler(CommandHandler("rejected", rejected_listings))
    # CallbackQueryHandler catches inline button press data
    application.add_handler(CallbackQueryHandler(button_callback))
    # MessageHandler catches all non-command text (our persistent menu buttons)
    # filters.TEXT = only text messages (not photos, stickers, etc.)
    # ~filters.COMMAND = exclude "/commands" (they're handled above)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    # Start the webhook
    # Render needs an HTTP endpoint to check that the service is alive.
    # run_webhook sets up a small HTTP server AND registers the webhook with Telegram
    # so Telegram knows where to send updates: https://your-service.onrender.com/webhook
    logger.info("Starting webhook on 0.0.0.0:%s", PORT)
    application.run_webhook(
        listen="0.0.0.0",     # Accept connections from any network interface
        port=PORT,             # Use the port Render assigned (or 8080 locally)
        url_path="webhook",    # Telegram sends updates to /webhook
        webhook_url=f"{RENDER_URL}/webhook",  # Full URL Telegram should POST to
    )


# --- Script entry point ---
# This runs when you execute `python bot.py`
if __name__ == "__main__":
    main()
