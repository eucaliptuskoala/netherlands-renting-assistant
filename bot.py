import logging
import os

from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import storage

load_dotenv()

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 8080))
APP_NAME = 'housing-bot'
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', f'https://{APP_NAME}.onrender.com')

# Onboarding conversation states
WAITING_CITY, WAITING_MIN_PRICE, WAITING_MAX_PRICE = range(3)

STATUS_ICONS = {
    'new': '\U0001f195',
    'accepted': '\u2705',
    'rejected': '\u274c',
}

BTN_NEW = '\U0001f3e0 New'
BTN_ACCEPTED = '\u2705 Accepted'
BTN_REJECTED = '\u274c Rejected'
BTN_SETTINGS = '\u2699\ufe0f Settings'
BTN_CHANGE_SETTINGS = '\u270f\ufe0f Change Settings'
BTN_CANCEL = '\u274c Cancel'

BTN_ACCEPT = '\u2705 Accept'
BTN_REJECT = '\u274c Reject'


def routing_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_NEW), KeyboardButton(BTN_ACCEPTED), KeyboardButton(BTN_REJECTED)],
            [KeyboardButton(BTN_SETTINGS)],
        ],
        resize_keyboard=True,
    )


def settings_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_CHANGE_SETTINGS)],
            [KeyboardButton(BTN_NEW), KeyboardButton(BTN_ACCEPTED), KeyboardButton(BTN_REJECTED)],
        ],
        resize_keyboard=True,
    )


def accept_reject_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_ACCEPT), KeyboardButton(BTN_REJECT)]],
        resize_keyboard=True,
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_CANCEL)]],
        resize_keyboard=True,
    )


def format_listing(listing):
    icon = STATUS_ICONS.get(listing['status'], '\U0001f3e0')
    address = listing['address'] or 'Unknown address'
    price = listing['price'] or '?'
    area = listing['living_area'] or '?'
    url = listing['url'] or 'No URL'
    city = listing.get('city', '').title()

    city_line = f' (\U0001f4cd {city})' if city else ''
    return f'{icon} {address}{city_line}\n\U0001f4b0 \u20ac{price} / {area}\n\U0001f517 {url}'


def _ensure_user(update: Update):
    """Ensure user exists in database and return user dictionary."""
    if not update.effective_chat:
        return None

    chat_id = update.effective_chat.id
    user = update.effective_user
    username = user.username if user else None
    first_name = user.first_name if user else None

    return storage.get_or_create_user(chat_id, username=username, first_name=first_name)


# --- Onboarding Conversation Handlers ---

