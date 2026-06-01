# Fix scraper → bot flow

## Problem
Scraper sends individual listing messages (no buttons) AND a summary. Users can't interact with listings.

## Changes

### 1. `main.py` — remove individual messages
Replace the entire `process()` function and `sendToTelegram()` with this:

```python
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
```

Delete the `sendToTelegram` function entirely.

On line 71, change:
```python
total_new += process(seen_ids, houses, sendToTelegram)
```
to:
```python
total_new += process(seen_ids, houses)
```

The summary message at lines 76-84 stays as-is.

### 2. `bot.py` — clearer /start message
Replace the `/start` handler with:

```python
async def start(update: Update, context):
    await update.message.reply_text(
        "\U0001F3E0 Housing Monitor Bot\n\n"
        "I track new rental listings for you.\n\n"
        "How it works:\n"
        "1. You'll receive a summary when new listings appear\n"
        "2. Use /new to see them with Accept / Reject buttons\n"
        "3. Accepted = you're interested, Rejected = not interested\n"
        "4. Use /accepted or /rejected to review past decisions\n\n"
        "Commands:\n"
        "/new \u2014 review new listings\n"
        "/accepted \u2014 view accepted listings\n"
        "/rejected \u2014 view rejected listings"
    )
```

## Result after applying
1. Scraper stores listings in DB + sends one summary: "🏠 3 new listing(s) found — use /new to view"
2. User opens the bot, uses `/new` → listings appear with ✅ Accept / ❌ Reject buttons
3. Each button press updates status and removes buttons from the message
4. `/accepted` and `/rejected` show past decisions with ability to change status
