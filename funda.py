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
        # Funda lists each listing inside a <div> that has "border-b" in its CSS class
        for listing in soup.select('div[class*="border-b"]'):
            # Each listing has an <a> tag with data-testid="listingDetailsAddress"
            link = listing.find('a', attrs={"data-testid": "listingDetailsAddress"})
            if not link:
                continue  # No link means this isn't a real listing — skip it

            href = link.get('href', '')        # Relative URL like "/en/huur/eindhoven/abc123/..."
            full_url = self.BASE + href         # Full URL like "https://funda.nl/en/huur/eindhoven/abc123/..."

            # Extract a unique listing ID from the URL (the last path segment before any trailing slash)
            house_id = href.rstrip('/').rsplit('/', 1)[-1]

            # Address is inside a <span class="truncate"> within the link
            addr_tag = link.find('span', class_='truncate')
            address = addr_tag.get_text(strip=True) if addr_tag else ''

            # Price is inside a <div class="truncate"> that contains "€"
            price = 0
            for d in listing.find_all('div', class_='truncate'):
                t = d.get_text(strip=True)
                if '\u20AC' in t:           # Found the price element
                    price = int(re.sub(r'[^0-9]', '', t.split('/')[0]))  # Remove everything except digits
                    break

            # Check if this price is within our configured range
            if not self._isPriceMatched(price):
                continue  # Skip listings outside our budget

            # Living area is the first item in a <ul class="gap-3"> list
            feature_items = listing.select('ul[class*="gap-3"] li')
            features = [li.get_text(strip=True) for li in feature_items]
            living_area = features[0] if features else ''

            # Add the listing to our results
            ret.append(House(house_id, full_url, address, price, living_area))

        return ret  # Return all qualifying listings
