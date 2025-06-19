import json
import os
from typing import Dict

import dotenv

ENV_FILE = '.env'

dotenv.load_dotenv(ENV_FILE)

BOT_TOKEN = os.getenv('BOT_TOKEN', None)
CHAT_ID = os.getenv('CHAT_ID', None)

GROUP_ID = os.getenv('GROUP_ID', None)

REFRESH_URL = 'https://notpixel.org/api/v1/auth/telegram/refresh'
PIXEL_CHECK_URL = 'https://notpixel.org/api/v1/battle-canvas/pixels/{pixel_id}'
PIXEL_URL = 'https://t.me/notpixel/app?startapp=x{x}_y{y}_mbattle'

PIXELS_DATA_FILENAME = r'data/pixels.csv'
TOKENS_PATH = r'data/tokens.json'
PRICE_TOPICS = r'data/topics.json'

MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT', 10))

MIN_COST = int(os.getenv('MIN_COST', 4))
MAX_COST = int(os.getenv('MAX_COST', 64))

MESSAGE_SIZE = int(os.getenv('MESSAGE_SIZE', 16))
BATCH_DELAY = int(os.getenv('BATCH_DELAY', 120))
REVERSE = False

BASE_ID = int(os.getenv('BASE_ID', 262401))
BASE_START = int(os.getenv('BASE_START', 256))
BASE_END = int(os.getenv('BASE_END', 657))

HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'dnt': '1',
    'priority': 'u=1, i',
    'referer': 'https://notpixel.org/',
    'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
}