async def start_onboarding_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the step-by-step setup."""
    if not update.message:
        return ConversationHandler.END

    if context.user_data is not None:
        context.user_data.pop('onboard_city', None)
        context.user_data.pop('onboard_min_price', None)

    msg = (
        '\U0001f3e0 Let\u2019s set up your rental search preferences!\n\n'
        'Step 1 of 3: Which Dutch city or region are you looking in?\n'
        '(e.g. Eindhoven, Amsterdam, Rotterdam, Utrecht)'
    )
    await update.message.reply_text(msg, reply_markup=cancel_keyboard())
    return WAITING_CITY


async def handle_onboard_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return WAITING_CITY

    city_input = update.message.text.strip().lower()
    if city_input == BTN_CANCEL.lower() or city_input == '/cancel':
        return await cancel_onboarding(update, context)

    if len(city_input) < 2:
        await update.message.reply_text('Please enter a valid city name:')
        return WAITING_CITY

    if context.user_data is not None:
        context.user_data['onboard_city'] = city_input

    msg = (
        f'\u2705 City: {city_input.title()}\n\n'
        'Step 2 of 3: What is your MINIMUM monthly budget in \u20ac?\n'
        '(e.g. 400 or enter 0 for no minimum)'
    )
    await update.message.reply_text(msg, reply_markup=cancel_keyboard())
    return WAITING_MIN_PRICE


async def handle_onboard_min_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return WAITING_MIN_PRICE

    text = update.message.text.strip()
    if text == BTN_CANCEL or text == '/cancel':
        return await cancel_onboarding(update, context)

    try:
        min_p = int(text)
        if min_p < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text(
            'Please enter a valid positive number for minimum budget (e.g. 400 or 0):',
            reply_markup=cancel_keyboard(),
        )
        return WAITING_MIN_PRICE

    if context.user_data is not None:
        context.user_data['onboard_min_price'] = min_p

    msg = (
        f'\u2705 Minimum budget: \u20ac{min_p}\n\n'
        'Step 3 of 3: What is your MAXIMUM monthly budget in \u20ac?\n'
        f'(e.g. {max(1200, min_p + 400)})'
    )
    await update.message.reply_text(msg, reply_markup=cancel_keyboard())
    return WAITING_MAX_PRICE


async def handle_onboard_max_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_chat or not update.message.text:
        return WAITING_MAX_PRICE

    text = update.message.text.strip()
    if text == BTN_CANCEL or text == '/cancel':
        return await cancel_onboarding(update, context)

    user_data = context.user_data or {}
    min_p = user_data.get('onboard_min_price', 0)
    city = user_data.get('onboard_city', 'eindhoven')

    try:
        max_p = int(text)
        if max_p < min_p:
            await update.message.reply_text(
                f'Maximum budget must be greater than or equal to minimum budget (\u20ac{min_p}).\n'
                'Please enter maximum budget in \u20ac:',
                reply_markup=cancel_keyboard(),
            )
            return WAITING_MAX_PRICE
    except ValueError:
        await update.message.reply_text(
            'Please enter a valid number for maximum budget (e.g. 1400):',
            reply_markup=cancel_keyboard(),
        )
        return WAITING_MAX_PRICE

    chat_id = update.effective_chat.id
    storage.update_user_preferences(
        chat_id,
        city=city,
        min_price=min_p,
        max_price=max_p,
        is_onboarded=True,
    )

    if context.user_data is not None:
        context.user_data.pop('onboard_city', None)
        context.user_data.pop('onboard_min_price', None)

    msg = (
        '\U0001f389 You\u2019re all set!\n\n'
        f'\U0001f4cd City: {city.title()}\n'
        f'\U0001f4b0 Budget: \u20ac{min_p} \u2014 \u20ac{max_p}\n\n'
        'I monitor listings every 15 minutes and will notify you when new matches appear.\n'
        'Tap \U0001f3e0 New below to view current listings:'
    )
    await update.message.reply_text(msg, reply_markup=routing_keyboard())
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return ConversationHandler.END

    if context.user_data is not None:
        context.user_data.pop('onboard_city', None)
        context.user_data.pop('onboard_min_price', None)

    await update.message.reply_text(
        'Setup cancelled. You can change your criteria anytime in \u2699\ufe0f Settings.',
        reply_markup=routing_keyboard(),
    )
    return ConversationHandler.END


# --- Main Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    user_profile = _ensure_user(update)
    if context.user_data is not None:
        context.user_data.clear()

    # If new user has not completed onboarding, launch setup wizard
    if not user_profile or not user_profile.get('is_onboarded'):
        await update.message.reply_text(
            'Welcome to Netherlands Renting Assistant! \U0001f3e0\n'
            'I will help you find an apartment in the Netherlands.'
        )
        return await start_onboarding_flow(update, context)

    city = user_profile['city'].title()
    min_p = user_profile['min_price']
    max_p = user_profile['max_price']
    stats = storage.get_user_stats(update.effective_chat.id)

    welcome_text = (
        '\U0001f3e0 Housing Monitor Bot\n\n'
        f'\U0001f4cd City: {city}\n'
        f'\U0001f4b0 Budget: \u20ac{min_p} \u2014 \u20ac{max_p}\n'
        f'\U0001f4ca Your listings: {stats["new"]} new | {stats["accepted"]} accepted | '
        f'{stats["rejected"]} rejected\n\n'
        'How it works:\n'
        '1. You\u2019ll receive an alert when new listings matching your criteria appear\n'
        '2. Tap \U0001f3e0 New to review them one by one\n'
        '3. Tap \u2699\ufe0f Settings to update your city or budget\n\n'
        'Tap \U0001f3e0 New to start reviewing:'
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=routing_keyboard(),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if context.user_data is not None:
        context.user_data.clear()

    await update.message.reply_text(
        'Cancelled. Use the buttons below to navigate.',
        reply_markup=routing_keyboard(),
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    user_profile = _ensure_user(update)
    chat_id = update.effective_chat.id
    stats = storage.get_user_stats(chat_id)

    city = user_profile['city'].title() if user_profile else 'Eindhoven'
    min_p = user_profile['min_price'] if user_profile else 400
    max_p = user_profile['max_price'] if user_profile else 1200

    text = (
        '\u2699\ufe0f Your Search Settings\n\n'
        f'\U0001f4cd City: {city}\n'
        f'\U0001f4b0 Budget: \u20ac{min_p} \u2014 \u20ac{max_p}\n\n'
        f'\U0001f4ca Status: {stats["new"]} new | {stats["accepted"]} accepted | {stats["rejected"]} rejected\n\n'
        'Tap \u270f\ufe0f Change Settings below to update your city and budget.'
    )

    await update.message.reply_text(text, reply_markup=settings_keyboard())


async def _show_listing(update, context, flow, listings):
    """Shared logic: show first listing from user's list and set context."""
    if not listings:
        if context.user_data is not None:
            context.user_data.pop('current_listing_id', None)
            context.user_data.pop('current_flow', None)

        labels = {'new': 'new listings', 'accepted': 'accepted listings', 'rejected': 'rejected listings'}
        if update.message:
            await update.message.reply_text(
                f'No {labels.get(flow, "listings")} to review.',
                reply_markup=routing_keyboard(),
            )
        return False

    listing = listings[0]
    if context.user_data is not None:
        context.user_data['current_listing_id'] = listing['listing_id']
        context.user_data['current_flow'] = flow

    icon = STATUS_ICONS.get(flow, '\U0001f3e0')

    if update.message:
        await update.message.reply_text(
            f'{format_listing(listing)}\nStatus: {icon} {flow.title()}',
            reply_markup=accept_reject_keyboard(),
        )
    return True


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    _ensure_user(update)
    listings = storage.get_listings_by_status('new', chat_id=update.effective_chat.id)
    await _show_listing(update, context, 'new', listings)


