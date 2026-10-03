import json
import re

from curl_cffi import requests as curl_req

from interface import RentProviderInterface
from model import House

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
    re.DOTALL,
)


class Kamernet(RentProviderInterface):
    BASE = "https://kamernet.nl"

    def __init__(self, city="amsterdam", price=[0, 9000], header=None):
        super().__init__(city, price)
        self._header = header or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def Run(self):
        slug = f"huurwoningen-{self._city}"
        params = "pageNo=1&searchView=1&listingTypes=1,2,4&sort=1"
        url = f"{self.BASE}/huren/{slug}?{params}"

        try:
            r = curl_req.get(url, headers=self._header, impersonate="chrome131")
            r.raise_for_status()
        except Exception as e:
            print(f"    [error] Kamernet request failed: {e}", flush=True)
            return []

        match = _NEXT_DATA_RE.search(r.text)
        if not match:
            print("    [error] Kamernet: could not find __NEXT_DATA__", flush=True)
            return []

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            print(f"    [error] Kamernet: failed to parse JSON: {e}", flush=True)
            return []

        target = data.get("props", {}).get("pageProps", {}).get("targetPageProps") or {}
        response = target.get("findListingsResponse")
        if not response:
            print("    [error] Kamernet: no findListingsResponse in payload", flush=True)
            return []

        listings = response.get("listings") or []

        ret = []
        for item in listings:
            listing_id = item.get("listingId")
            if not listing_id:
                continue

            price = int(item.get("totalRentalPrice") or 0)
            if not self._isPriceMatched(price):
                continue

            city_slug = item.get("citySlug", "")
            street_slug = item.get("streetSlug", "")
            full_url = f"{self.BASE}/huren/{city_slug}/{street_slug}/{listing_id}"

            street = item.get("street") or ""
            city = item.get("city") or ""
            address = f"{street}, {city}" if street else city

            surface = item.get("surfaceArea")
            living_area = f"{surface} m\u00b2" if surface else ""

            ret.append(House(f"kamernet-{listing_id}", full_url, address, price, living_area))

        return ret
