import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger(__name__)


@dataclass
class PriceMessage:
    cost: int
    x: int
    y: int
    link: str
    timestamp: datetime


class ChannelManager:
    def __init__(
            self,
            bot_token: str,
            price_channels: Dict[int, str],
            batch_size: int = 7,
            batch_delay: int = 120
    ):
        self.bot = Bot(token=bot_token)
        self.price_channels = price_channels
        self.batch_size = batch_size
        self.batch_delay = batch_delay

        # Очереди сообщений для каждого канала
        self.message_queues: Dict[int, List[PriceMessage]] = {
            price: [] for price in price_channels.keys()
        }

        self._lock = asyncio.Lock()
        self._running = False
        self._batch_task: Optional[asyncio.Task] = None

    def _get_price_category(self, cost: int) -> Optional[int]:
        """Определить категорию цены для сообщения"""
        for price_limit in sorted(self.price_channels.keys()):
            if cost == price_limit:
                return price_limit
        return None

    async def add_message(self, cost: int, x: int, y: int, link: str):
        """Добавить сообщение в очередь соответствующего канала"""
        price_category = self._get_price_category(cost)
        if price_category is None:
            logger.warning(f"Нет канала для цены {cost} $PX")
            return

        message = PriceMessage(
            cost=cost,
            x=x,
            y=y,
            link=link,
            timestamp=datetime.now()
        )

        async with self._lock:
            self.message_queues[price_category].append(message)
            logger.debug(f"Добавлено сообщение в очередь {price_category} PX: {cost} PX ({x},{y})")

    async def _send_batch_to_channel(self, channel: str, messages: List[PriceMessage]) -> bool:
        """Отправить пачку сообщений в канал"""
        try:
            # Формируем текст сообщения
            message_lines = []
            for msg in messages:
                message_lines.append(f"{msg.cost} $PX ({msg.x},{msg.y}): {msg.link}")

            combined_message = "\n\n".join(message_lines)

            await self.bot.send_message(
                chat_id=channel,
                text=combined_message,
                disable_web_page_preview=True
            )

            logger.info(f"Отправлено {len(messages)} сообщений в канал {channel}")
            return True

        except TelegramBadRequest as e:
            logger.error(f"Ошибка отправки в канал {channel}: {e}")
            return False
        except TelegramForbiddenError as e:
            logger.error(f"Нет доступа к каналу {channel}: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке в {channel}: {e}")
            return False

    async def _process_message_queues(self):
        """Обработать очереди сообщений"""
        while self._running:
            try:
                messages_sent = 0

                async with self._lock:
                    for price_category, messages in self.message_queues.items():
                        if len(messages) >= self.batch_size:
                            # Отправляем пачку
                            batch = messages[:self.batch_size]
                            channel = self.price_channels[price_category]

                            if await self._send_batch_to_channel(channel, batch):
                                # Удаляем отправленные сообщения из очереди
                                self.message_queues[price_category] = messages[self.batch_size:]
                                messages_sent += len(batch)

                if messages_sent > 0:
                    logger.info(f"Всего отправлено сообщений: {messages_sent}")

                await asyncio.sleep(self.batch_delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в обработке очередей сообщений: {e}")
                await asyncio.sleep(10)

    async def flush_all_queues(self):
        """Отправить все оставшиеся сообщения из очередей"""
        async with self._lock:
            for price_category, messages in self.message_queues.items():
                if messages:
                    channel = self.price_channels[price_category]

                    # Отправляем пачками
                    for i in range(0, len(messages), self.batch_size):
                        batch = messages[i:i + self.batch_size]
                        await self._send_batch_to_channel(channel, batch)

                        if i + self.batch_size < len(messages):
                            await asyncio.sleep(1)  # Небольшая задержка между пачками

                    self.message_queues[price_category] = []

    async def start(self):
        """Запустить обработку очередей"""
        if self._running:
            return

        self._running = True
        self._batch_task = asyncio.create_task(self._process_message_queues())
        logger.info("Менеджер каналов запущен")

    async def stop(self):
        """Остановить обработку очередей и отправить оставшиеся сообщения"""
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
        logger.info("Менеджер каналов остановлен")

    async def get_queue_stats(self) -> Dict[int, int]:
        """Получить статистику очередей"""
        async with self._lock:
            return {price: len(messages) for price, messages in self.message_queues.items()}
