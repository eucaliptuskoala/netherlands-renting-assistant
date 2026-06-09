import re

from curl_cffi import requests as curl_req

from interface import RentProviderInterface
from model import House


class Vestide(RentProviderInterface):
    BASE = "https://rooms.vestide.nl"

    def __init__(self, city="eindhoven", price=[0, 9000], header=None):
        super().__init__(city, price)
        self._header = header or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def Run(self):
        url = f"{self.BASE}/api/accommodation/getlivingspaces/?LanguageCode=en&Skip=0&Take=999"

        try:
            r = curl_req.get(url, headers=self._header, impersonate="chrome131")
            r.raise_for_status()
        except Exception as e:
            print(f"    [error] Vestide request failed: {e}", flush=True)
            return []

        print(f"    [debug] Vestide response: {len(r.text)} bytes")

        try:
            data = r.json()
        except Exception as e:
            print(f"    [error] Vestide JSON parse failed: {e}", flush=True)
            return []

        ret = []
        for item in data:
            house_id = f"vestide-{item.get('id', '')}"
            detail_id = item.get("id", "")
            full_url = f"{self.BASE}/en/find-room/detail-accommodation/?detailId={detail_id}"

            address = item.get("advertentietitel", "")

            price_text = item.get("totaleHuur", "0")
            price = int(re.sub(r"[^0-9]", "", price_text)) if price_text else 0

            if not self._isPriceMatched(price):
                continue

            area_value = item.get("woonoppervlakte", 0)
            living_area = f"{int(area_value)} m\u00b2" if area_value else ""

            ret.append(House(house_id, full_url, address, price, living_area))

        return ret
