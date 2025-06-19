import aiohttp
import logging

from datetime import datetime

from src.api.tokens import token_manager

logger = logging.getLogger(__name__)


class ErrorResponse:
    status = 401

    async def json(self):
        return {"error": "No valid token"}

    async def text(self):
        return "No valid token"


async def api_get_with_refresh(url, headers=None, session=None):
    """
    Выполнить GET запрос с автоматическим обновлением токена
    """
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    if headers is None:
        headers = {}

    response = None
    try:
        # Получаем действительный токен (автоматически обновится если нужно)
        access_token = await token_manager.get_valid_access_token()

        if not access_token:
            logger.error("Не удалось получить действительный токен")
            return ErrorResponse()

        # Устанавливаем токен в заголовки
        request_headers = dict(headers)
        request_headers['Authorization'] = f'Bearer {access_token}'

        # Выполняем запрос
        response = await session.get(url, headers=request_headers)

        # Если получили 401, пытаемся принудительно обновить токен и повторить
        if response.status == 401:
            logger.info("Получен 401, принудительно обновляем токен")

            # Принудительно помечаем токен как истекший
            token_manager.token_expires_at = datetime.now()

            # Получаем новый токен
            access_token = await token_manager.get_valid_access_token()

            if access_token:
                request_headers['Authorization'] = f'Bearer {access_token}'

                # Закрываем предыдущий ответ
                response.close()

                # Повторяем запрос с новым токеном
                response = await session.get(url, headers=request_headers)
                logger.info(f"Повторный запрос выполнен со статусом: {response.status}")
            else:
                logger.error("Не удалось обновить токен после 401")

        return response

    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса {url}")
        # logger.exception(e)
        if response:
            response.close()
        raise
    finally:
        if close_session and session:
            await session.close()