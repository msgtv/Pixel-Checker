import logging
from typing import List
from dataclasses import dataclass
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class PriceMessage:
    cost: int
    x: int
    y: int
    link: str
    timestamp: datetime


class MessageFormatter:
    """Класс для форматирования сообщений"""

    @staticmethod
    def format_message(msg: PriceMessage) -> str:
        """Форматирование одного сообщения"""
        return f"<b><a href='{msg.link}'>{msg.x},{msg.y}</a></b>"

    @staticmethod
    def format_batch_message(messages: List[PriceMessage]) -> str:
        """Форматирование пачки сообщений"""
        message_lines = []
        for msg in messages:
            message_lines.append(MessageFormatter.format_message(msg))

        message_lines.append(
            f'\n{"=" * len("author: @odincryptan")}\nauthor: @odincryptan\n'
            # f'{" " * len("author: ")}<b><a href="https://app.tonkeeper.com/transfer/UQCku2Rt-aU7_AiNG-7Lz66ruaywXDFXUGL8kbJ8UaEFwXPD">donate</a></b>'
        )

        return "\n\n".join(message_lines)