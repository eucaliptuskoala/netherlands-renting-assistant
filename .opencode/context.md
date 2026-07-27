# Netherlands Renting Assistant — Project Context

## What is it?
Scrapes Dutch rental websites (Funda.nl and Pararius.com) and sends new listings to Telegram. Built because the Dutch rental market moves fast — listings are gone within hours.

## Tech Stack
- **Language**: Python 3.11+
- **Scraping**: `curl_cffi` (TLS fingerprint impersonation) for Funda; ScrapingBee API + `curl_cffi` fallback for Pararius
- **Parsing**: BeautifulSoup + lxml
- **Storage**: PostgreSQL via Supabase (psycopg2)
- **Bot**: python-telegram-bot (webhook-based, deployed on Render)
- **Scheduling**: GitHub Actions cron (every 15 minutes)
- **Quality**: Ruff linter + mypy configured (June 2026), no tests yet

## Scraping Approaches

### Currently Used

| Approach | Where | How it works |
|----------|-------|-------------|
| `curl_cffi` TLS impersonation | Funda (primary), Pararius (fallback) | Mimics Chrome 131's TLS fingerprint at the C library level (libcurl-impersonate). Beats Akamai (Funda) and sometimes Cloudflare (Pararius). |
| ScrapingBee API | Pararius (primary) | Paid proxy-as-a-service that handles Cloudflare bypass. Works from data-center IPs (GitHub Actions). 1,000 free credits, then $49/mo. |
| Standard `requests` | ScrapingBee calls + Telegram notifications | No impersonation needed for API calls. |

### Architecture
- Interface → Scrapers → Model → Storage → Telegram
- Two entry points: `main.py` (cron scraper) and `bot.py` (interactive Telegram bot)
- Deduplication via Postgres upsert

### Key Files

| File | Role |
|------|------|
| `interface.py` | Abstract base class for all scrapers |
| `funda.py` | Funda scraper (curl_cffi, Akamai bypass) |
| `parariusScraper.py` | Pararius scraper (ScrapingBee + curl_cffi fallback) |
| `model.py` | House dataclass |
| `storage.py` | Supabase/Postgres CRUD |
| `main.py` | GitHub Actions entry point — scrape + notify |
| `bot.py` | Telegram webhook bot — interactive review |

## Future Scraping Options (if ScrapingBee credits run out)

Ranked by practicality for this codebase:

### 1. ScraperAPI (managed, free tier)
- **Free**: 5,000 req/mo, no credit card
- **Integration**: Prepend `http://api.scraperapi.com?api_key=...&url=` to target URL
- **Effort**: ~3 lines changed in `parariusScraper.py`
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

## Current Status (June 2026)
- All critical error-handling issues reviewed and fixed
- Ruff linter and mypy configured in pyproject.toml
- No tests yet
- Working on: code quality review implementation
