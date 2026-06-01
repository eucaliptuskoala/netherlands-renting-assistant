# parariusScraper.py — Scraper for pararius.com
# Pararius is another Dutch rental website (focuses exclusively on rentals, no sales).
# The structure is very similar to funda.py — same pattern, different CSS selectors.

import re                                   # Regular expressions for extracting IDs and numbers from text
from curl_cffi import requests as curl_req  # Same curl-impersonate library as funda.py
from bs4 import BeautifulSoup               # HTML parser
from model import House                     # Data class for a listing
from interface import RentProviderInterface  # Parent class

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class Pararius(RentProviderInterface):
    BASE = "https://www.pararius.com"  # Pararius base URL

    def __init__(self, city='amsterdam', price=[0, 9000], header={}):
        super().__init__(city, price)
        self._header = header or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _fetch_with_playwright(self, url):
        """Fallback: use a real headless Chromium to bypass Cloudflare."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            # Block images/fonts/media/stylesheets — Cloudflare challenge doesn't need them,
            # and skipping them speeds up the page load significantly in CI.
            page.route('**/*', lambda route: route.abort()
                       if route.request.resource_type in ('image', 'font', 'media', 'stylesheet')
                       else route.continue_())
            page.goto(url, wait_until='load', timeout=90000)
            page.wait_for_timeout(5000)
            html = page.content()
            browser.close()
        return html

    def Run(self):
        """Scrape Pararius and return a list of House objects."""
        # Pararius allows price filtering directly in the URL (e.g. /apartments/eindhoven/400-1400)
        url = f"{self.BASE}/apartments/{self._city}/{self._min_price}-{self._max_price}"

        # Cloudflare in GH Actions sometimes blocks chrome131 but lets older fingerprints through.
        # We try multiple impersonations in order and use the first one that returns a real page (>20KB).
        html = ''
        used_impersonation = ''
        for imp in ['chrome131', 'chrome124', 'chrome110', 'chrome99', 'safari15_3']:
            try:
                r = curl_req.get(url, headers=self._header, impersonate=imp)
            except Exception as e:
                print(f"    [debug] Pararius: {imp} not supported ({e})")
                continue
            if len(r.text) > 20000:  # Real listing page is ~700KB; CAPTCHA page is ~6KB
                html = r.text
                used_impersonation = imp
                break

        print(f"    [debug] Pararius ({used_impersonation or 'none'}): {len(html)} bytes")

        # If curl_cffi couldn't get past Cloudflare, fall back to Playwright (real browser).
        if not html and HAS_PLAYWRIGHT:
            print("    [debug] Pararius: falling back to Playwright...")
            html = self._fetch_with_playwright(url)
            print(f"    [debug] Pararius (playwright): {len(html)} bytes")

        soup = BeautifulSoup(html, 'lxml') if html else BeautifulSoup('', 'lxml')

        ret = []
        # Pararius lists each item as an <li> with class "search-list__item search-list__item--listing"
        for listing in soup.find_all('li', class_='search-list__item search-list__item--listing'):
            # Title is inside an <h3 class="listing-search-item__title"> with an <a> inside
            title = listing.find('h3', class_='listing-search-item__title')
            if not title or not title.a:
                continue  # Skip if there's no title/URL

            href = title.a.get('href', '')        # Relative URL like "/apartments/eindhoven/abc123/..."
            full_url = self.BASE + href             # Build the full URL

            # Extract listing ID from URL pattern like /abcdef123456/street-name/
            # The ID is a hex string (a-f, 0-9) right before the last path segment
            m = re.search(r'/([a-f0-9]+)/[^/]+$', href.rstrip('/'))
            house_id = m.group(1) if m else href   # Fallback: whole URL as ID

            # Address is in <div class="listing-search-item__sub-title">
            loc = listing.find('div', class_='listing-search-item__sub-title')
            address = loc.get_text(strip=True) if loc else ''

            # Price is in <span class="listing-search-item__price-main">
            price_el = listing.find('span', class_='listing-search-item__price-main')
            price_text = price_el.get_text(strip=True) if price_el else '0'
            price = int(re.sub(r'[^0-9]', '', price_text))  # Remove "€", "," etc.

            # Skip if outside budget
            if not self._isPriceMatched(price):
                continue

            # Living area is the first item in a <ul class="illustrated-features">
            features = listing.find('ul', class_='illustrated-features')
            area = ''
            if features:
                items = features.find_all('li')
                if items:
                    area = items[0].get_text(strip=True)

            ret.append(House(house_id, full_url, address, price, area))

        return ret
