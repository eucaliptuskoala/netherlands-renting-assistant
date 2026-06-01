# parariusScraper.py — Scraper for pararius.com
# Pararius is another Dutch rental website (focuses exclusively on rentals, no sales).
# The structure is very similar to funda.py — same pattern, different CSS selectors.

import os                                   # Read environment variables (for ScrapingBee API key)
import re                                   # Regular expressions for extracting IDs and numbers from text
import requests                             # Standard HTTP — used for ScrapingBee API fallback
from curl_cffi import requests as curl_req  # Same curl-impersonate library as funda.py
from bs4 import BeautifulSoup               # HTML parser
from model import House                     # Data class for a listing
from interface import RentProviderInterface  # Parent class


class Pararius(RentProviderInterface):
    BASE = "https://www.pararius.com"  # Pararius base URL

    def __init__(self, city='amsterdam', price=[0, 9000], header={}):
        super().__init__(city, price)
        self._header = header or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def Run(self):
        """Scrape Pararius and return a list of House objects."""
        # Pararius allows price filtering directly in the URL (e.g. /apartments/eindhoven/400-1400)
        url = f"{self.BASE}/apartments/{self._city}/{self._min_price}-{self._max_price}"

        # In GitHub Actions, Cloudflare blocks all data-center IPs → curl_cffi always fails.
        # ScrapingBee handles proxy rotation and Cloudflare bypass natively.
        # Locally (at home), curl_cffi works fine, so we skip ScrapingBee to save credits.
        html = ''
        api_key = os.environ.get('SCRAPINGBEE_API_KEY')
        if api_key:
            print("    [debug] Pararius: using ScrapingBee...")
            r = requests.get('https://app.scrapingbee.com/api/v1/', params={
                'api_key': api_key,
                'url': url,
                'render_js': 'false',
            })
            if r.status_code == 200:
                html = r.text
                print(f"    [debug] Pararius (ScrapingBee): {len(html)} bytes")

        # No API key? Try curl_cffi directly (works from non-data-center IPs).
        if not html:
            for imp in ['chrome131', 'chrome124', 'chrome110', 'chrome99', 'safari15_3']:
                try:
                    r = curl_req.get(url, headers=self._header, impersonate=imp)
                except Exception as e:
                    print(f"    [debug] Pararius: {imp} not supported ({e})")
                    continue
                if len(r.text) > 20000:
                    html = r.text
                    break

            print(f"    [debug] Pararius (curl_cffi): {len(html)} bytes")

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
