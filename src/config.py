import json
import os
from typing import Dict

import dotenv

# Файл с переменными окружения
ENV_FILE = '.env'

dotenv.load_dotenv(ENV_FILE)

# Токен Telegram бота для отправки уведомлений
BOT_TOKEN = os.getenv('BOT_TOKEN', None)
# ID чата для отправки сообщений
CHAT_ID = os.getenv('CHAT_ID', None)

# ID группы
GROUP_ID = os.getenv('GROUP_ID', None)

# URL для обновления токена аутентификации
REFRESH_URL = 'https://notpixel.org/api/v1/auth/telegram/refresh'
# URL для проверки информации о пикселе
PIXEL_CHECK_URL = 'https://notpixel.org/api/v1/battle-canvas/pixels/{pixel_id}'
# URL для открытия приложения с конкретным пикселем
PIXEL_URL = 'https://t.me/notpixel/app?startapp=x{x}_y{y}_mbattle'

# Путь к файлу с данными о пикселях
PIXELS_DATA_FILENAME = r'data/pixels.csv'
# Путь к файлу с токенами
TOKENS_PATH = r'data/tokens.json'
# Путь к файлу с темами для уведомлений о ценах
PRICE_TOPICS = r'data/topics.json'
# Путь к файлу с ценами пикселей для уведомления {цена: тип пикселя (available, lock, any)}
ALERT_COSTS_FILENAME = r'data/alert_costs.json'

# Максимальное количество одновременных запросов
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT', 10))

# # Минимальная стоимость пикселя для обработки
# MIN_COST = int(os.getenv('MIN_COST', 4))
# # Максимальная стоимость пикселя для обработки
# MAX_COST = int(os.getenv('MAX_COST', 64))
# # Список исключаемых стоимостей
# EXCLUDE_COSTS = [int(x) for x in os.getenv('EXCLUDE_COSTS', '').split(',')]

# Размер сообщения по умолчанию
MESSAGE_SIZE = int(os.getenv('MESSAGE_SIZE', 16))
# Максимальный размер сообщения
MAX_MESSAGE_SIZE = int(os.getenv('MAX_MESSAGE_SIZE', 20))
# Минимальный размер сообщения
MIN_MESSAGE_SIZE = int(os.getenv('MIN_MESSAGE_SIZE', 1))

# Задержка между пакетами запросов (в секундах)
BATCH_DELAY = int(os.getenv('BATCH_DELAY', 120))
# Флаг для обратного порядка обработки
REVERSE = False

# Базовый ID для расчетов
BASE_ID = int(os.getenv('BASE_ID', 262401))
# Начальное значение диапазона
BASE_START = int(os.getenv('BASE_START', 256))
# Конечное значение диапазона
BASE_END = int(os.getenv('BASE_END', 657))

# HTTP заголовки для запросов к API
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
