import time
import asyncio
from datetime import datetime
from pytz import UTC
from loguru import logger
import sys

sys.path.insert(0, '/home/Supagoldbot/supagoldbot')

from bot_config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TWELVE_DATA_API_KEY
from bot_messages.bot import SignalBot
from main import run_one_cycle

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

CHECK_INTERVAL_MINUTES = 30

async def run_scheduler():
    logger.info("=" * 45)
    logger.info("   GOLDBOT SCHEDULER v1.0 STARTED — 24/7")
    logger.info("   Timeframes: 1D | 4H | 1H | 15M | 5M | 1M")
    logger.info("=" * 45)

    bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    await bot.send_message(
        "🤖 <b>GoldBot v1.0 is now online — 24/7</b>\n"
        "Full 6-Timeframe Dashboard active.\n"
        "1M | 5M | 15M | 1H | 4H | 1D\n"
        "Signals every 30 minutes.\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🕯️ Patterns | 📐 Fibonacci | 📏 S/R | 📊 Volume"
    )

    while True:
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        logger.info(f"\n[{now}] Running MTF analysis...")

        try:
            await run_one_cycle()
        except Exception as e:
            logger.error(f"  Scheduler error: {e}")
            try:
                await bot.send_message(f"⚠️ <b>GoldBot Error:</b> {str(e)[:200]}")
            except:
                pass

        logger.info(f"  Sleeping {CHECK_INTERVAL_MINUTES} minutes...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    asyncio.run(run_scheduler())
