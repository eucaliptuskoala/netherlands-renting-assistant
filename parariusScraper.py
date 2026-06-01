# parariusScraper.py — Scraper for pararius.com
# Pararius is another Dutch rental website (focuses exclusively on rentals, no sales).
# The structure is very similar to funda.py — same pattern, different CSS selectors.

import re                                   # Regular expressions for extracting IDs and numbers from text
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
        r = curl_req.get(url, headers=self._header, impersonate='chrome131')  # Bypasses Pararius' Cloudflare detection
        print(f"    [debug] Pararius response: {len(r.text)} bytes, first 200: {r.text[:200].strip()!r}")
        soup = BeautifulSoup(r.text, 'lxml')

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
