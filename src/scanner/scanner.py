import logging
import random

import aiohttp
import asyncio

from typing import Optional, Any, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


from src.service.utils import get_id, get_pixel_url, get_check_url
from src.api.api import api_get_with_refresh
from src.service.file_handler import FileHandler
from src.bot.telegram import send_telegram_message
from src.bot.channel_manager import ChannelManager
from src.bot.topic_manager import TopicManager
from src.config import (
    BOT_TOKEN,
    CHAT_ID,
    HEADERS,
    MIN_COST,
    PRICE_TOPICS,
    MAX_COST,
    BATCH_DELAY,
    MESSAGE_SIZE,
    GROUP_ID,
    EXCLUDE_COSTS,
)

logger = logging.getLogger(__name__)


class CellStatus(Enum):
    FOR_MINT = "for_mint"
    OCCUPIED = "occupied"
    ERROR = "error"
    AVAILABLE = "available"
    FOR_MINT_NOT_AVAILABLE = "for_mint_not_available"


@dataclass
class CellResult:
    cell_id: str
    x: int
    y: int
    status: CellStatus
    data: Optional[Dict[str, Any]] = None
    link: Optional[str] = None
    error: Optional[str] = None
    cost: Optional[int] = None


class PixelScanner:
    file_handler: FileHandler = FileHandler

    def __init__(self, pixels_filename: str):
        self.pixels_filename = pixels_filename

        self.free_cells: List[CellResult] = []
        self.free_cells_not_available: List[CellResult] = []
        self.available_cells: List[CellResult] = []
        self.occupied_cells: List[CellResult] = []
        self.error_cells: List[CellResult] = []
        self.processed_count = 0
        self._lock = asyncio.Lock()

        # Батчинг для Telegram сообщений
        self._telegram_queue: List[str] = []
        self._telegram_batch_size = MESSAGE_SIZE
        self._telegram_batch_delay = 2.0  # секунды
        self._start_time: Optional[datetime] = None
        self.df = None

        # self.channel_manager: ChannelManager = ChannelManager(
        #     bot_token=BOT_TOKEN,
        #     price_channels=PRICE_CHANNELS,
        #     batch_size=MESSAGE_SIZE,
        #     batch_delay=BATCH_DELAY,
        # )

        self.topic_manager: TopicManager = TopicManager(
            bot_token=BOT_TOKEN,
            group_id=GROUP_ID,
            topic_ids_filename=PRICE_TOPICS,
            batch_size=MESSAGE_SIZE,
            batch_delay=BATCH_DELAY,
        )

    async def check_cell(self, session: aiohttp.ClientSession, x: int, y: int) -> CellResult:
        """Проверить одну ячейку с улучшенной обработкой ошибок"""
        cell_id = get_id(x, y)
        url = get_check_url(cell_id)

        try:
            response = await api_get_with_refresh(url, HEADERS, session=session)

            if response is None:
                return CellResult(
                    cell_id=cell_id, x=x, y=y,
                    status=CellStatus.ERROR,
                    error='No response'
                )

            if response.status == 200:
                data = await response.json()
                return await self._process_successful_response(cell_id, x, y, data)
            else:
                error_msg = f'HTTP {response.status}'
                logger.warning(f"{error_msg} для ячейки {cell_id} ({x}, {y})")
                return CellResult(
                    cell_id=cell_id, x=x, y=y,
                    status=CellStatus.ERROR,
                    error=error_msg
                )

        except asyncio.TimeoutError:
            error_msg = "Timeout"
            logger.warning(f"Таймаут для ячейки {cell_id} ({x}, {y})")
            return CellResult(
                cell_id=cell_id, x=x, y=y,
                status=CellStatus.ERROR,
                error=error_msg
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка для ячейки {cell_id} ({x}, {y}): {e}")
            return CellResult(
                cell_id=cell_id, x=x, y=y,
                status=CellStatus.ERROR,
                error=error_msg
            )

    async def _process_successful_response(
            self,
            cell_id: str,
            x: int,
            y: int,
            data: Dict[str, Any]
    ) -> CellResult:
        """Обработать успешный ответ от API"""
        meta_data = data.get('metaData', {})
        item_address = meta_data.get('itemAddress', '')
        is_available = meta_data.get('isAvailable', False)

        link = get_pixel_url(x=x, y=y)

        if item_address == '':
            cost = 1
            if is_available:
                status = CellStatus.FOR_MINT
            else:
                status = CellStatus.FOR_MINT_NOT_AVAILABLE
        else:
            cost: int = meta_data.get('nextPrice', 0)
            cost = cost and cost / 1_000_000_000

            if is_available:
                status = CellStatus.AVAILABLE
            else:
                status = CellStatus.OCCUPIED

        if (
            MIN_COST <= cost <= MAX_COST
            and
            cost not in EXCLUDE_COSTS
        ):
            # msg = f"Найдена ячейка {'' if is_available else '(НЕ ДОСТУПНА ДЛЯ МИНТА)'} за {cost} $PX ({x}, {y}): {link}"

            msg = f'{cost} $PX ({x},{y}): {link}'

            logger.info(msg)
            # await self.channel_manager.add_message(cost, x, y, link)
            # await self._queue_telegram_message(msg)
            await self.topic_manager.add_message(
                cost=cost,
                x=x,
                y=y,
                link=link,
            )

        checking_result = CellResult(
            cell_id=cell_id,
            x=x,
            y=y,
            status=status,
            data=data,
            link=link,
            cost=cost,
        )

        self._update_pixel_data(checking_result)

        return checking_result

    async def _queue_telegram_message(self, message: str):
        """Добавить сообщение в очередь для батчевой отправки"""
        async with self._lock:
            self._telegram_queue.append(message)

    async def _process_telegram_queue(self):
        """Обработать очередь Telegram сообщений батчами"""
        while True:
            try:
                messages_to_send = []
                async with self._lock:
                    if len(self._telegram_queue) >= self._telegram_batch_size:
                        messages_to_send = self._telegram_queue[:self._telegram_batch_size]
                        self._telegram_queue = self._telegram_queue[self._telegram_batch_size:]

                if messages_to_send:
                    combined_message = "\n\n".join(messages_to_send)
                    try:
                        await send_telegram_message(
                            bot_token=BOT_TOKEN,
                            chat_id=CHAT_ID,
                            text=combined_message
                        )
                    except Exception as telegram_error:
                        logger.error(f"Ошибка отправки Telegram сообщения: {telegram_error}")

                await asyncio.sleep(self._telegram_batch_delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в обработке Telegram очереди: {e}")
                await asyncio.sleep(self._telegram_batch_delay)

    async def _flush_telegram_queue(self):
        """Отправить оставшиеся сообщения из очереди"""
        async with self._lock:
            if self._telegram_queue:
                combined_message = "\n\n".join(self._telegram_queue)
                self._telegram_queue.clear()

                try:
                    await send_telegram_message(
                        bot_token=BOT_TOKEN,
                        chat_id=CHAT_ID,
                        text=combined_message
                    )
                except Exception as telegram_error:
                    logger.error(f"Ошибка отправки финальных Telegram сообщений: {telegram_error}")

    async def _update_progress(self, total_cells: int, log_interval: int = 100):
        """Обновить прогресс обработки"""
        async with self._lock:
            self.processed_count += 1
            if self.processed_count % log_interval == 0:
                progress = (self.processed_count / total_cells) * 100
                elapsed = (datetime.now() - self._start_time).total_seconds()
                rate = self.processed_count / elapsed if elapsed > 0 else 0
                eta = (total_cells - self.processed_count) / rate if rate > 0 else 0

                logger.info(
                    f"Обработано {self.processed_count}/{total_cells} ячеек "
                    f"({progress:.1f}%) - {rate:.1f} ячеек/сек - ETA: {eta:.0f}с"
                )

    def _categorize_results(self, results: List[CellResult]):
        """Категоризировать результаты по типам"""
        for result in results:
            if result.status == CellStatus.FOR_MINT:
                self.free_cells.append(result)
            elif result.status == CellStatus.FOR_MINT_NOT_AVAILABLE:
                self.free_cells_not_available.append(result)
            elif result.status == CellStatus.AVAILABLE:
                self.available_cells.append(result)
            elif result.status == CellStatus.OCCUPIED:
                self.occupied_cells.append(result)
            elif result.status == CellStatus.ERROR:
                self.error_cells.append(result)

    def _get_coordinates(self, min_cost: int = 0) -> List[Tuple[int, int]]:
        self.df = self.file_handler.read_file(self.pixels_filename, index_col=['x', 'y'])

        indexes = self.df.loc[self.df['cost'] <= min_cost].index.to_list()
        random.shuffle(indexes)

        return indexes

    def _save_pixel_data(self):
        self.file_handler.write_file(self.pixels_filename, self.df)

    def _update_pixel_data(self, result: CellResult):
        self.df.loc[(result.x, result.y), 'cost'] = result.cost
        self.df.loc[(result.x, result.y), 'available'] = result.status in (CellStatus.AVAILABLE, CellStatus.FOR_MINT)

    async def scan_canvas(self, max_concurrent: int = 50, timeout: float = 30.0,
                          retry_errors: bool = True, max_retries: int = 2):
        """
        Сканировать холст с улучшенными возможностями
        """
        logger.info("Начинаем сканирование холста...")
        self._start_time = datetime.now()
        # Запускаем менеджер тем
        await self.topic_manager.start()

        # Запускаем обработчик Telegram очереди
        telegram_task = asyncio.create_task(self._process_telegram_queue())

        total_cells = 1

        try:
            while True:
                coordinates = self._get_coordinates(min_cost=MIN_COST)
                total_cells = len(coordinates)
                logger.info(f"Всего пикселей для проверки: {total_cells}")

                # Настройка соединения с оптимизациями
                timeout_config = aiohttp.ClientTimeout(total=timeout)
                connector = aiohttp.TCPConnector(
                    limit=max_concurrent,
                    limit_per_host=max_concurrent,
                    ttl_dns_cache=300,  # Кэш DNS на 5 минут
                    use_dns_cache=True,
                    keepalive_timeout=30,
                    enable_cleanup_closed=True
                )

                semaphore = asyncio.Semaphore(max_concurrent)

                async def bounded_check_cell(x: int, y: int, session: aiohttp.ClientSession) -> CellResult:
                    async with semaphore:
                        result = await self.check_cell(session, x, y)
                        await self._update_progress(total_cells)
                        return result

                async with aiohttp.ClientSession(
                        connector=connector,
                        headers=HEADERS,
                        timeout=timeout_config
                ) as session:
                    # Первый проход
                    tasks = [bounded_check_cell(x, y, session) for x, y in coordinates]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Обработка результатов и сбор ошибок
                    processed_results = []
                    error_coordinates = []

                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            x, y = coordinates[i]
                            cell_id = get_id(x, y)
                            logger.error(f"Исключение при обработке ячейки {cell_id} ({x}, {y}): {result}")
                            error_result = CellResult(
                                cell_id=cell_id, x=x, y=y,
                                status=CellStatus.ERROR,
                                error=str(result)
                            )
                            processed_results.append(error_result)
                            if retry_errors:
                                error_coordinates.append((x, y))
                        else:
                            processed_results.append(result)
                            if result.status == CellStatus.ERROR and retry_errors:
                                error_coordinates.append((result.x, result.y))

                    # Повторные попытки для ошибок
                    if retry_errors and error_coordinates:
                        for retry_attempt in range(max_retries):
                            if not error_coordinates:
                                break

                            logger.info(
                                f"Повторная попытка {retry_attempt + 1}/{max_retries} для {len(error_coordinates)} ячеек")

                            retry_tasks = [bounded_check_cell(x, y, session) for x, y in error_coordinates]
                            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)

                            new_error_coordinates = []
                            for i, result in enumerate(retry_results):
                                x, y = error_coordinates[i]

                                if isinstance(result, Exception):
                                    logger.error(f"Повторная ошибка для ячейки ({x}, {y}): {result}")
                                    if retry_attempt == max_retries - 1:  # Последняя попытка
                                        cell_id = get_id(x, y)
                                        error_result = CellResult(
                                            cell_id=cell_id, x=x, y=y,
                                            status=CellStatus.ERROR,
                                            error=f"После {max_retries} попыток: {str(result)}"
                                        )
                                        # Обновляем результат в processed_results
                                        for j, prev_result in enumerate(processed_results):
                                            if prev_result.x == x and prev_result.y == y:
                                                processed_results[j] = error_result
                                                break
                                    else:
                                        new_error_coordinates.append((x, y))
                                else:
                                    # Успешный результат - обновляем в processed_results
                                    for j, prev_result in enumerate(processed_results):
                                        if prev_result.x == x and prev_result.y == y:
                                            processed_results[j] = result
                                            break

                                    if result.status == CellStatus.ERROR:
                                        new_error_coordinates.append((x, y))

                            error_coordinates = new_error_coordinates

                            if error_coordinates:
                                await asyncio.sleep(1)  # Пауза между повторными попытками

                    # Категоризируем все результаты
                    self._categorize_results(processed_results)

                    # сохраним информацию о пикселях
                    self._save_pixel_data()
        except KeyboardInterrupt:
            logger.info("Заверщение работы...")
        finally:
            # Останавливаем обработчик Telegram и отправляем оставшиеся сообщения
            telegram_task.cancel()
            try:
                await telegram_task
            except asyncio.CancelledError:
                pass

            await self._flush_telegram_queue()
            await self.topic_manager.stop()

    def get_statistics(self) -> Dict[str, Any]:
        """Получить подробную статистику сканирования"""
        total = len(self.free_cells) + len(self.occupied_cells) + len(self.error_cells)
        return {
            'total_processed': total,
            'free_cells': len(self.free_cells),
            'occupied_cells': len(self.occupied_cells),
            'error_cells': len(self.error_cells),
            'success_rate': (total - len(self.error_cells)) / total * 100 if total > 0 else 0,
            'free_cell_rate': len(self.free_cells) / total * 100 if total > 0 else 0,
            'free_cell_links': [cell.link for cell in self.free_cells if cell.link]
        }
