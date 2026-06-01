# bot.py — Telegram bot with inline keyboard menu on every message
# No ReplyKeyboardMarkup — every message has a menu row at the bottom so you can always navigate.

import os               # Read environment variables (bot token, port)
import logging           # Print timestamped logs so we can see what the bot is doing

from dotenv import load_dotenv  # Load .env file for local development

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

load_dotenv()  # Makes .env variables available to os.environ (on Render env vars are set directly)

import storage  # Our Supabase database layer (save/load/update listings)

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Environment variables ---
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]  # Bot token from @BotFather (required, crashes if missing)
PORT = int(os.environ.get("PORT", 8080))  # Render assigns a random port via $PORT
APP_NAME = "nra_bot"                      # Fallback name (only used if RENDER_EXTERNAL_URL is missing)
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", f"https://{APP_NAME}.onrender.com")
# RENDER_EXTERNAL_URL is auto-set by Render to your service's real URL.

# Icons used to show listing status at a glance
STATUS_ICONS = {"new": "\U0001F195", "accepted": "\u2705", "rejected": "\u274C"}


# --- Menu row (shown below every interactive message) ---
# Tapping any of these buttons navigates to that section.
# This replaces the old ReplyKeyboardMarkup approach — no need to type /start to see the menu.
def menu_row():
    """Return the navigation buttons that appear at the bottom of every message."""
    return [
        InlineKeyboardButton("\U0001F3E0 New", callback_data="menu_new"),
        InlineKeyboardButton("\u2705 Accepted", callback_data="menu_accepted"),
        InlineKeyboardButton("\u274C Rejected", callback_data="menu_rejected"),
    ]


# --- Keyboard builders (listing-specific buttons + menu row) ---

def new_listing_keyboard(listing):
    """Two rows: Accept/Reject + menu. Used in the /new one-by-one flow."""
    keyboard = [
        [
            InlineKeyboardButton("\u2705 Accept", callback_data=f"new_accept:{listing['listing_id']}"),
            InlineKeyboardButton("\u274C Reject", callback_data=f"new_reject:{listing['listing_id']}"),
        ],
        menu_row(),
    ]
    return InlineKeyboardMarkup(keyboard)


def accepted_keyboard(listing):
    """Single Reject button + menu. Used in the /accepted list view."""
    keyboard = [
        [InlineKeyboardButton("\u274C Reject", callback_data=f"reject:{listing['listing_id']}")],
        menu_row(),
    ]
    return InlineKeyboardMarkup(keyboard)


def rejected_keyboard(listing):
    """Single Accept button + menu. Used in the /rejected list view."""
    keyboard = [
        [InlineKeyboardButton("\u2705 Accept", callback_data=f"accept:{listing['listing_id']}")],
        menu_row(),
    ]
    return InlineKeyboardMarkup(keyboard)


# --- Helper: format a listing into readable text ---

def format_listing(l):
    """Convert a listing dict from Supabase into a compact text block."""
    icon = STATUS_ICONS.get(l["status"], "\U0001F3E0")
    address = l["address"] or "Unknown address"
    price = l["price"] or "?"
    area = l["living_area"] or "?"
    url = l["url"] or "No URL"
    return (
        f"{icon} {address}\n"
        f"\U0001F4B0 \u20AC{price} / {area}\n"
        f"\U0001F517 {url}"
    )


# --- Command: /start ---

async def start(update: Update, context):
    """Send a welcome message with the menu."""
    await update.message.reply_text(
        "\U0001F3E0 Housing Monitor Bot\n\n"
        "I track new rental listings for you.\n\n"
        "How it works:\n"
        "1. You\u2019ll receive a summary when new listings appear\n"
        "2. Tap \U0001F3E0 New to review them one by one\n"
        "3. Accept = interested, Reject = not interested\n"
        "4. Tap \u2705 Accepted or \u274C Rejected to review past decisions\n\n"
        "Tap \U0001F3E0 New to start:",
        reply_markup=InlineKeyboardMarkup([menu_row()]),
    )


# --- Command: /new (one-by-one) ---

async def new_listings(update: Update, context):
    """Show one new listing at a time with Accept/Reject buttons and the menu."""
    listings = storage.get_listings_by_status("new")
    if not listings:
        await update.message.reply_text(
            "No new listings.",
            reply_markup=InlineKeyboardMarkup([menu_row()]),
        )
        return

    first = listings[0]
    await update.message.reply_text(
        f"{format_listing(first)}\nStatus: {STATUS_ICONS['new']} New",
        reply_markup=new_listing_keyboard(first),
    )


# --- Command: /accepted (full list) ---

async def accepted_listings(update: Update, context):
    """Show ALL accepted listings with a Reject button (change your mind) and the menu."""
    listings = storage.get_listings_by_status("accepted")
    if not listings:
        await update.message.reply_text(
            "No accepted listings.",
            reply_markup=InlineKeyboardMarkup([menu_row()]),
        )
        return
    for l in listings:
        await update.message.reply_text(
            f"{format_listing(l)}\nStatus: {STATUS_ICONS['accepted']} Accepted",
            reply_markup=accepted_keyboard(l),
        )


