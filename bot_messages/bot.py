from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
import sys
from storage.database import get_stats, init_db

logger.remove()
logger.add(sys.stdout, level="INFO")

class SignalBot:
    def __init__(self, token, chat_id):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        init_db()

    async def send_message(self, text: str) -> bool:
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
            return True
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False

    async def send_startup_message(self):
        message = (
            "🤖 <b>GoldBot v4.0 — Self-Learning Strategist</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            "🐋 SWING | 🐟 SCALP — 4-7 signals/day\n"
            "XAU/USD | GBP/USD\n"
            "✅ News filter active\n"
            "👻 Ghost trading active\n"
            "📓 Journal logging active\n"
            "Only signals when confidence ≥ 75%"
        )
        await self.send_message(message)
