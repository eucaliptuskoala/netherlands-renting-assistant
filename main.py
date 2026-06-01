import json
import time
import sys
from datetime import datetime
import os

import requests

from funda import Funda
from parariusScraper import Pararius

AREA = "eindhoven"
PRICE = [400, 1400]
DATA = 'data.json'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

def loaddata():
    with open(DATA) as f:
        try:
            return json.load(f)
        except:
            return dict()

def savedata(data):
    with open(DATA, "w+") as f:
        f.write(json.dumps(data))


def process(localdata, houses, callback):
    for house in houses:
        if not localdata.get(str(house.id)):
            localdata[str(house.id)] = True
        else:
            continue

        try:
            callback(house)
        finally:
            savedata(localdata)

def sendToTelegram(house):
    CHATID = os.environ.get('TELEGRAM_CHAT_ID')
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    URL = 'https://api.telegram.org/bot%s/sendMessage' % TOKEN

    body = {'parse_mode': 'Markdown', 'chat_id': CHATID, 'text': '**%s**\n€%s/%s\n%s' % (house.address, house.price, house.living_area, house.URL)}
    requests.post(URL, json=body)

if __name__ == '__main__':
    svcs = [Funda, Pararius]
    for idx, svc in enumerate(svcs):
        svcs[idx] = svc(AREA, PRICE, header=HEADERS)

    data = loaddata()
    print(f"[{datetime.now():%H:%M:%S}] Started")

    try:
        for svc in svcs:
            print(f"[{datetime.now():%H:%M:%S}] Running {svc.__class__.__name__}...")
            houses = svc.Run()
            process(data, houses, sendToTelegram)
            print(f"  -> {len(houses)} listings checked")
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] Error: {e}", file=sys.stderr) 
