# Netherlands Renting Assistant — Project Context

## What is it?
Scrapes Dutch rental websites (Funda.nl and Pararius.com) and sends new listings to Telegram. Built because the Dutch rental market moves fast — listings are gone within hours.

## Tech Stack
- **Language**: Python 3.11+
- **Scraping**: `curl_cffi` (TLS fingerprint impersonation) for Funda, Pararius, Kamernet, Vestide; Playwright Chromium for Xior
- **Parsing**: BeautifulSoup + lxml
- **Storage**: PostgreSQL via Supabase (psycopg2)
- **Bot**: python-telegram-bot (webhook-based, deployed on Render)
- **Scheduling**: GitHub Actions cron (every 15 minutes)
- **Quality**: Ruff linter + mypy configured

## Scraping Approaches

### Currently Used

| Approach | Where | How it works |
|----------|-------|-------------|
| `curl_cffi` TLS impersonation | Funda, Pararius, Kamernet, Vestide | Mimics Chrome/Safari TLS fingerprints at the C library level (libcurl-impersonate). Beats Akamai and Cloudflare. |
| Playwright Chromium | Xior | Headless browser for JavaScript/Yardi room availability API extraction. |
| Standard `requests` | Telegram notifications | Simple HTTP POST to Telegram Bot API. |

### Architecture
- Interface → Scrapers → Model → Storage → Telegram
- Two entry points: `main.py` (cron scraper) and `bot.py` (interactive Telegram bot)
- Deduplication via Postgres upsert

### Key Packages & Files

| Path | Role |
|------|------|
| `main.py` | GitHub Actions entry point — scrape + notify |
| `bot.py` | Telegram webhook bot (Render) — interactive review |
| `models/` | Data models (`models/house.py`) |
| `scrapers/` | Scraper package (`base.py`, `funda.py`, `kamernet.py`, `pararius.py`, `vestide.py`, `xior.py`) |
| `storage/` | Database package (`storage/database.py`, backward-compatible re-exports in `storage/__init__.py`) |

## Future Scraping Options (if ScrapingBee credits run out)

Ranked by practicality for this codebase:

### 1. ScraperAPI (managed, free tier)
- **Free**: 5,000 req/mo, no credit card
- **Integration**: Prepend `http://api.scraperapi.com?api_key=...&url=` to target URL
- **Effort**: ~3 lines changed in `pararius.py`
- **Pro**: Same pattern as ScrapingBee, pay only for success, largest free tier
- **Con**: JS rendering costs 5x credits

### 2. Scrapling (Python library, free)
- **Free**: Zero cost, runs locally on GitHub Actions runner
- **Integration**: Swap `curl_cffi` for `scrapling.StealthyFetcher` in Pararius
- **Effort**: Add dependency + replace the HTTP call
- **Pro**: No API key, solves Cloudflare Turnstile, same pattern as curl_cffi
- **Con**: May still fail from data-center IPs on aggressive Cloudflare configs

### 3. Wick (self-hosted proxy, free)
- **Free**: Unlimited local usage, $20/mo Pro for JS rendering
- **Integration**: Run as local HTTP API, point scraper at `http://localhost:...`
- **Effort**: Add subprocess/health check in `main.py`
- **Pro**: Chrome's real TLS fingerprint (Cronet), claimed 100% on Cloudflare/Akamai
- **Con**: Requires Chromium binary (~300MB) on the runner

### 4. limit-break (self-hosted gateway, free)
- **Free**: Deploy on Render/Fly free tier
- **Integration**: Self-hosted gateway with curl_cffi + FlareSolverr + browser fallback
- **Effort**: Deploy separately, change URL prefix in scraper
- **Pro**: Full auto-escalation chain, built-in dashboard
- **Con**: Infrastructure to maintain

### 5. Crawlbase (managed, cheap)
- **Free**: 1,000 req, then $29/mo for 20K req
- **Integration**: Same pattern as ScrapingBee
- **Pro**: Cheapest paid entry at $29/mo

## Current Status (September 2026)
- Multi-user architecture implemented and verified:
  - Database schema normalized (`users`, `user_listings`, and master catalog `seen_listings`).
  - Historical data (530 listings) 100% migrated to owner's profile with zero data loss.
  - Step-by-step onboarding conversation wizard in Telegram bot (`bot.py`) for new users and reusable via `⚙️ Settings` -> `✏️ Change Settings`.
  - Batched database persistence (`save_and_assign_listings`) in a single connection & transaction.
  - Scraper runs partitioned by exact user budget profiles to eliminate page-1 starvation.
- Scraper robustness fixes:
  - Funda: resolved HTTP 404 by migrating URL from deprecated `/en/huur/` to `/huur/`; updated price parsing to use container-scoped regex matching modern DOM cards.
  - Xior: resolved `ReferenceError` crash by switching bare identifier lookup to `window.xiorajax?.ajaxurl`.
  - Pararius: improved telemetry to clearly log Cloudflare challenge/status codes on datacenter runners.
- Bot navigation & listing review fixes (October 2026):
  - Fixed infinite loop when accepting already accepted listings by adding dedicated contextual keyboards (`browse_accepted_keyboard`, `browse_rejected_keyboard`, `new_listing_keyboard`).
  - Added index-based pagination (`current_index` + `➡️ Next`) for browsing saved listings without getting trapped on the first item.
  - Hardened `storage.update_status()` to check `cur.rowcount > 0`.
- Codebase reorganization into modular domain packages (October 2026):
  - Created `models/` (`house.py`), `scrapers/` (`base.py`, `funda.py`, `kamernet.py`, `pararius.py`, `vestide.py`, `xior.py`), and `storage/` (`database.py`).
  - Root entry points `main.py` and `bot.py` preserved for Render and GitHub Actions compatibility.
- Quality tooling: Ruff linter + mypy passing cleanly across all files.
- Next steps: Implement Gemini AI Cover Letter Generator (`services/ai_assistant.py`) and user bio management.


