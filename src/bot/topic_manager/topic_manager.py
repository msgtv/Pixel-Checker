import asyncio
import logging
from typing import Dict, Optional
from aiogram import Bot

from src.bot.topic_manager.rate_limiter import RateLimiter
from src.bot.topic_manager.manager import Manager
from src.bot.topic_manager.sender import MessageSender
from src.bot.topic_manager.queue import MessageQueue

logger = logging.getLogger(__name__)


class TopicManager:
    """Основной класс менеджера тем (рефакторинг)"""

    def __init__(self,
                 bot_token: str,
                 group_id: str,
                 topic_ids_filename: str,
                 batch_size: int = 5,
                 min_batch_size: int = 1,
                 max_batch_size: int = 20,
                 batch_delay: int = 180):

        self.bot = Bot(token=bot_token)
        self.batch_delay = batch_delay

        # Инициализация компонентов
        self.rate_limiter = RateLimiter()
        self.topic_manager = Manager(self.bot, group_id, topic_ids_filename)
        self.message_sender = MessageSender(self.bot, group_id, self.rate_limiter)
        self.message_queue = MessageQueue(min_batch_size, max_batch_size)

        # Контроль выполнения
        self._running = False
        self._batch_task: Optional[asyncio.Task] = None

    async def add_message(self, cost: int, x: int, y: int, link: str, is_available: bool):
        """Добавить сообщение в очередь"""
        await self.message_queue.add_message(
            cost=cost,
            x=x,
            y=y,
            link=link,
            is_available=is_available,
        )

    async def start(self):
        """Запустить обработку очередей"""
        if self._running:
            return

        self._running = True
        self._batch_task = asyncio.create_task(self._process_message_queues())
        logger.info("Менеджер тем запущен")

    async def stop(self):
        """Остановить обработку очередей"""
        if not self._running:
            return

        self._running = False
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        await self.flush_all_queues()
        await self.bot.session.close()
        self.topic_manager.save_topic_ids()
        logger.info("Менеджер тем остановлен")

    async def _process_message_queues(self):
        """Обработать очереди сообщений"""
        while self._running:
            try:
                messages_sent = 0
                ready_batches = await self.message_queue.get_ready_batches()

                for price_category, batch in ready_batches.items():
                    topic_id = await self.topic_manager.get_or_create_topic_id(price_category)
                    if topic_id is None:
                        logger.error(f"Не удалось получить ID темы для категории {price_category}")
                        continue

                    if await self.message_sender.send_batch_to_topic(topic_id, batch, price_category):
                        await self.message_queue.clear_sent_messages(price_category)
                        messages_sent += len(batch)
                    else:
                        logger.warning(f"Ошибка отправки для категории {price_category}")

                if messages_sent > 0:
                    logger.info(f"Всего отправлено сообщений: {messages_sent}")

                # Адаптивная задержка
                delay = self.rate_limiter.get_adaptive_delay(self.batch_delay)
                if delay != self.batch_delay:
                    logger.info(f"Увеличена задержка до {delay:.1f}с из-за ошибок")

                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в обработке очередей сообщений: {e}")
                self.rate_limiter.handle_error()
                await asyncio.sleep(min(self.batch_delay * 2, 300))

    async def flush_all_queues(self):
        """Отправить все оставшиеся сообщения из очередей"""
        remaining_messages = await self.message_queue.flush_all_queues()

        for price_category, messages in remaining_messages.items():
            topic_id = await self.topic_manager.get_or_create_topic_id(price_category)
            if topic_id:
                await self.message_sender.send_batch_to_topic(topic_id, messages, price_category)

    async def get_queue_stats(self) -> Dict[int, int]:
        """Получить статистику очередей"""
        return await self.message_queue.get_queue_stats()
