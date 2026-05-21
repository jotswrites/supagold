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

    async def send_stats(self):
        stats = get_stats()
        message = (
            f"📊 <b>GoldBot Performance</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🔢 Total Signals: {stats['total']}\n"
            f"✅ Wins: {stats['wins']}\n"
            f"❌ Losses: {stats['losses']}\n"
            f"⏳ Pending: {stats['pending']}\n"
            f"📈 Win Rate: {stats['win_rate']}%\n"
            f"💰 Total PnL: {stats['total_pnl']} pips\n"
            f"📐 Avg R:R: 1:{stats['avg_rr']}"
        )
        await self.send_message(message)

    async def send_startup_message(self):
        message = (
            "🤖 <b>GoldBot v2.0 is now online — 24/7</b>\n"
            "Multi-Symbol Dashboard\n"
            "XAU/USD | GBP/USD\n"
            "━━━━━━━━━━━━━━━━━\n"
            "🕯️ Patterns | 📐 Fib | 📏 S/R | 🔮 Harmonic"
        )
        await self.send_message(message)
