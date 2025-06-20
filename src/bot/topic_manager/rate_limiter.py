import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RateLimiter:
    """Класс для управления ограничениями скорости отправки сообщений"""

    def __init__(self,
                 min_send_interval: float = 3.0,
                 max_group_messages_per_minute: int = 15):
        self.min_send_interval = min_send_interval
        self.max_group_messages_per_minute = max_group_messages_per_minute
        self._last_send_time = 0
        self._group_message_count = 0
        self._group_reset_time = datetime.now()
        self._consecutive_errors = 0

    async def wait_if_needed(self):
        """Ожидание перед отправкой сообщения если необходимо"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_send_time

        if time_since_last < self.min_send_interval:
            sleep_time = self.min_send_interval - time_since_last
            logger.debug(f"Ожидание {sleep_time:.1f} секунд перед отправкой")
            await asyncio.sleep(sleep_time)

    async def check_group_limit(self):
        """Проверка лимита сообщений в группе за минуту"""
        now = datetime.now()
        if (now - self._group_reset_time).total_seconds() >= 60:
            self._group_message_count = 0
            self._group_reset_time = now

        if self._group_message_count >= self.max_group_messages_per_minute:
            wait_time = 60 - (now - self._group_reset_time).total_seconds()
            logger.info(f"Достигнут лимит сообщений в группе. Ожидание {wait_time:.1f} секунд")
            await asyncio.sleep(wait_time)
            self._group_message_count = 0
            self._group_reset_time = datetime.now()

    def update_after_send(self):
        """Обновление счетчиков после успешной отправки"""
        self._last_send_time = asyncio.get_event_loop().time()
        self._group_message_count += 1
        self._consecutive_errors = 0

    def handle_error(self):
        """Обработка ошибки отправки"""
        self._consecutive_errors += 1
        self.min_send_interval = min(self.min_send_interval * 1.5, 10.0)
        logger.info(f"Увеличен минимальный интервал до {self.min_send_interval:.1f} секунд")

    def get_adaptive_delay(self, base_delay: int) -> float:
        """Получение адаптивной задержки на основе количества ошибок"""
        if self._consecutive_errors > 0:
            return base_delay * (1.5 ** min(self._consecutive_errors, 5))
        return base_delay