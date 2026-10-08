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

import services
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

BTN_ACCEPT = '✅ Accept'
BTN_REJECT = '❌ Reject'
BTN_NEXT = '➡️ Next'
BTN_MENU = '🏠 Main Menu'
BTN_MOVE_REJECTED = '❌ Move to Rejected'
BTN_MOVE_ACCEPTED = '✅ Move to Accepted'
BTN_COVER_LETTER = '✍️ Cover Letter'
BTN_EDIT_BIO = '📝 Edit Bio'


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
            [KeyboardButton(BTN_CHANGE_SETTINGS), KeyboardButton(BTN_EDIT_BIO)],
            [KeyboardButton(BTN_NEW), KeyboardButton(BTN_ACCEPTED), KeyboardButton(BTN_REJECTED)],
        ],
        resize_keyboard=True,
    )


def new_listing_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_ACCEPT), KeyboardButton(BTN_REJECT)],
            [KeyboardButton(BTN_COVER_LETTER), KeyboardButton(BTN_MENU)],
        ],
        resize_keyboard=True,
    )


def browse_accepted_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_NEXT), KeyboardButton(BTN_MOVE_REJECTED)],
            [KeyboardButton(BTN_COVER_LETTER), KeyboardButton(BTN_MENU)],
        ],
        resize_keyboard=True,
    )


def browse_rejected_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_NEXT), KeyboardButton(BTN_MOVE_ACCEPTED)],
            [KeyboardButton(BTN_MENU)],
        ],
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
    bio = user_profile.get('bio') if user_profile else None
    bio_display = f'"{bio}"' if bio else 'Not set yet (tap 📝 Edit Bio below)'

    text = (
        '⚙️ Your Search Settings\n\n'
        f'📍 City: {city}\n'
        f'💰 Budget: €{min_p} — €{max_p}\n'
        f'📝 Bio: {bio_display}\n\n'
        f'📊 Status: {stats["new"]} new | {stats["accepted"]} accepted | {stats["rejected"]} rejected\n\n'
        'Tap ✏️ Change Settings to change city/budget, or 📝 Edit Bio to update your applicant profile.'
    )

    await update.message.reply_text(text, reply_markup=settings_keyboard())


async def cmd_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    user_profile = _ensure_user(update)
    current_bio = user_profile.get('bio') if user_profile else None
    current_bio_text = f'\n\nCurrently set to:\n_{current_bio}_' if current_bio else ''

    if context.user_data is not None:
        context.user_data['waiting_for_bio'] = True

    msg = (
        '📝 *Applicant Bio / Profile*\n\n'
        'Tell makelaars and landlords about yourself: your occupation/studies, '
        'monthly income or guarantor, who is moving in, and any pets or smoking status.\n\n'
        '💡 *Example:*\n'
        '_"Master student at TU/e, quiet, non-smoker, no pets. Parents provide financial guarantee for the rent."_'
        f'{current_bio_text}\n\n'
        'Send your bio text below, or tap ❌ Cancel:'
    )

    await update.message.reply_text(
        msg,
        reply_markup=cancel_keyboard(),
        parse_mode='Markdown',
    )


async def _show_listing(update, context, flow, listings, index=0):
    """Shared logic: show listing at index from user's list and set context."""
    if not listings or index >= len(listings):
        if context.user_data is not None:
            context.user_data.pop('current_listing_id', None)
            context.user_data.pop('current_flow', None)
            context.user_data.pop('current_index', None)

        labels = {
            'new': 'new listings',
            'accepted': 'accepted listings',
            'rejected': 'rejected listings',
        }
        if update.message:
            msg = (
                'All caught up! No new listings to review.'
                if flow == 'new'
                else f'End of {labels.get(flow, "listings")}.'
            )
            await update.message.reply_text(
                msg,
                reply_markup=routing_keyboard(),
            )
        return False

    listing = listings[index]
    if context.user_data is not None:
        context.user_data['current_listing_id'] = listing['listing_id']
        context.user_data['current_flow'] = flow
        context.user_data['current_index'] = index

    icon = STATUS_ICONS.get(flow, '🏠')
    total = len(listings)
    counter = f' ({index + 1}/{total})' if total > 1 else ''

    if flow == 'new':
        markup = new_listing_keyboard()
    elif flow == 'accepted':
        markup = browse_accepted_keyboard()
    elif flow == 'rejected':
        markup = browse_rejected_keyboard()
    else:
        markup = routing_keyboard()

    if update.message:
        await update.message.reply_text(
            f'{format_listing(listing)}\nStatus: {icon} {flow.title()}{counter}',
            reply_markup=markup,
        )
    return True


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    _ensure_user(update)
    listings = storage.get_listings_by_status('new', chat_id=update.effective_chat.id)
    await _show_listing(update, context, 'new', listings, index=0)


async def cmd_accepted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    _ensure_user(update)
    listings = storage.get_listings_by_status('accepted', chat_id=update.effective_chat.id)
    await _show_listing(update, context, 'accepted', listings, index=0)


async def cmd_rejected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    _ensure_user(update)
    listings = storage.get_listings_by_status('rejected', chat_id=update.effective_chat.id)
    await _show_listing(update, context, 'rejected', listings, index=0)


