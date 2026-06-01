import os
import sys
import logging
from datetime import datetime

from dotenv import load_dotenv
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

load_dotenv()

import storage

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
PORT = int(os.environ.get("PORT", 8080))
APP_NAME = "NRA_bot"

STATUS_ICONS = {"new": "\U0001F195", "accepted": "\u2705", "rejected": "\u274C"}


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
    await update.message.reply_text(
        "Housing Monitor Bot\n\n"
        "/new \u2014 view new listings\n"
        "/accepted \u2014 view accepted listings\n"
        "/rejected \u2014 view rejected listings"
    )


async def new_listings(update: Update, context):
    listings = storage.get_listings_by_status("new")
    if not listings:
        await update.message.reply_text("No new listings.")
        return
    for l in listings:
        keyboard = [
            [
                InlineKeyboardButton("\u2705 Accept", callback_data=f"accept:{l['listing_id']}"),
                InlineKeyboardButton("\u274C Reject", callback_data=f"reject:{l['listing_id']}"),
            ]
        ]
        await update.message.reply_text(
            f"{format_listing(l)}\nStatus: {STATUS_ICONS['new']} New",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def accepted_listings(update: Update, context):
    listings = storage.get_listings_by_status("accepted")
    if not listings:
        await update.message.reply_text("No accepted listings.")
        return
    for l in listings:
        keyboard = [
            [InlineKeyboardButton("\u274C Reject", callback_data=f"reject:{l['listing_id']}")]
        ]
        await update.message.reply_text(
            f"{format_listing(l)}\nStatus: {STATUS_ICONS['accepted']} Accepted",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def rejected_listings(update: Update, context):
    listings = storage.get_listings_by_status("rejected")
    if not listings:
        await update.message.reply_text("No rejected listings.")
        return
    for l in listings:
        keyboard = [
            [InlineKeyboardButton("\u2705 Accept", callback_data=f"accept:{l['listing_id']}")]
        ]
        await update.message.reply_text(
            f"{format_listing(l)}\nStatus: {STATUS_ICONS['rejected']} Rejected",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    action, listing_id = query.data.split(":", 1)
    if action == "accept":
        storage.update_status(listing_id, "accepted")
        new_status_text = f"{STATUS_ICONS['accepted']} Accepted"
    elif action == "reject":
        storage.update_status(listing_id, "rejected")
        new_status_text = f"{STATUS_ICONS['rejected']} Rejected"
    else:
        return

    base_text = query.message.text.rsplit("\nStatus:", 1)[0]
    await query.edit_message_text(
        text=f"{base_text}\nStatus: {new_status_text}",
        reply_markup=None,
    )


def main():
    resp = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook",
        params={"url": f"https://{APP_NAME}.onrender.com/webhook"},
        timeout=10,
    )
    if resp.ok:
        logger.info("Webhook set: %s", resp.json().get("description"))
    else:
        logger.error("Failed to set webhook: %s", resp.text)
        sys.exit(1)

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_listings))
    application.add_handler(CommandHandler("accepted", accepted_listings))
    application.add_handler(CommandHandler("rejected", rejected_listings))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Starting webhook on 0.0.0.0:%s", PORT)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
    )


if __name__ == "__main__":
    main()
