from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, level="INFO")

class SignalBot:
    def __init__(self, token, chat_id):
        self.bot = Bot(token=token)
        self.chat_id = chat_id

    async def send_message(self, text: str) -> bool:
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="HTML"
            )
            return True
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False
