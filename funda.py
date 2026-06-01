# funda.py — Scraper for funda.nl
# Funda is the largest Dutch rental/sale website.
# This class scrapes the rental listings page, parses the HTML, and extracts listing details.

from curl_cffi import requests as curl_req  # Special HTTP library that mimics browser TLS fingerprints
from bs4 import BeautifulSoup               # HTML parser — makes it easy to find elements by CSS/tags
import re                                   # Regular expressions — used to extract numbers from text
from model import House                     # Our simple data class for a listing
from interface import RentProviderInterface  # Parent class that ensures all scrapers have the same structure


class Funda(RentProviderInterface):
    BASE = "https://www.funda.nl"  # The website's base URL — all paths start with this

    def __init__(self, city='amsterdam', price=[0, 9000], header={}):
        super().__init__(city, price)  # Call parent __init__ to set city, min_price, max_price
        self._header = header or {      # HTTP headers that make our request look like a real browser
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def Run(self):
        """Scrape Funda and return a list of House objects."""
        url = f"{self.BASE}/en/huur/{self._city}/"  # Funda's rental URL for the city (e.g. /en/huur/eindhoven/)
        r = curl_req.get(url, headers=self._header, impersonate='chrome131')  # Bypasses Funda's Akamai bot detection
        soup = BeautifulSoup(r.text, 'lxml')  # Parse HTML with the fast lxml parser

        ret = []
        # Funda renders each listing with an <a data-testid="listingDetailsAddress"> link.
        # Finding links directly is more robust than guessing container classes.
        for link in soup.select('a[data-testid="listingDetailsAddress"]'):
            href = link.get('href', '')        # Relative URL like "/en/huur/eindhoven/abc123/..."
            full_url = self.BASE + href         # Full URL like "https://funda.nl/en/huur/eindhoven/abc123/..."

            # Extract a unique listing ID from the URL (the last path segment before any trailing slash)
            house_id = href.rstrip('/').rsplit('/', 1)[-1]

            # Address is inside a <span> within the link (no more "truncate" class — just find any span)
            addr_span = link.find('span')
            address = addr_span.get_text(strip=True) if addr_span else ''

            # Walk up 4 parent levels from the <a> tag to reach the listing container div
            # The hierarchy is: a > h2 > div.flex.flex-col > div.flex > div.\@container.border-b
            container = link
            for _ in range(4):
                container = container.parent

            # Price is inside the container, usually in a <div class="mt-2"> with text like "€ 1,600 /maand"
            price = 0
            price_div = container.find('div', class_=lambda c: c and 'mt-2' in (c if isinstance(c, str) else ' '.join(c)))
            if price_div:
                price_match = re.search(r'€\s*([0-9,.]+)', price_div.get_text())
                if price_match:
                    price = int(re.sub(r'[^0-9]', '', price_match.group(1)))  # Remove € , . /maand etc.

            # Check if this price is within our configured range
            if not self._isPriceMatched(price):
                continue  # Skip listings outside our budget

            # Living area is shown as "XX m²" somewhere in the container text
            living_area = ''
            area_match = re.search(r'(\d+)\s*m[²2]', container.get_text())
            if area_match:
                living_area = area_match.group(0)  # e.g. "47 m²"

            # Add the listing to our results
            ret.append(House(house_id, full_url, address, price, living_area))

        return ret  # Return all qualifying listings