BUTTON_HANDLERS = {
    BTN_NEW: cmd_new,
    BTN_ACCEPTED: cmd_accepted,
    BTN_REJECTED: cmd_rejected,
    BTN_SETTINGS: cmd_settings,
    BTN_CHANGE_SETTINGS: start_onboarding_flow,
    BTN_EDIT_BIO: cmd_bio,
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

    if context.user_data and context.user_data.get('waiting_for_bio'):
        if text == BTN_CANCEL or text == '/cancel':
            context.user_data.pop('waiting_for_bio', None)
            await update.message.reply_text(
                'Bio edit cancelled.',
                reply_markup=settings_keyboard(),
            )
            return

        bio_text = text.strip()
        storage.update_user_bio(chat_id, bio_text)
        context.user_data.pop('waiting_for_bio', None)

        await update.message.reply_text(
            '✅ Applicant bio updated successfully!\n\n'
            'Gemini will now tailor your cover letters using your profile information.',
            reply_markup=settings_keyboard(),
        )
        return

    if text == BTN_MENU:
        if context.user_data is not None:
            context.user_data.pop('current_listing_id', None)
            context.user_data.pop('current_flow', None)
            context.user_data.pop('current_index', None)
        await update.message.reply_text(
            'Main Menu:',
            reply_markup=routing_keyboard(),
        )
        return

    user_data = context.user_data if context.user_data is not None else {}
    listing_id = user_data.get('current_listing_id')
    flow = user_data.get('current_flow')
    index = user_data.get('current_index', 0)

    # Cover Letter generation with Gemini
    if text == BTN_COVER_LETTER:
        if not listing_id:
            await update.message.reply_text(
                'No active listing selected. Tap 🏠 New or ✅ Accepted to open a listing first.',
                reply_markup=routing_keyboard(),
            )
            return

        listing = storage.get_listing(listing_id)
        if not listing:
            await update.message.reply_text(
                'Listing details could not be found.',
                reply_markup=routing_keyboard(),
            )
            return

        user_profile = storage.get_or_create_user(chat_id)
        status_msg = await update.message.reply_text('✍️ Generating cover letter with Gemini...')

        cover_letter = services.generate_cover_letter(user_profile, listing)

        if flow == 'new':
            markup = new_listing_keyboard()
        elif flow == 'accepted':
            markup = browse_accepted_keyboard()
        elif flow == 'rejected':
            markup = browse_rejected_keyboard()
        else:
            markup = routing_keyboard()

        try:
            await status_msg.delete()
        except Exception:
            pass

        try:
            await update.message.reply_text(
                cover_letter,
                parse_mode='Markdown',
                reply_markup=markup,
            )
        except Exception:
            await update.message.reply_text(
                cover_letter,
                reply_markup=markup,
            )
        return

    # 1. Handling Next in browse mode (accepted / rejected)
    if text == BTN_NEXT:
        if not flow or flow not in ('accepted', 'rejected'):
            await update.message.reply_text(
                'No active list to browse. Tap 🏠 New to start.',
                reply_markup=routing_keyboard(),
            )
            return

        listings = storage.get_listings_by_status(flow, chat_id=chat_id)
        next_index = index + 1
        await _show_listing(update, context, flow, listings, index=next_index)
        return

    # 2. Handling New flow (Accept / Reject)
    if flow == 'new' and text in (BTN_ACCEPT, BTN_REJECT):
        if not listing_id:
            await update.message.reply_text(
                'No active listing to review. Tap 🏠 New to start.',
                reply_markup=routing_keyboard(),
            )
            return

        new_status = 'accepted' if text == BTN_ACCEPT else 'rejected'
        success = storage.update_status(listing_id, new_status, chat_id=chat_id)

        if not success:
            await update.message.reply_text(
                'Could not save your decision. Please try again.',
                reply_markup=new_listing_keyboard(),
            )
            return

        remaining = storage.get_listings_by_status('new', chat_id=chat_id)
        await _show_listing(update, context, 'new', remaining, index=0)
        return

    # 3. Handling Accepted flow
    if flow == 'accepted':
        if text in (BTN_MOVE_REJECTED, BTN_REJECT):
            if listing_id:
                storage.update_status(listing_id, 'rejected', chat_id=chat_id)
            remaining = storage.get_listings_by_status('accepted', chat_id=chat_id)
            await _show_listing(update, context, 'accepted', remaining, index=index)
            return

        # If user taps Accept while already in accepted, treat it gracefully as Next
        if text == BTN_ACCEPT:
            listings = storage.get_listings_by_status('accepted', chat_id=chat_id)
            next_index = index + 1
            await _show_listing(update, context, 'accepted', listings, index=next_index)
            return

    # 4. Handling Rejected flow
    if flow == 'rejected':
        if text in (BTN_MOVE_ACCEPTED, BTN_ACCEPT):
            if listing_id:
                storage.update_status(listing_id, 'accepted', chat_id=chat_id)
            remaining = storage.get_listings_by_status('rejected', chat_id=chat_id)
            await _show_listing(update, context, 'rejected', remaining, index=index)
            return

        # If user taps Reject while already in rejected, treat it gracefully as Next
        if text == BTN_REJECT:
            listings = storage.get_listings_by_status('rejected', chat_id=chat_id)
            next_index = index + 1
            await _show_listing(update, context, 'rejected', listings, index=next_index)
            return

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
    application.add_handler(CommandHandler('bio', cmd_bio))

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
