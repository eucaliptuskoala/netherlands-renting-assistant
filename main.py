import os
import sys
from collections import defaultdict
from datetime import datetime

import requests
from dotenv import load_dotenv

import storage
from scrapers import Funda, Kamernet, Pararius, Vestide, Xior

load_dotenv()

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}


def send_telegram_notification(token: str, chat_id: int, message: str) -> bool:
    """Send Telegram message to a specific chat_id."""
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    try:
        r = requests.post(
            url,
            json={'chat_id': chat_id, 'text': message},
            timeout=10,
        )
        if not r.ok:
            print(
                f'[{datetime.now():%H:%M:%S}] Telegram failed for chat {chat_id}: status {r.status_code} ({r.text})',
                file=sys.stderr,
            )
            return False
        return True
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] Telegram error for chat {chat_id}: {e}', file=sys.stderr)
        return False


def main():
    default_chat_id = int(os.environ.get('TELEGRAM_CHAT_ID', 0)) or None
    storage.init_db(default_chat_id=default_chat_id)

    active_users = storage.get_active_users()
    if not active_users and default_chat_id:
        owner = storage.get_or_create_user(default_chat_id, first_name='Owner', default_onboarded=True)
        if owner:
            active_users = [owner]

    if not active_users:
        print(f'[{datetime.now():%H:%M:%S}] No active onboarded users found. Exiting.')
        return

    print(f'[{datetime.now():%H:%M:%S}] Active onboarded users: {len(active_users)}')

    # Group users by exact search query to guarantee page-1 relevance
    query_users: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
    for u in active_users:
        city = (u.get('city') or 'eindhoven').strip().lower()
        min_p = int(u.get('min_price', 400))
        max_p = int(u.get('max_price', 1200))
        query_users[(city, min_p, max_p)].append(u)

    user_new_counts: dict[int, int] = defaultdict(int)

    for (city, min_price, max_price), target_users in query_users.items():
        price_range = [min_price, max_price]
        print(
            f'[{datetime.now():%H:%M:%S}] Searching {city.title()} for {len(target_users)} user(s) '
            f'with target budget {price_range}...'
        )

        svcs = [
            Funda(city, price_range, header=HEADERS),
            Kamernet(city, price_range, header=HEADERS),
            Pararius(city, price_range, header=HEADERS),
        ]

        if city == 'eindhoven':
            svcs.append(Vestide(city, price_range, header=HEADERS))
            svcs.append(Xior(city, price_range, header=HEADERS))

        city_houses = []
        for svc in svcs:
            print(f'[{datetime.now():%H:%M:%S}]   Running {svc.__class__.__name__} ({city.title()})...')
            try:
                houses = svc.Run()
                print(f'    -> Found {len(houses)} listings from {svc.__class__.__name__}')
                city_houses.extend(houses)
            except Exception as e:
                print(f'    [error] {svc.__class__.__name__} failed: {e}', file=sys.stderr)

        # Batch persistence in a single connection / transaction
        batch_counts = storage.save_and_assign_listings(city_houses, city, target_users)
        for chat_id, count in batch_counts.items():
            user_new_counts[chat_id] += count

    # Send notifications to each user who has new listings
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print(f'[{datetime.now():%H:%M:%S}] TELEGRAM_BOT_TOKEN not set, skipping notifications.')
        return

    for chat_id, count in user_new_counts.items():
        if count > 0:
            msg = f'\U0001f3e0 {count} new rental listing(s) found! Tap \U0001f3e0 New in the bot to review.'
            ok = send_telegram_notification(bot_token, chat_id, msg)
            if ok:
                print(f'[{datetime.now():%H:%M:%S}] Sent alert to chat {chat_id} ({count} new).')


if __name__ == '__main__':
    main()
