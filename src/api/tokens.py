import os
import json
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Optional

from src.config import REFRESH_URL, TOKENS_PATH

logger = logging.getLogger(__name__)


class TokenManager:
    def __init__(self):
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self._refresh_lock = asyncio.Lock()
        self._refresh_task: Optional[asyncio.Task] = None
        self._load_tokens_from_file()

    def _load_tokens_from_file(self) -> None:
        """Загрузить токены из файла при инициализации"""
        if not os.path.exists(TOKENS_PATH):
            return

        try:
            with open(TOKENS_PATH, 'r', encoding='utf-8') as f:
                tokens = json.load(f)

            self.access_token = tokens.get('access')
            self.refresh_token = tokens.get('refresh')

            # Устанавливаем время истечения с запасом в 5 минут
            # Если нет информации о времени истечения, считаем токен истекшим
            expires_in = tokens.get('expires_in', 0)
            if expires_in > 0:
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
            else:
                self.token_expires_at = datetime.now()  # Токен считается истекшим

        except Exception as e:
            logger.error(f"Ошибка при загрузке токенов из файла: {e}")

    def _save_tokens_to_file(self, access_token: str, refresh_token: str, expires_in: int = 3600) -> None:
        """Сохранить токены в файл"""
        try:
            tokens_data = {
                "access": access_token,
                "refresh": refresh_token,
                "expires_in": expires_in,
                "updated_at": datetime.now().isoformat()
            }

            with open(TOKENS_PATH, 'w', encoding='utf-8') as f:
                json.dump(tokens_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Ошибка при сохранении токенов в файл: {e}")

    def _is_token_expired(self) -> bool:
        """Проверить, истек ли токен"""
        if not self.access_token or not self.token_expires_at:
            return True
        return datetime.now() >= self.token_expires_at

    async def get_valid_access_token(self) -> Optional[str]:
        """Получить действительный access token, обновив его при необходимости"""
        if self._is_token_expired():
            await self._refresh_token_if_needed()
        return self.access_token

    async def _refresh_token_if_needed(self) -> None:
        """Обновить токен с защитой от множественных одновременных запросов"""
        async with self._refresh_lock:
            # Повторная проверка после получения блокировки
            # Возможно, другая корутина уже обновила токен
            if not self._is_token_expired():
                return

            # Если уже есть активная задача обновления, ждем ее завершения
            if self._refresh_task and not self._refresh_task.done():
                try:
                    await self._refresh_task
                except Exception:
                    # Если предыдущая задача завершилась с ошибкой,
                    # создаем новую задачу
                    pass

            # Проверяем еще раз после ожидания задачи
            if not self._is_token_expired():
                return

            # Создаем новую задачу обновления
            self._refresh_task = asyncio.create_task(self._perform_token_refresh())
            await self._refresh_task

    async def _perform_token_refresh(self) -> None:
        """Выполнить фактическое обновление токена"""
        if not self.refresh_token:
            logger.error(f"Refresh token отсутствует!")
            return

        payload = {"refresh_token": self.refresh_token}
        headers = {'Content-Type': 'application/json'}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(REFRESH_URL, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success', False):
                            # Обновляем токены в памяти
                            self.access_token = data['token']
                            self.refresh_token = data['refresh_token']

                            # Устанавливаем время истечения с запасом в 5 минут
                            expires_in = data.get('expires_in', 3600)
                            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)

                            # Сохраняем в файл
                            self._save_tokens_to_file(
                                self.access_token,
                                self.refresh_token,
                                expires_in
                            )

                            logger.info("Токены успешно обновлены и сохранены")
                        else:
                            logger.error(f"Некорректный ответ от сервера: {data}")
                            raise Exception(f"Token refresh failed: {data}")
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка обновления токенов: {response.status} {error_text}")
                        raise Exception(f"Token refresh failed: {response.status}")

        except Exception as e:
            logger.error(f"Ошибка при обновлении токенов: {e}")
            # Сбрасываем токены при ошибке
            self.access_token = None
            self.token_expires_at = None
            raise
        finally:
            # Очищаем задачу после завершения
            self._refresh_task = None

    def get_access_token_sync(self) -> Optional[str]:
        """Синхронный метод для получения текущего access token (без обновления)"""
        return self.access_token

    def get_refresh_token_sync(self) -> Optional[str]:
        """Синхронный метод для получения текущего refresh token"""
        return self.refresh_token


# Создаем глобальный экземпляр менеджера токенов
token_manager = TokenManager()
