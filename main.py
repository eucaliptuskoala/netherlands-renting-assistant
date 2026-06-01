# main.py - Scraper entry point
# This runs inside GitHub Actions every 15 minutes (see .github/workflows/monitor.yml).
# It scrapes rental websites, stores new listings in Supabase, and sends you a Telegram summary.

import sys            # Used for printing errors to stderr (visible in GitHub Actions logs)
from datetime import datetime  # For timestamping log messages
import os             # To read TELEGRAM_CHAT_ID and TELEGRAM_BOT_TOKEN from environment variables

from dotenv import load_dotenv  # Loads .env file so we can test locally
import requests       # The standard Python HTTP library — used here to send Telegram notifications

load_dotenv()  # Make .env variables available to os.environ (does nothing in GitHub Actions — those use secrets)

# Our own modules:
from funda import Funda              # Funda scraper class
from parariusScraper import Pararius  # Pararius scraper class
import storage  # Database layer — functions to save/load listings from Supabase

# --- Configuration (change these for your city / budget) ---
AREA = "eindhoven"   # City to search in
PRICE = [400, 1400]  # Minimum and maximum monthly rent in euros
# Headers mimic a real browser so the rental sites don't block us as a bot
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


# --- Process newly scraped houses ---
def process(seen_ids, houses):
    """Check which houses are new (not already in the database) and store them."""
    new_count = 0
    for house in houses:                    # Each house is a House object (from model.py)
        listing_id = str(house.id)          # Unique ID from the rental site
        if listing_id in seen_ids:          # Skip if we already know about this one
            continue
        seen_ids.add(listing_id)            # Mark as seen for this run (avoid duplicates within the same run)
        storage.mark_seen(                  # Save to Supabase with status "new"
            listing_id,
            house.address,
            str(house.price),
            house.living_area,
            house.URL,
        )
        new_count += 1
    return new_count


# --- Script starts here ---
if __name__ == '__main__':
    # Step 1: Create scraper instances (one per rental website)
    svcs = [Funda, Pararius]         # Start with class references
    for idx, svc in enumerate(svcs):  # Replace each class with an instance
        svcs[idx] = svc(AREA, PRICE, header=HEADERS)

    # Step 2: Load all previously-seen listing IDs from Supabase
    # This returns a set (a fast lookup structure) so we can skip duplicates
    seen_ids = storage.load_seen_ids()
    print(f"[{datetime.now():%H:%M:%S}] Started ({len(seen_ids)} already seen)")

    # Step 3: Run each scraper and collect new listings
    total_new = 0
    try:
        for svc in svcs:
            print(f"[{datetime.now():%H:%M:%S}] Running {svc.__class__.__name__}...")
            houses = svc.Run()           # Scrape the website, returns a list of House objects
            total_new += process(seen_ids, houses)
            print(f"  -> {len(houses)} listings checked, {total_new} new so far")
    except Exception as e:
        # If anything goes wrong (network error, parsing failure, etc.), log it but don't crash
        print(f"[{datetime.now():%H:%M:%S}] Error: {e}", file=sys.stderr)

    # Step 4: If we found new listings, send a Telegram notification
    if total_new > 0:
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')  # Your Telegram user/chat ID
        token = os.environ.get('TELEGRAM_BOT_TOKEN')   # Bot token from @BotFather
        if chat_id and token:  # Only send if both are available
            url = f'https://api.telegram.org/bot{token}/sendMessage'
            # The message tells you how many new listings were found
            # Then you open the bot and tap 🏠 New to view them one by one
            requests.post(url, json={
                'chat_id': chat_id,
                'text': f'\U0001F3E0 {total_new} new listing(s) found \u2014 use /new to view',
            })
            # We don't check the response — if it fails, we just won't get notified this time
