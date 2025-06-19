import os
import dotenv

ENV_FILE = '.env'

dotenv.load_dotenv(ENV_FILE)

BOT_TOKEN = os.getenv('BOT_TOKEN', None)
CHAT_ID = os.getenv('CHAT_ID', None)

REFRESH_URL = 'https://notpixel.org/api/v1/auth/telegram/refresh'
TOKENS_PATH = 'tokens.json'

MIN_COST = 32
MESSAGE_SIZE = 3
REVERSE = False

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
