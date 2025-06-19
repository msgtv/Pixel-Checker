import asyncio
import logging
import random

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from src.service.file_handler import FileHandler

logger = logging.getLogger(__name__)


@dataclass
class PriceMessage:
    cost: int
    x: int
    y: int
    link: str
    timestamp: datetime


class TopicManager:
    def __init__(
            self,
            bot_token: str,
            group_id: str,
            topic_ids_filename: str,
            batch_size: int = 5,  # Уменьшили с 7 до 5
            batch_delay: int = 180  # Увеличили с 120 до 180 секунд
    ):
        self.bot = Bot(token=bot_token)
        self.group_id = group_id
        self.batch_size = batch_size
        self.batch_delay = batch_delay

        # Словарь для хранения ID тем
        self.topic_ids_filename = topic_ids_filename
        self.topic_ids = FileHandler.read_json(topic_ids_filename)

        # Очереди сообщений для каждой темы
        self.message_queues: Dict[int, List[PriceMessage]] = {}

        # Контроль скорости отправки
        self._lock = asyncio.Lock()
        self._running = False
        self._batch_task: Optional[asyncio.Task] = None
        self._last_send_time = 0
        self._min_send_interval = 3.0  # Минимум 3 секунды между отправками
        self._group_message_count = 0
        self._group_reset_time = datetime.now()
        self._max_group_messages_per_minute = 15  # Консервативный лимит
        self._consecutive_errors = 0

    async def _get_or_create_topic_id(self, price_category: int) -> Optional[int]:
        """Получить или создать ID темы для ценовой категории"""
        pc = str(int(price_category))

        topic_id = self.topic_ids.get(pc, None)
        if topic_id is None:
            try:
                # Добавляем задержку перед созданием темы
                await asyncio.sleep(2)

                topic = await self.bot.create_forum_topic(
                    chat_id=self.group_id,
                    name=f'{pc} $PX',
                )

                self.topic_ids[pc] = topic.message_thread_id
                topic_id = topic.message_thread_id

                # Сохраняем обновленные ID тем
                FileHandler.write_json(self.topic_ids_filename, self.topic_ids)
                logger.info(f"Создана новая тема '{pc} $PX' с ID {topic_id}")

            except TelegramRetryAfter as e:
                logger.warning(f"RetryAfter при создании темы для {price_category}: ожидание {e.retry_after}с")
                await asyncio.sleep(e.retry_after + random.uniform(1, 3))
                return None
            except Exception as e:
                logger.error(f"Ошибка получения ID темы для категории {price_category}: {e}")
                return None

        return topic_id

    async def add_message(self, cost: int, x: int, y: int, link: str):
        """Добавить сообщение в очередь соответствующей темы"""
        price_category = cost
        if price_category is None:
            logger.warning(f"Цена {cost} превышает максимальную категорию")
            return

        message = PriceMessage(
            cost=cost,
            x=x,
            y=y,
            link=link,
            timestamp=datetime.now()
        )

        async with self._lock:
            self.message_queues.setdefault(price_category, []).append(message)
            logger.debug(f"Добавлено сообщение в очередь темы {price_category} PX: {cost} PX ({x},{y})")

    def _get_message_text(self, msg):
        return (
            f"<b>{msg.x},{msg.y}:</b> "
            f"<a href='{msg.link}'>click</a>"
        )

    async def _send_batch_to_topic(self, price_category: int, messages: List[PriceMessage]) -> bool:
        """Отправить пачку сообщений в тему с соблюдением лимитов"""
        topic_id = await self._get_or_create_topic_id(price_category)
        if topic_id is None:
            logger.error(f"Не удалось получить ID темы для категории {price_category}")
            return False

        # Проверяем лимит сообщений в группе за минуту
        now = datetime.now()
        if (now - self._group_reset_time).total_seconds() >= 60:
            self._group_message_count = 0
            self._group_reset_time = now

        if self._group_message_count >= self._max_group_messages_per_minute:
            wait_time = 60 - (now - self._group_reset_time).total_seconds()
            logger.info(f"Достигнут лимит сообщений в группе. Ожидание {wait_time:.1f} секунд")
            await asyncio.sleep(wait_time)
            self._group_message_count = 0
            self._group_reset_time = datetime.now()

        # Соблюдаем минимальный интервал между отправками
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_send_time
        if time_since_last < self._min_send_interval:
            sleep_time = self._min_send_interval - time_since_last
            logger.debug(f"Ожидание {sleep_time:.1f} секунд перед отправкой")
            await asyncio.sleep(sleep_time)

        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                # Формируем текст сообщения
                message_lines = []
                for msg in messages:
                    message_lines.append(
                        self._get_message_text(msg)
                    )

                message_lines.append(
                    '\n<b>author: @odincryptan</b>\n'
                    f'{" " * len("author: ")}<b><a href="https://app.tonkeeper.com/transfer/UQCku2Rt-aU7_AiNG-7Lz66ruaywXDFXUGL8kbJ8UaEFwXPD">donate</a></b>'
                )

                combined_message = "\n\n".join(message_lines)

                # Проверяем размер сообщения
                if len(combined_message.encode('utf-8')) > 4000:  # Telegram лимит ~4096 символов
                    return await self._send_large_message_in_parts(topic_id, messages, price_category)

                await self.bot.send_message(
                    chat_id=self.group_id,
                    text=combined_message,
                    message_thread_id=topic_id,
                    disable_web_page_preview=True,
                    parse_mode='HTML',
                )

                # Обновляем счетчики
                self._last_send_time = asyncio.get_event_loop().time()
                self._group_message_count += 1
                self._consecutive_errors = 0

                logger.info(f"Отправлено {len(messages)} сообщений в тему '{price_category} $PX'")
                return True

            except TelegramRetryAfter as e:
                wait_time = e.retry_after + random.uniform(1, 3)
                logger.warning(f"RetryAfter {e.retry_after}с для темы {price_category}. Ожидание {wait_time:.1f}с")
                await asyncio.sleep(wait_time)

                # Увеличиваем минимальный интервал после RetryAfter
                self._min_send_interval = min(self._min_send_interval * 1.5, 10.0)
                self._consecutive_errors += 1
                logger.info(f"Увеличен минимальный интервал до {self._min_send_interval:.1f} секунд")

                if attempt == max_retries - 1:
                    logger.error(f"Превышено количество попыток для темы {price_category}")
                    return False

            except TelegramBadRequest as e:
                logger.error(f"Ошибка отправки в тему {price_category}: {e}")
                if "message is too long" in str(e).lower():
                    return await self._send_large_message_in_parts(topic_id, messages, price_category)
                return False

            except TelegramForbiddenError as e:
                logger.error(f"Нет доступа к группе {self.group_id}: {e}")
                return False

            except Exception as e:
                logger.error(f"Неожиданная ошибка при отправке в тему {price_category}: {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                    await asyncio.sleep(delay)
                else:
                    return False

        return False

    async def _send_large_message_in_parts(self, topic_id: int, messages: List[PriceMessage],
                                           price_category: int) -> bool:
        """Отправить большое сообщение частями"""
        parts = []
        current_part = []
        current_size = 0

        for msg in messages:
            line = self._get_message_text(msg)
            line_size = len(line.encode('utf-8')) + 2  # +2 для \n\n

            if current_size + line_size > 3500:  # Консервативный лимит
                if current_part:
                    parts.append(current_part)
                    current_part = [msg]
                    current_size = line_size
                else:
                    current_part = [msg]
                    parts.append(current_part)
                    current_part = []
                    current_size = 0
            else:
                current_part.append(msg)
                current_size += line_size

        if current_part:
            parts.append(current_part)

        success_count = 0
        for i, part in enumerate(parts):
            if i > 0:
                await asyncio.sleep(self._min_send_interval)

            message_lines = [
                self._get_message_text(msg) for msg in part
            ]

            message_lines += ['\n<b>author: @odincryptan</b>']
            combined_message = "\n\n".join(message_lines)

            try:
                await self.bot.send_message(
                    chat_id=self.group_id,
                    text=combined_message,
                    message_thread_id=topic_id,
                    disable_web_page_preview=True,
                    parse_mode='HTML',
                )
                success_count += 1
                self._group_message_count += 1

            except TelegramRetryAfter as e:
                logger.warning(f"RetryAfter при отправке части {i + 1}: ожидание {e.retry_after}с")
                await asyncio.sleep(e.retry_after + random.uniform(1, 2))
                try:
                    await self.bot.send_message(
                        chat_id=self.group_id,
                        text=combined_message,
                        message_thread_id=topic_id,
                        disable_web_page_preview=True,
                        parse_mode='HTML',
                    )
                    success_count += 1
                    self._group_message_count += 1
                except Exception as e2:
                    logger.error(f"Ошибка при повторной отправке части {i + 1}: {e2}")

            except Exception as e:
                logger.error(f"Ошибка отправки части {i + 1}: {e}")

        logger.info(f"Отправлено {success_count}/{len(parts)} частей в тему '{price_category} $PX'")
        return success_count > 0

    # async def _process_message_queues(self):
    #     """Обработать очереди сообщений с адаптивными задержками"""
    #     base_delay = self.batch_delay
    #
    #     while self._running:
    #         try:
    #             messages_sent = 0
    #
    #             async with self._lock:
    #                 for price_category, messages in self.message_queues.items():
    #                     if len(messages) >= self.batch_size:
    #                         batch = messages[:self.batch_size]
    #
    #                         if await self._send_batch_to_topic(price_category, batch):
    #                             self.message_queues[price_category] = messages[self.batch_size:]
    #                             messages_sent += len(batch)
    #                         else:
    #                             logger.warning(f"Ошибка отправки для категории {price_category}")
    #
    #             if messages_sent > 0:
    #                 logger.info(f"Всего отправлено сообщений: {messages_sent}")
    #
    #             # Адаптивная задержка на основе ошибок
    #             if self._consecutive_errors > 0:
    #                 adaptive_delay = base_delay * (1.5 ** min(self._consecutive_errors, 5))
    #                 logger.info(f"Увеличена задержка до {adaptive_delay:.1f}с из-за ошибок")
    #                 await asyncio.sleep(adaptive_delay)
    #             else:
    #                 await asyncio.sleep(base_delay)
    #
    #         except asyncio.CancelledError:
    #             break
    #         except Exception as e:
    #             logger.error(f"Ошибка в обработке очередей сообщений: {e}")
    #             self._consecutive_errors += 1
    #             await asyncio.sleep(min(base_delay * 2, 300))  # Максимум 5 минут

    async def _process_message_queues(self):
        """Обработать очереди сообщений с адаптивными задержками и таймаутом для неполных батчей"""
        base_delay = self.batch_delay
        # Словарь для отслеживания времени первого сообщения в каждой очереди
        first_message_time: Dict[int, datetime] = {}
        # Таймаут для отправки неполных батчей (например, 5 минут)
        incomplete_batch_timeout = 120  # секунд

        while self._running:
            try:
                messages_sent = 0
                current_time = datetime.now()

                async with self._lock:
                    for price_category, messages in self.message_queues.items():
                        if not messages:
                            # Очищаем время для пустых очередей
                            first_message_time.pop(price_category, None)
                            continue

                        # Отслеживаем время первого сообщения в очереди
                        if price_category not in first_message_time:
                            first_message_time[price_category] = current_time

                        # Проверяем условия для отправки
                        should_send_full_batch = len(messages) >= self.batch_size

                        # Проверяем таймаут для неполных батчей
                        time_since_first = (current_time - first_message_time[price_category]).total_seconds()
                        should_send_by_timeout = (
                                len(messages) > 0 and
                                time_since_first >= incomplete_batch_timeout
                        )

                        if should_send_full_batch or should_send_by_timeout:
                            # Определяем размер батча
                            if should_send_full_batch:
                                batch = messages[:self.batch_size]
                                logger.debug(f"Отправка полного батча для категории {price_category}")
                            else:
                                batch = messages  # Отправляем все накопленные сообщения
                                logger.info(
                                    f"Отправка неполного батча по таймауту для категории {price_category}: {len(batch)} сообщений")

                            if await self._send_batch_to_topic(price_category, batch):
                                # Удаляем отправленные сообщения
                                if should_send_full_batch:
                                    self.message_queues[price_category] = messages[self.batch_size:]
                                else:
                                    self.message_queues[price_category] = []

                                messages_sent += len(batch)

                                # Сбрасываем время для этой категории
                                if not self.message_queues[price_category]:
                                    first_message_time.pop(price_category, None)
                                else:
                                    # Обновляем время для оставшихся сообщений
                                    first_message_time[price_category] = current_time
                            else:
                                logger.warning(f"Ошибка отправки для категории {price_category}")

                if messages_sent > 0:
                    logger.info(f"Всего отправлено сообщений: {messages_sent}")

                # Адаптивная задержка на основе ошибок
                if self._consecutive_errors > 0:
                    adaptive_delay = base_delay * (1.5 ** min(self._consecutive_errors, 5))
                    logger.info(f"Увеличена задержка до {adaptive_delay:.1f}с из-за ошибок")
                    await asyncio.sleep(adaptive_delay)
                else:
                    await asyncio.sleep(base_delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в обработке очередей сообщений: {e}")
                self._consecutive_errors += 1
                await asyncio.sleep(min(base_delay * 2, 300))  # Максимум 5 минут

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

        FileHandler.write_json(self.topic_ids_filename, self.topic_ids)
        logger.info("Менеджер тем остановлен")

    async def flush_all_queues(self):
        """Отправить все оставшиеся сообщения из очередей"""
        async with self._lock:
            for price_category, messages in self.message_queues.items():
                if messages:
                    for i in range(0, len(messages), self.batch_size):
                        batch = messages[i:i + self.batch_size]
                        await self._send_batch_to_topic(price_category, batch)

                        if i + self.batch_size < len(messages):
                            await asyncio.sleep(self._min_send_interval)

                    self.message_queues[price_category] = []

    async def get_queue_stats(self) -> Dict[int, int]:
        """Получить статистику очередей"""
        async with self._lock:
            return {price: len(messages) for price, messages in self.message_queues.items()}