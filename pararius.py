import os
import re

import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_req

from interface import RentProviderInterface
from model import House


class Pararius(RentProviderInterface):
    BASE = "https://www.pararius.com"

    def __init__(self, city="amsterdam", price=[0, 9000], header=None):
        super().__init__(city, price)
        self._header = header or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def Run(self):
        url = f"{self.BASE}/apartments/{self._city}/{self._min_price}-{self._max_price}"

        html = ""
        api_key = os.environ.get("SCRAPINGBEE_API_KEY")
        if api_key:
            print("    [debug] Pararius: using ScrapingBee...")
            try:
                r = requests.get(
                    "https://app.scrapingbee.com/api/v1/",
                    params={
                        "api_key": api_key,
                        "url": url,
                        "render_js": "false",
                    },
                )
                if r.status_code == 200:
                    html = r.text
                    print(f"    [debug] Pararius (ScrapingBee): {len(html)} bytes")
            except Exception as e:
                print(f"    [error] Pararius ScrapingBee failed: {e}")

        if not html:
            for imp in ["chrome131", "chrome124", "chrome110", "chrome99", "safari15_3"]:
                try:
                    r = curl_req.get(url, headers=self._header, impersonate=imp)
                except Exception as e:
                    print(f"    [debug] Pararius: {imp} not supported ({e})")
                    continue
                if len(r.text) > 20000:
                    html = r.text
                    break

            print(f"    [debug] Pararius (curl_cffi): {len(html)} bytes")

        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")

        ret = []
        for listing in soup.find_all("li", class_="search-list__item search-list__item--listing"):
            title = listing.find("h3", class_="listing-search-item__title")
            if not title or not title.a:
                continue

            href = title.a.get("href", "")
            full_url = self.BASE + href

            m = re.search(r"/([a-f0-9]+)/[^/]+$", href.rstrip("/"))
            house_id = m.group(1) if m else href

            loc = listing.find("div", class_="listing-search-item__sub-title")
            address = loc.get_text(strip=True) if loc else ""

            price_el = listing.find("span", class_="listing-search-item__price-main")
            price_text = price_el.get_text(strip=True) if price_el else "0"
            price = int(re.sub(r"[^0-9]", "", price_text))

            if not self._isPriceMatched(price):
                continue

            features = listing.find("ul", class_="illustrated-features")
            area = ""
            if features:
                items = features.find_all("li")
                if items:
                    area = items[0].get_text(strip=True)

            ret.append(House(house_id, full_url, address, price, area))

        return ret
