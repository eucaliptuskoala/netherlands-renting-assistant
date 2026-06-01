import sys
from datetime import datetime
import os

from dotenv import load_dotenv
import requests

load_dotenv()

from funda import Funda
from parariusScraper import Pararius
import storage

AREA = "eindhoven"
PRICE = [400, 1400]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


def process(seen_ids, houses):
    new_count = 0
    for house in houses:
        listing_id = str(house.id)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)
        storage.mark_seen(listing_id, house.address, str(house.price), house.living_area, house.URL)
        new_count += 1
    return new_count


if __name__ == '__main__':
    svcs = [Funda, Pararius]
    for idx, svc in enumerate(svcs):
        svcs[idx] = svc(AREA, PRICE, header=HEADERS)

    seen_ids = storage.load_seen_ids()
    print(f"[{datetime.now():%H:%M:%S}] Started ({len(seen_ids)} already seen)")

    total_new = 0
    try:
        for svc in svcs:
            print(f"[{datetime.now():%H:%M:%S}] Running {svc.__class__.__name__}...")
            houses = svc.Run()
            total_new += process(seen_ids, houses)
            print(f"  -> {len(houses)} listings checked, {total_new} new so far")
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] Error: {e}", file=sys.stderr)

    if total_new > 0:
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if chat_id and token:
            url = f'https://api.telegram.org/bot{token}/sendMessage'
            requests.post(url, json={
                'chat_id': chat_id,
                'text': f'\U0001F3E0 {total_new} new listing(s) found \u2014 use /new to view',
            }) 
