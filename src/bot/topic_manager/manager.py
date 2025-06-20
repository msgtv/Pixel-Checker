import asyncio
import logging
import random
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from src.service.file_handler import FileHandler


logger = logging.getLogger(__name__)


class Manager:
    """Класс для управления темами форума"""

    def __init__(self, bot: Bot, group_id: str, topic_ids_filename: str):
        self.bot = bot
        self.group_id = group_id
        self.topic_ids_filename = topic_ids_filename
        self.topic_ids = FileHandler.read_json(topic_ids_filename)

    @staticmethod
    def _generate_topic_name(price_category: str) -> str:
        is_locked = price_category[0] == '_'

        if is_locked:
            return f'{price_category.strip("_")} $PX [locked]'
        return f'{price_category} $PX'


    async def get_or_create_topic_id(self, price_category: str) -> Optional[int]:
        """Получить или создать ID темы для ценовой категории"""
        topic_id = self.topic_ids.get(price_category, None)

        if topic_id is None:
            try:
                await asyncio.sleep(2)
                topic_name = self._generate_topic_name(price_category)
                topic = await self.bot.create_forum_topic(
                    chat_id=self.group_id,
                    name=topic_name,
                )

                self.topic_ids[price_category] = topic.message_thread_id
                topic_id = topic.message_thread_id

                FileHandler.write_json(self.topic_ids_filename, self.topic_ids)
                logger.info(f"Создана новая тема '{topic_name}' с ID {topic_id}")

            except TelegramRetryAfter as e:
                logger.warning(f"RetryAfter при создании темы для {price_category}: ожидание {e.retry_after}с")
                await asyncio.sleep(e.retry_after + random.uniform(1, 3))
                return None
            except Exception as e:
                logger.error(f"Ошибка получения ID темы для категории {price_category}: {e}")
                return None

        return topic_id

    def save_topic_ids(self):
        """Сохранить ID тем в файл"""
        FileHandler.write_json(self.topic_ids_filename, self.topic_ids)