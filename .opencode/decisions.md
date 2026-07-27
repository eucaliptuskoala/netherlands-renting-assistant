# Netherlands Renting Assistant — Architecture Decisions

## ADR-1: Dual scraping strategy for Pararius (ScrapingBee + curl_cffi fallback)

- **Context**: Pararius uses Cloudflare, which blocks data-center IPs (GitHub Actions). `curl_cffi` works from residential IPs but fails on data-center IPs. ScrapingBee handles Cloudflare from data-center IPs but costs money.
- **Decision**: Use ScrapingBee when an API key is available (GitHub Actions), fall back to `curl_cffi` with multiple impersonation profiles when it isn't (local dev). The fallback iterates through Chrome 131, 124, 110, 99 and Safari 15.3 until one returns content >20KB.
- **Consequence**: Works everywhere without hard dependency on a paid service. ScrapingBee credits are conserved when running locally.

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
