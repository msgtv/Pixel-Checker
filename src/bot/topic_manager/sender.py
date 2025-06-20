import asyncio
import logging
import random

from typing import List
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest, TelegramForbiddenError

from src.bot.topic_manager.rate_limiter import RateLimiter
from src.bot.topic_manager.msg_formatter import PriceMessage, MessageFormatter


logger = logging.getLogger(__name__)


class MessageSender:
    """Класс для отправки сообщений в Telegram"""

    def __init__(self, bot: Bot, group_id: str, rate_limiter: RateLimiter):
        self.bot = bot
        self.group_id = group_id
        self.rate_limiter = rate_limiter

    async def send_batch_to_topic(
            self,
            topic_id: int,
            messages: List[PriceMessage],
            price_category: int,
    ) -> bool:
        """Отправить пачку сообщений в тему"""
        await self.rate_limiter.check_group_limit()
        await self.rate_limiter.wait_if_needed()

        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                combined_message = MessageFormatter.format_batch_message(messages)

                if len(combined_message.encode('utf-8')) > 4000:
                    return await self._send_large_message_in_parts(topic_id, messages, price_category)

                await self.bot.send_message(
                    chat_id=self.group_id,
                    text=combined_message,
                    message_thread_id=topic_id,
                    disable_web_page_preview=True,
                    parse_mode='HTML'
                )

                self.rate_limiter.update_after_send()
                logger.info(f"Отправлено {len(messages)} сообщений в тему '{price_category} $PX'")
                return True

            except TelegramRetryAfter as e:
                wait_time = e.retry_after + random.uniform(1, 3)
                logger.warning(f"RetryAfter {e.retry_after}с для темы {price_category}. Ожидание {wait_time:.1f}с")
                await asyncio.sleep(wait_time)
                self.rate_limiter.handle_error()

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

    async def _send_large_message_in_parts(
            self,
            topic_id: int,
            messages: List[PriceMessage],
            price_category: int,
    ) -> bool:
        """Отправить большое сообщение частями"""
        parts = self._split_messages_into_parts(messages)
        success_count = 0

        for i, part in enumerate(parts):
            if i > 0:
                await asyncio.sleep(self.rate_limiter.min_send_interval)

            success = await self._send_message_part(topic_id, part)
            if success:
                success_count += 1

        logger.info(f"Отправлено {success_count}/{len(parts)} частей в тему '{price_category} $PX'")
        return success_count > 0

    def _split_messages_into_parts(self, messages: List[PriceMessage]) -> List[List[PriceMessage]]:
        """Разделить сообщения на части для отправки"""
        parts = []
        current_part = []
        current_size = 0

        for msg in messages:
            line = MessageFormatter.format_message(msg)
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

        return parts

    async def _send_message_part(self, topic_id: int, part: List[PriceMessage]) -> bool:
        """Отправить часть сообщения"""
        message_lines = [MessageFormatter.format_message(msg) for msg in part]
        message_lines += ['\nauthor: @odincryptan']
        combined_message = "\n\n".join(message_lines)

        try:
            await self.bot.send_message(
                chat_id=self.group_id,
                text=combined_message,
                message_thread_id=topic_id,
                disable_web_page_preview=True,
                parse_mode='HTML'
            )
            self.rate_limiter.update_after_send()
            return True

        except TelegramRetryAfter as e:
            logger.warning(f"RetryAfter при отправке части: ожидание {e.retry_after}с")
            await asyncio.sleep(e.retry_after + random.uniform(1, 2))
            try:
                await self.bot.send_message(
                    chat_id=self.group_id,
                    text=combined_message,
                    message_thread_id=topic_id,
                    disable_web_page_preview=True,
                    parse_mode='HTML'
                )
                self.rate_limiter.update_after_send()
                return True
            except Exception as e2:
                logger.error(f"Ошибка при повторной отправке части: {e2}")
                return False

        except Exception as e:
            logger.error(f"Ошибка отправки части: {e}")
            return False