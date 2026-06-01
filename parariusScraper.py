import re
from curl_cffi import requests as curl_req
from bs4 import BeautifulSoup
from model import House
from interface import RentProviderInterface


class Pararius(RentProviderInterface):
    BASE = "https://www.pararius.com"

    def __init__(self, city='amsterdam', price=[0, 9000], header={}):
        super().__init__(city, price)
        self._header = header or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def Run(self):
        url = f"{self.BASE}/apartments/{self._city}/{self._min_price}-{self._max_price}"
        r = curl_req.get(url, headers=self._header, impersonate='chrome120')
        soup = BeautifulSoup(r.text, 'lxml')

        ret = []
        for listing in soup.find_all('li', class_='search-list__item search-list__item--listing'):
            title = listing.find('h3', class_='listing-search-item__title')
            if not title or not title.a:
                continue

            href = title.a.get('href', '')
            full_url = self.BASE + href

            m = re.search(r'/([a-f0-9]+)/[^/]+$', href.rstrip('/'))
            house_id = m.group(1) if m else href

            loc = listing.find('div', class_='listing-search-item__sub-title')
            address = loc.get_text(strip=True) if loc else ''

            price_el = listing.find('span', class_='listing-search-item__price-main')
            price_text = price_el.get_text(strip=True) if price_el else '0'
            price = int(re.sub(r'[^0-9]', '', price_text))

            if not self._isPriceMatched(price):
                continue

            features = listing.find('ul', class_='illustrated-features')
            area = ''
            if features:
                items = features.find_all('li')
                if items:
                    area = items[0].get_text(strip=True)

            ret.append(House(house_id, full_url, address, price, area))

        return ret
