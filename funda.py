from curl_cffi import requests as curl_req
from bs4 import BeautifulSoup
import re
from model import House
from interface import RentProviderInterface


class Funda(RentProviderInterface):
    BASE = "https://www.funda.nl"

    def __init__(self, city='amsterdam', price=[0, 9000], header={}):
        super().__init__(city, price)
        self._header = header or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def Run(self):
        url = f"{self.BASE}/en/huur/{self._city}/"
        r = curl_req.get(url, headers=self._header, impersonate='chrome120')
        soup = BeautifulSoup(r.text, 'lxml')

        ret = []
        for listing in soup.select('div[class*="border-b"]'):
            link = listing.find('a', attrs={"data-testid": "listingDetailsAddress"})
            if not link:
                continue

            href = link.get('href', '')
            full_url = self.BASE + href

            house_id = href.rstrip('/').rsplit('/', 1)[-1]

            addr_tag = link.find('span', class_='truncate')
            address = addr_tag.get_text(strip=True) if addr_tag else ''

            price = 0
            for d in listing.find_all('div', class_='truncate'):
                t = d.get_text(strip=True)
                if '€' in t:
                    price = int(re.sub(r'[^0-9]', '', t.split('/')[0]))
                    break

            if not self._isPriceMatched(price):
                continue

            feature_items = listing.select('ul[class*="gap-3"] li')
            features = [li.get_text(strip=True) for li in feature_items]
            living_area = features[0] if features else ''

            ret.append(House(house_id, full_url, address, price, living_area))

        return ret
