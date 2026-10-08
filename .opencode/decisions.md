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

## ADR-7: Scraper Resilience & Modern DOM Parsing (September 2026)

- **Context**: Funda deprecated its `/en/huur/` URL structure and redesigned listing cards, causing 404 errors and broken price extraction. Xior crawler crashed with unhandled JS `ReferenceError` when target scripts were delayed.
- **Decision**:
  1. Funda: switch to canonical `/huur/{city}/` endpoint and container-scoped price regex.
  2. Xior: use safe `window.xiorajax?.ajaxurl` property access inside Playwright evaluation.
  3. Pararius: provide transparent diagnostic logging for Cloudflare challenge responses.
- **Consequence**: Restored Funda listing discovery (15+ listings per run) and prevented crawler aborts on Xior.

## ADR-8: Context-Aware Keyboards & Listing Browse Pagination (October 2026)

- **Context**: When browsing accepted listings, users were presented with `[Accept, Reject]` buttons and no pagination controls. Tapping `Accept` re-applied the `accepted` status to the first item, querying `listings[0]` and causing an infinite duplicate loop on the same listing.
- **Decision**:
  1. Differentiate review vs. browse flows with dedicated keyboards (`new_listing_keyboard`, `browse_accepted_keyboard`, `browse_rejected_keyboard`).
  2. Implement index-based pagination (`current_index` + `➡️ Next`) for browsing saved collections.
  3. Gracefully handle taps on `Accept` in `accepted` mode by advancing to the next item instead of reloading the current one.
  4. Enforce `cur.rowcount > 0` checks in `storage.update_status()`.
- **Consequence**: Users can browse saved collections sequentially, change listing statuses without losing their position, and never get trapped in duplicate listing loops.

## ADR-9: Modular Package Architecture Reorganization (October 2026)

- **Context**: All modules were flat in the repository root (`model.py`, `interface.py`, 5 scrapers, `storage.py`), cluttering the workspace and obscuring domain boundaries.
- **Decision**:
  1. Organize code into domain packages: `models/` (`house.py`), `scrapers/` (`base.py`, providers), and `storage/` (`database.py`).
  2. Maintain `storage/__init__.py` re-exporting all database APIs to ensure 100% backward compatibility for existing callers.
  3. Keep `main.py` and `bot.py` at the root as entry points to avoid breaking Render and GitHub Actions configurations.
- **Consequence**: Clean, decoupled architecture with clear separation of responsibilities, ready for integrating new services (e.g. AI assistance).

## ADR-10: Gemini AI Cover Letter Generator & Applicant Bio Management (October 2026)

- **Context**: Dutch rental listings receive hundreds of responses within minutes. To secure a viewing, applicants need professional, tailored motivation letters in Dutch and English addressing makelaar requirements (income, guarantor, non-smoker, move-in readiness). Additionally, user applicant situations (student vs. expat professional) must be preserved in their profile.
- **Decision**:
  1. Add optional free-form `bio` column to `users` table via graceful auto-migration in `storage.init_db()` (`ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;`).
  2. Provide `📝 Edit Bio` within `⚙️ Settings` and via `/bio` command in Telegram, allowing users to freely describe their employment, income, and guarantor situation.
  3. Integrate Google GenAI SDK (`google-genai>=2.3.0`) with model cascading (`gemini-3.5-flash` -> `gemini-3.5-flash-lite` -> `gemini-3.8-flash`) in `services/ai_assistant.py` to ensure high availability and resistance to temporary 503 spikes.
  4. Prompt design: generate Dutch version first, English version second, both formatted in markdown code blocks for single-tap clipboard copying in Telegram.
  5. Add `✍️ Cover Letter` action button to `new_listing_keyboard` and `browse_accepted_keyboard` without mutating the user's active listing queue index.
- **Consequence**: Users can generate personalized, high-converting bilingual application letters in seconds with a single tap, drastically improving viewing invitation rates while keeping operational API costs essentially zero on Google AI's free tier.

## ADR-11: Modular Testing Suite with Unit and Integration Isolation (October 2026)

- **Context**: The application interacts with multiple external APIs and third-party systems (Google Gemini AI, Supabase PostgreSQL, Telegram Bot API, and real estate portals). Lack of structured tests risked silent regressions during scraper DOM shifts or schema updates.
- **Decision**:
  1. Adopt `pytest` and `pytest-mock` with explicit test markers (`unit` vs `integration`).
  2. Implement unit tests with comprehensive mocking to guarantee fast, 100% offline test execution:
     - `services/ai_assistant.py`: mock Gemini client, testing prompt construction, model cascading fallback on 503 errors, and missing key/bio handling.
     - `scrapers/`: mock HTTP responses to validate parser robustness (Vestide JSON, Funda HTML, price filters).
     - `main.py`: mock `requests.post` to validate Telegram notification status and exception handling.
     - `bot.py`: test formatting helpers and keyboard configurations.
  3. Implement integration tests verifying real API contracts against live external services:
     - `tests/integration/test_gemini_integration.py`: live validation of bilingual cover letter generation.
     - `tests/integration/test_storage_integration.py`: live connection and query verification against Supabase.
     - Both tests gracefully skip via `pytest.mark.skipif` when environment secrets are absent.
- **Consequence**: Full automated verification of core business flows and third-party API contracts, allowing rapid and safe evolution of scrapers and bot features.






