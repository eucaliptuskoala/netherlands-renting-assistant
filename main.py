import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

import storage
from funda import Funda
from kamernet import Kamernet
from parariusScraper import Pararius
from vestide import Vestide
from xior import Xior

AREA = "eindhoven"
PRICE = [400, 1200]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


def process(seen_ids, houses):
    new_count = 0
    persisted_count = 0
    for house in houses:
        listing_id = str(house.id)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)
        ok = storage.mark_seen(
            listing_id,
            house.address,
            str(house.price),
            house.living_area,
            house.URL,
        )
        new_count += 1
        if ok:
            persisted_count += 1
    return new_count, persisted_count


if __name__ == "__main__":
    svcs = [
        Funda(AREA, PRICE, header=HEADERS),
        Kamernet(AREA, PRICE, header=HEADERS),
        Pararius(AREA, PRICE, header=HEADERS),
        Vestide(AREA, PRICE, header=HEADERS),
        Xior(AREA, PRICE, header=HEADERS),
    ]

    seen_ids = storage.load_seen_ids()
    print(f"[{datetime.now():%H:%M:%S}] Started ({len(seen_ids)} already seen)")

    total_new = 0
    total_persisted = 0
    try:
        for svc in svcs:
            print(f"[{datetime.now():%H:%M:%S}] Running {svc.__class__.__name__}...")
            houses = svc.Run()
            new_found, persisted = process(seen_ids, houses)
            total_new += new_found
            total_persisted += persisted
            print(f"  -> {len(houses)} listings checked, {new_found} new")
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] Error: {e}", file=sys.stderr)

    if total_persisted == 0 and total_new > 0:
        print(f"[{datetime.now():%H:%M:%S}] DB unavailable — skipping Telegram notification", file=sys.stderr)
    elif total_new > 0:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if chat_id and token:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            try:
                r = requests.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": f"\U0001f3e0 {total_new} new listing(s) found \u2014 use /new to view",
                    },
                    timeout=10,
                )
                if not r.ok:
                    print(f"[{datetime.now():%H:%M:%S}] Telegram notification failed: {r.status_code}", file=sys.stderr)
            except Exception as e:
                print(f"[{datetime.now():%H:%M:%S}] Telegram notification error: {e}", file=sys.stderr)
