# bot.py — Telegram bot with dynamic reply keyboard
# When reviewing a listing: [✅ Accept | ❌ Reject]
# When idle (no listings): [🏠 New | ✅ Accepted | ❌ Rejected]

import os
import logging

from dotenv import load_dotenv

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters

load_dotenv()

import storage

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
PORT = int(os.environ.get("PORT", 8080))
APP_NAME = "nra_bot"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", f"https://{APP_NAME}.onrender.com")

STATUS_ICONS = {"new": "\U0001F195", "accepted": "\u2705", "rejected": "\u274C"}

BTN_NEW = "\U0001F3E0 New"
BTN_ACCEPTED = "\u2705 Accepted"
BTN_REJECTED = "\u274C Rejected"
BTN_ACCEPT = "\u2705 Accept"
BTN_REJECT = "\u274C Reject"


def routing_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_NEW), KeyboardButton(BTN_ACCEPTED), KeyboardButton(BTN_REJECTED)]],
        resize_keyboard=True,
    )


def accept_reject_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_ACCEPT), KeyboardButton(BTN_REJECT)]],
        resize_keyboard=True,
    )


def format_listing(l):
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


async def start(update: Update, context):
    context.user_data.clear()
    await update.message.reply_text(
        "\U0001F3E0 Housing Monitor Bot\n\n"
        "I track new rental listings for you.\n\n"
        "How it works:\n"
        "1. You\u2019ll receive a summary when new listings appear\n"
        "2. Tap \U0001F3E0 New to review them one by one\n"
        "3. Accept = interested, Reject = not interested\n"
        "4. Tap \u2705 Accepted or \u274C Rejected to review past decisions\n\n"
        "Tap \U0001F3E0 New to start:",
        reply_markup=routing_keyboard(),
    )


async def _show_listing(update, context, flow, listings):
    """Shared logic: show first listing from a list and set context."""
    if not listings:
        context.user_data.pop("current_listing_id", None)
        context.user_data.pop("current_flow", None)
        return False

    l = listings[0]
    context.user_data["current_listing_id"] = l["listing_id"]
    context.user_data["current_flow"] = flow
    icon = STATUS_ICONS[flow]
    await update.message.reply_text(
        f"{format_listing(l)}\nStatus: {icon} {flow.title()}",
        reply_markup=accept_reject_keyboard(),
    )
    return True


async def cmd_new(update: Update, context):
    await _show_listing(update, context, "new", storage.get_listings_by_status("new"))


async def cmd_accepted(update: Update, context):
    await _show_listing(update, context, "accepted", storage.get_listings_by_status("accepted"))


async def cmd_rejected(update: Update, context):
    await _show_listing(update, context, "rejected", storage.get_listings_by_status("rejected"))


async def handle_text(update: Update, context):
    text = update.message.text

    if text == BTN_NEW:
        await cmd_new(update, context)
    elif text == BTN_ACCEPTED:
        await cmd_accepted(update, context)
    elif text == BTN_REJECTED:
        await cmd_rejected(update, context)
    elif text in (BTN_ACCEPT, BTN_REJECT):
        listing_id = context.user_data.get("current_listing_id")
        flow = context.user_data.get("current_flow")
        if not listing_id or not flow:
            await update.message.reply_text(
                "No active listing to review. Tap \U0001F3E0 New to start.",
                reply_markup=routing_keyboard(),
            )
            return

        new_status = "accepted" if text == BTN_ACCEPT else "rejected"
        storage.update_status(listing_id, new_status)

        remaining = storage.get_listings_by_status(flow)
        if remaining:
            await _show_listing(update, context, flow, remaining)
        else:
            context.user_data.pop("current_listing_id", None)
            context.user_data.pop("current_flow", None)
            labels = {"new": "new listings", "accepted": "accepted listings", "rejected": "rejected listings"}
            await update.message.reply_text(
                f"All done! No more {labels.get(flow, 'listings')}.",
                reply_markup=routing_keyboard(),
            )
    else:
        await update.message.reply_text(
            "Use the buttons below to navigate.",
            reply_markup=routing_keyboard(),
        )


def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", cmd_new))
    application.add_handler(CommandHandler("accepted", cmd_accepted))
    application.add_handler(CommandHandler("rejected", cmd_rejected))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Starting webhook on 0.0.0.0:%s", PORT)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{RENDER_URL}/webhook",
    )


if __name__ == "__main__":
    main()
