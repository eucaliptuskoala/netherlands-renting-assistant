# Netherlands Renting Assistant — Architecture Decisions

## ADR-1: Dual scraping strategy for Pararius (Retired September 2026 -> curl_cffi only)

- **Context**: Pararius uses Cloudflare, which blocks data-center IPs (GitHub Actions). Originally used ScrapingBee as primary and `curl_cffi` as fallback.
- **Decision**: In September 2026, ScrapingBee was completely retired due to credit exhaustion and dependency cleanup. Pararius now exclusively uses `curl_cffi` with a multi-profile TLS impersonation loop (Chrome 131, 124, 110, 99 and Safari 15.3).
- **Consequence**: Zero cost, no external paid API dependency or API keys in GitHub Secrets.

## ADR-2: curl_cffi over requests/httpx for TLS impersonation

- **Context**: Funda uses Akamai, which fingerprints TLS handshakes. Standard `requests` and `httpx` have distinct TLS signatures that are blocked immediately.
- **Decision**: Use `curl_cffi` which links `libcurl-impersonate` to produce TLS handshakes byte-identical to real Chrome/Firefox/Safari.
- **Consequence**: Funda scraping works. Adds a compiled C dependency (`libcurl-impersonate`) which can cause install issues on some platforms.

## ADR-3: BeautifulSoup over lxml.html / selectolax / parsing APIs

- **Context**: Need to parse HTML from rental sites. Options: BeautifulSoup (slow, forgiving), lxml.html (fast, strict), selectolax (fastest, limited), or managed parsing APIs.
- **Decision**: BeautifulSoup + lxml backend. Forgiving parser handles malformed HTML from rental sites. lxml backend keeps speed acceptable.
- **Consequence**: Simple, well-known, but slower than selectolax for very large pages (not an issue at this scale).

## ADR-4: psycopg2 over SQLAlchemy / Supabase SDK

- **Context**: Need Postgres access for Supabase. Options: raw psycopg2, SQLAlchemy ORM, Supabase Python SDK.
- **Decision**: psycopg2-binary. The schema is a single table with simple CRUD. An ORM would add complexity without benefit. The Supabase SDK adds network overhead (REST) vs direct Postgres connection.
- **Consequence**: Simple, fast, minimal dependencies. Manual SQL means more verbose code for complex queries (not an issue here).

## ADR-5: Multi-User Architecture & Normalized Schema (September 2026)

- **Context**: The original implementation was single-user: `seen_listings` combined listing metadata with user status (`new`/`accepted`/`rejected`), scraping filters were hardcoded in `main.py`, and Telegram alerts only went to one chat. Adding a second user (or N users) required isolating decisions, supporting custom search filters (city, budget), and delivering personalized alerts without losing existing listing data.
- **Decision**:
  1. Keep `seen_listings` as a global master catalog of scraped listings.
  2. Add `users` table for user profiles and preferences (`telegram_chat_id`, `city`, `min_price`, `max_price`, `is_active`).
  3. Add `user_listings` junction table (`user_id`, `listing_id`, `status`, `notified`) with unique constraint on `(user_id, listing_id)`.
  4. Perform zero-data-loss backfill of existing `seen_listings` into `user_listings` for the owner.
  5. Multi-user scraper in `main.py`: aggregates search queries by city/price bounds, matches listings per user, and dispatches individual Telegram notifications.
- **Consequence**: Enables independent, concurrent users with individual preferences and decision queues while 100% preserving historical data.

## ADR-6: Step-by-Step Onboarding Wizard & Batched Persistence (September 2026)

- **Context**: Architectural review identified two operational risks: (1) high database connection churn due to opening a new TLS connection for every individual listing and user match, (2) wide price range aggregation starving users with higher budgets on single-page scrapers, and (3) awkward UX requiring manual command entry for setting city and budget.
- **Decision**:
  1. Introduce `ConversationHandler` in `bot.py` for guided onboarding (`city` -> `min_price` -> `max_price`), reusable via `⚙️ Settings` -> `✏️ Change Settings`.
  2. Add `is_onboarded` flag on `users` table so unconfigured profiles are excluded from scraper runs.
  3. Implement `save_and_assign_listings()` in `storage.py` to persist all catalog entries and user assignments within a single database connection and transaction.
  4. Partition scraper queries by exact user budget profiles `(city, min_price, max_price)` in `main.py` rather than an all-inclusive outer envelope.
- **Consequence**: Drastically reduced database latency/connections, eliminated page-1 result starvation for differing budgets, and created an intuitive button-driven setup experience.


