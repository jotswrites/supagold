import asyncio
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
import sys

# Configure logger
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

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
            logger.info("Message sent to Telegram")
            return True
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False

    async def send_startup_message(self):
        message = (
            "⚡ <b>Gold AI Bot — Online</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            "🟢 Monitoring XAU/USD\n"
            "⏰ Signals every 30 minutes\n"
            "📊 Timeframes: 1D | 4H | 1H | 15M\n"
            "━━━━━━━━━━━━━━━━━\n"
            "ℹ️ <i>Self-test phase. Analysis engine loading...</i>"
        )
        await self.send_message(message)

    async def send_signal(self, signal_data: dict):
        timestamp = signal_data.get('timestamp', 'N/A')
        mode = signal_data.get('mode', 'WAIT')
        confidence = signal_data.get('confidence', 0)

        message = (
            f"📊 <b>XAU/USD Signal — {timestamp}</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🎯 Mode: {mode}\n"
            f"📈 Confidence: {confidence}%\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"⏰ Next update in 30 min"
        )
        await self.send_message(message)