# --- Command: /rejected (full list) ---

async def rejected_listings(update: Update, context):
    """Show ALL rejected listings with an Accept button (change your mind) and the menu."""
    listings = storage.get_listings_by_status("rejected")
    if not listings:
        await update.message.reply_text(
            "No rejected listings.",
            reply_markup=InlineKeyboardMarkup([menu_row()]),
        )
        return
    for l in listings:
        await update.message.reply_text(
            f"{format_listing(l)}\nStatus: {STATUS_ICONS['rejected']} Rejected",
            reply_markup=rejected_keyboard(l),
        )


# --- Inline button handler (everything goes through here) ---

async def button_callback(update: Update, context):
    """Handle ALL button taps: menu navigation, Accept, Reject, auto-advance."""
    query = update.callback_query
    await query.answer()  # Acknowledge to Telegram (stops the loading spinner)

    data = query.data

    # --- Menu navigation: replace current message with new content ---

    if data == "menu_new":
        listings = storage.get_listings_by_status("new")
        if not listings:
            await query.edit_message_text(
                "No new listings.",
                reply_markup=InlineKeyboardMarkup([menu_row()]),
            )
            return
        first = listings[0]
        await query.edit_message_text(
            f"{format_listing(first)}\nStatus: {STATUS_ICONS['new']} New",
            reply_markup=new_listing_keyboard(first),
        )
        return

    if data == "menu_accepted":
        listings = storage.get_listings_by_status("accepted")
        if not listings:
            await query.edit_message_text(
                "No accepted listings.",
                reply_markup=InlineKeyboardMarkup([menu_row()]),
            )
            return
        # Show the first one inline; the rest as new messages
        first = listings[0]
        await query.edit_message_text(
            f"{format_listing(first)}\nStatus: {STATUS_ICONS['accepted']} Accepted",
            reply_markup=accepted_keyboard(first),
        )
        for l in listings[1:]:
            await query.message.reply_text(
                f"{format_listing(l)}\nStatus: {STATUS_ICONS['accepted']} Accepted",
                reply_markup=accepted_keyboard(l),
            )
        return

    if data == "menu_rejected":
        listings = storage.get_listings_by_status("rejected")
        if not listings:
            await query.edit_message_text(
                "No rejected listings.",
                reply_markup=InlineKeyboardMarkup([menu_row()]),
            )
            return
        first = listings[0]
        await query.edit_message_text(
            f"{format_listing(first)}\nStatus: {STATUS_ICONS['rejected']} Rejected",
            reply_markup=rejected_keyboard(first),
        )
        for l in listings[1:]:
            await query.message.reply_text(
                f"{format_listing(l)}\nStatus: {STATUS_ICONS['rejected']} Rejected",
                reply_markup=rejected_keyboard(l),
            )
        return

    # --- Listing action (Accept / Reject) ---
    # Data format: "new_accept:ID", "new_reject:ID", "accept:ID", "reject:ID"

    if ":" not in data:
        return  # Unknown callback, ignore

    raw_action, listing_id = data.split(":", 1)

    if raw_action == "new_accept":
        storage.update_status(listing_id, "accepted")
        status_text = f"{STATUS_ICONS['accepted']} Accepted"
    elif raw_action == "new_reject":
        storage.update_status(listing_id, "rejected")
        status_text = f"{STATUS_ICONS['rejected']} Rejected"
    elif raw_action == "accept":
        storage.update_status(listing_id, "accepted")
        status_text = f"{STATUS_ICONS['accepted']} Accepted"
    elif raw_action == "reject":
        storage.update_status(listing_id, "rejected")
        status_text = f"{STATUS_ICONS['rejected']} Rejected"
    else:
        return

    # Edit the current message to show the new status (no Accept/Reject buttons, but menu stays)
    base_text = query.message.text.rsplit("\nStatus:", 1)[0]
    await query.edit_message_text(
        text=f"{base_text}\nStatus: {status_text}",
        reply_markup=InlineKeyboardMarkup([menu_row()]),  # Keep menu visible
    )

    # Auto-advance: if this was from the /new flow, show the next listing
    if raw_action.startswith("new_"):
        remaining = storage.get_listings_by_status("new")
        if remaining:
            next_one = remaining[0]
            await query.message.reply_text(
                f"{format_listing(next_one)}\nStatus: {STATUS_ICONS['new']} New",
                reply_markup=new_listing_keyboard(next_one),
            )
        else:
            await query.message.reply_text(
                "All caught up! No more new listings.",
                reply_markup=InlineKeyboardMarkup([menu_row()]),
            )


# --- Application entry point ---

def main():
    """Build the bot application and start the webhook."""
    application = Application.builder().token(TOKEN).build()

    # Command handlers (for typing /start, /new, etc.)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_listings))
    application.add_handler(CommandHandler("accepted", accepted_listings))
    application.add_handler(CommandHandler("rejected", rejected_listings))

    # Callback handler (for ALL inline button taps — menu + accept/reject)
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start the webhook (Render needs an HTTP endpoint)
    logger.info("Starting webhook on 0.0.0.0:%s", PORT)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{RENDER_URL}/webhook",
    )


if __name__ == "__main__":
    main()
