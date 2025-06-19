import aiohttp
import asyncio
from urllib.parse import urlencode


def get_canvas_id(x, y):
    """
    Вычисляет ID для координат (x, y) на холсте

    Args:
        x (int): координата x (от 384 до 639)
        y (int): координата y (от 384 до 639)

    Returns:
        int: ID точки
    """
    base_id = 393601
    return base_id + (x - 384) + (y - 384) * 1024





# Пример использования
async def main():
    bot_token = "5829736204:AAFTOPkh5uRSy7Oq28Z1wATKSeeF0l0OiaU"  # Замените на токен вашего бота
    chat_id = 349385497  # Замените на ID чата пользователя
    message = "Привет! Это сообщение отправлено асинхронно."

    result = await send_telegram_message(bot_token, chat_id, message)
    if result:
        print("Сообщение доставлено!")


if __name__ == '__main__':
    # Примеры использования:
    asyncio.run(main())