import aiohttp
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)

async def send_telegram_message(bot_token: str, chat_id: int | str, text: str):
    base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {
        'chat_id': chat_id,
        'text': text
    }
    url = f"{base_url}?{urlencode(params)}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Сообщение отправлено успешно: {result}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка {response.status}: {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Произошла ошибка: {e}")
            return None 