async def cmd_accepted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    _ensure_user(update)
    listings = storage.get_listings_by_status('accepted', chat_id=update.effective_chat.id)
    await _show_listing(update, context, 'accepted', listings)


async def cmd_rejected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    _ensure_user(update)
    listings = storage.get_listings_by_status('rejected', chat_id=update.effective_chat.id)
    await _show_listing(update, context, 'rejected', listings)


BUTTON_HANDLERS = {
    BTN_NEW: cmd_new,
    BTN_ACCEPTED: cmd_accepted,
    BTN_REJECTED: cmd_rejected,
    BTN_SETTINGS: cmd_settings,
    BTN_CHANGE_SETTINGS: start_onboarding_flow,
}


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.message.text:
        return

    text = update.message.text
    chat_id = update.effective_chat.id
    _ensure_user(update)

    handler = BUTTON_HANDLERS.get(text)
    if handler:
        await handler(update, context)
        return

    if text in (BTN_ACCEPT, BTN_REJECT):
        user_data = context.user_data if context.user_data is not None else {}
        listing_id = user_data.get('current_listing_id')
        flow = user_data.get('current_flow')

        if not listing_id or not flow:
            await update.message.reply_text(
                'No active listing to review. Tap \U0001f3e0 New to start.',
                reply_markup=routing_keyboard(),
            )
            return

        new_status = 'accepted' if text == BTN_ACCEPT else 'rejected'
        success = storage.update_status(listing_id, new_status, chat_id=chat_id)

        if not success:
            await update.message.reply_text(
                'Could not save your decision. Please try again.',
                reply_markup=accept_reject_keyboard(),
            )
            return

        remaining = storage.get_listings_by_status(flow, chat_id=chat_id)
        if remaining:
            await _show_listing(update, context, flow, remaining)
        else:
            if context.user_data is not None:
                context.user_data.pop('current_listing_id', None)
                context.user_data.pop('current_flow', None)

            labels = {
                'new': 'new listings',
                'accepted': 'accepted listings',
                'rejected': 'rejected listings',
            }
            await update.message.reply_text(
                f'All done! No more {labels.get(flow, "listings")}.',
                reply_markup=routing_keyboard(),
            )
    else:
        await update.message.reply_text(
            'Use the buttons below to navigate.',
            reply_markup=routing_keyboard(),
        )


def main():
    if not TOKEN:
        logger.error('TELEGRAM_BOT_TOKEN environment variable is not set')
        return

    default_chat_id = int(os.environ.get('TELEGRAM_CHAT_ID', 0)) or None
    storage.init_db(default_chat_id=default_chat_id)

    application = Application.builder().token(TOKEN).build()

    # Step-by-step Onboarding / Settings wizard
    onboarding_conv = ConversationHandler(
        entry_points=[
            CommandHandler('onboard', start_onboarding_flow),
            MessageHandler(filters.Regex(f'^{BTN_CHANGE_SETTINGS}$'), start_onboarding_flow),
        ],
        states={
            WAITING_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_onboard_city),
            ],
            WAITING_MIN_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_onboard_min_price),
            ],
            WAITING_MAX_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_onboard_max_price),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_onboarding),
            MessageHandler(filters.Regex(f'^{BTN_CANCEL}$'), cancel_onboarding),
        ],
    )

    application.add_handler(onboarding_conv)

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(CommandHandler('new', cmd_new))
    application.add_handler(CommandHandler('accepted', cmd_accepted))
    application.add_handler(CommandHandler('rejected', cmd_rejected))
    application.add_handler(CommandHandler('settings', cmd_settings))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info('Starting webhook on 0.0.0.0:%s', PORT)
    application.run_webhook(
        listen='0.0.0.0',
        port=PORT,
        url_path='webhook',
        webhook_url=f'{RENDER_URL}/webhook',
    )


if __name__ == '__main__':
    main()
