import re

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_req

from interface import RentProviderInterface
from model import House


class Funda(RentProviderInterface):
    BASE = "https://www.funda.nl"

    def __init__(self, city="amsterdam", price=[0, 9000], header=None):
        super().__init__(city, price)
        self._header = header or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def Run(self):
        url = f"{self.BASE}/en/huur/{self._city}/"

        try:
            r = curl_req.get(url, headers=self._header, impersonate="chrome131")
            r.raise_for_status()
        except Exception as e:
            print(f"    [error] Funda request failed: {e}", flush=True)
            return []

        print(f"    [debug] Funda response: {len(r.text)} bytes, first 200: {r.text[:200].strip()!r}")
        soup = BeautifulSoup(r.text, "lxml")

        ret = []
        for link in soup.select('a[data-testid="listingDetailsAddress"]'):
            href = link.get("href", "")
            full_url = self.BASE + href

            house_id = href.rstrip("/").rsplit("/", 1)[-1]

            addr_span = link.find("span")
            address = addr_span.get_text(strip=True) if addr_span else ""

            container = link
            for _ in range(10):
                if container.parent is None:
                    break
                container = container.parent

            if container is link:
                continue

            price = 0
            price_div = container.find(
                "div", class_=lambda c: c and "mt-2" in (c if isinstance(c, str) else " ".join(c))
            )
            if price_div:
                price_match = re.search(r"€\s*([0-9,.]+)", price_div.get_text())
                if price_match:
                    price = int(re.sub(r"[^0-9]", "", price_match.group(1)))

            if not self._isPriceMatched(price):
                continue

            living_area = ""
            area_match = re.search(r"(\d+)\s*m[²2]", container.get_text())
            if area_match:
                living_area = area_match.group(0)

            ret.append(House(house_id, full_url, address, price, living_area))

        return ret
