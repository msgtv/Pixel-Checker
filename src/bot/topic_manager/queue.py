import asyncio
import logging

from datetime import datetime
from typing import Dict, List

from src.bot.topic_manager.msg_formatter import PriceMessage

logger = logging.getLogger(__name__)


class MessageQueue:
    """
    Класс для управления очередями сообщений по ценовым категориям.

    Основная задача - накапливать сообщения в очередях для каждой ценовой категории
    и формировать батчи для отправки на основе размера очереди или времени ожидания.

    Логика работы:
    1. Сообщения добавляются в очереди по ценовым категориям
    2. Когда очередь достигает min_batch_size или проходит timeout - формируется батч
    3. Батчи отправляются, очереди очищаются
    """

    def __init__(self, min_batch_size: int = 1, max_batch_size: int = 20,
                 incomplete_batch_timeout: int = 120):
        """
        Инициализация менеджера очередей сообщений.

        Args:
            min_batch_size: Минимальный размер батча для отправки (по умолчанию 1)
            max_batch_size: Максимальный размер батча (по умолчанию 20)
            incomplete_batch_timeout: Таймаут в секундах для отправки неполного батча (по умолчанию 120)
        """
        # Настройки размеров батчей
        self.min_batch_size = min_batch_size  # Минимальное количество сообщений для отправки
        self.max_batch_size = max_batch_size  # Максимальное количество сообщений в одном батче
        self.incomplete_batch_timeout = incomplete_batch_timeout  # Время ожидания неполного батча в секундах

        # Основные структуры данных
        self.message_queues: Dict[int, List[PriceMessage]] = {}  # Очереди сообщений по ценовым категориям
        self.first_message_time: Dict[int, datetime] = {}  # Время добавления первого сообщения в каждую очередь

        # Асинхронная блокировка для thread-safe операций с очередями
        self._lock = asyncio.Lock()

    async def add_message(self, cost: int, x: int, y: int, link: str):
        """
        Добавить сообщение в очередь соответствующей ценовой категории.

        Метод thread-safe благодаря использованию asyncio.Lock().
        Создает объект PriceMessage и добавляет его в очередь для указанной ценовой категории.

        Args:
            cost: Стоимость пикселя (определяет ценовую категорию)
            x: Координата X пикселя
            y: Координата Y пикселя
            link: Ссылка на пиксель
        """
        # Создаем объект сообщения с текущим временем
        message = PriceMessage(
            cost=cost,
            x=x,
            y=y,
            link=link,
            timestamp=datetime.now()
        )

        # Используем блокировку для thread-safe доступа к очередям
        async with self._lock:
            # Создаем очередь для категории если её нет, затем добавляем сообщение
            self.message_queues.setdefault(cost, []).append(message)
            logger.debug(f"Добавлено сообщение в очередь темы {cost} PX: {cost} PX ({x},{y})")

    async def get_ready_batches(self) -> Dict[int, List[PriceMessage]]:
        """
        Получить готовые к отправке пачки сообщений.

        Проверяет каждую очередь и определяет, готова ли она к отправке на основе:
        1. Достижения минимального размера батча (min_batch_size)
        2. Превышения времени ожидания (incomplete_batch_timeout)

        Returns:
            Dict[int, List[PriceMessage]]: Словарь готовых батчей по ценовым категориям
        """
        ready_batches = {}  # Результирующий словарь готовых батчей
        current_time = datetime.now()  # Текущее время для расчета таймаутов

        # Используем блокировку для thread-safe доступа к очередям
        async with self._lock:
            # Проходим по всем очередям сообщений
            for price_category, messages in self.message_queues.items():
                # Если очередь пуста - удаляем время первого сообщения и пропускаем
                if not messages:
                    self.first_message_time.pop(price_category, None)
                    continue

                # Если это первое сообщение в очереди - запоминаем время
                if price_category not in self.first_message_time:
                    self.first_message_time[price_category] = current_time

                # Проверяем условие отправки по размеру батча
                should_send_full_batch = len(messages) >= self.min_batch_size

                # Проверяем условие отправки по таймауту
                time_since_first = (current_time - self.first_message_time[price_category]).total_seconds()
                should_send_by_timeout = (
                        len(messages) > 0 and  # Есть сообщения в очереди
                        time_since_first >= self.incomplete_batch_timeout  # Прошло достаточно времени
                )

                # Если выполнено любое из условий - формируем батч
                if should_send_full_batch or should_send_by_timeout:
                    if should_send_full_batch:
                        # Полный батч - берем последние сообщения (ограничиваем max_batch_size)
                        batch = self._get_last_messages(messages)
                        logger.debug(f"Готов полный батч для категории {price_category}")
                    else:
                        # Неполный батч по таймауту - берем все сообщения
                        batch = messages
                        logger.info(
                            f"Готов неполный батч по таймауту для категории {price_category}: {len(batch)} сообщений")

                    # Добавляем готовый батч в результат
                    ready_batches[price_category] = batch

        return ready_batches

    async def clear_sent_messages(self, price_category: int):
        """
        Очистить отправленные сообщения из очереди указанной ценовой категории.

        Вызывается после успешной отправки батча для освобождения памяти
        и сброса счетчика времени первого сообщения.

        Args:
            price_category: Ценовая категория для очистки
        """
        # Используем блокировку для thread-safe операций
        async with self._lock:
            # Очищаем очередь сообщений для указанной категории
            self.message_queues[price_category] = []

            # Если очередь действительно пуста - удаляем время первого сообщения
            # (дополнительная проверка на случай race condition)
            if not self.message_queues[price_category]:
                self.first_message_time.pop(price_category, None)

    def _get_last_messages(self, messages: List[PriceMessage]) -> List[PriceMessage]:
        """
        Получить последние сообщения из очереди с ограничением max_batch_size.

        Приватный метод для формирования батча из очереди сообщений.
        Берет последние сообщения, чтобы отправлять наиболее актуальные данные.

        Args:
            messages: Список всех сообщений в очереди

        Returns:
            List[PriceMessage]: Список последних сообщений (не более max_batch_size)
        """
        if messages:
            # Вычисляем индекс начала среза: max(0, общее_количество - максимальный_размер_батча)
            # Это гарантирует, что мы возьмем последние max_batch_size сообщений
            start_index = max(0, len(messages) - self.max_batch_size)
            return messages[start_index:]
        return []

    async def get_queue_stats(self) -> Dict[int, int]:
        """
        Получить статистику очередей - количество сообщений в каждой ценовой категории.

        Полезно для мониторинга состояния очередей и отладки.

        Returns:
            Dict[int, int]: Словарь {ценовая_категория: количество_сообщений}
        """
        # Используем блокировку для получения консистентного снимка состояния
        async with self._lock:
            # Создаем словарь со статистикой по каждой категории
            return {price: len(messages) for price, messages in self.message_queues.items()}

    async def flush_all_queues(self) -> Dict[int, List[PriceMessage]]:
        """
        Получить все оставшиеся сообщения для отправки и очистить очереди.

        Используется при завершении работы приложения для отправки всех накопленных сообщений.
        После вызова этого метода все очереди будут пусты.

        Returns:
            Dict[int, List[PriceMessage]]: Все оставшиеся сообщения по ценовым категориям
        """
        all_messages = {}  # Результирующий словарь всех сообщений

        # Используем блокировку для thread-safe операций
        async with self._lock:
            # Проходим по всем очередям
            for price_category, messages in self.message_queues.items():
                if messages:
                    # Берем последние сообщения (с ограничением max_batch_size)
                    all_messages[price_category] = self._get_last_messages(messages)
                    # Очищаем очередь после извлечения сообщений
                    self.message_queues[price_category] = []

        return all_messages
