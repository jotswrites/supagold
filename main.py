import asyncio
import sys
from datetime import datetime
from loguru import logger
from pytz import UTC
import os

# Adjust import paths for single folder structure
sys.path.insert(0, os.path.dirname(__file__))

from bot_config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TWELVE_DATA_API_KEY,
    TIMEFRAMES
)
from bot_messages.bot import SignalBot
from data.fetcher import DataFetcher

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

async def run_one_cycle():
    logger.info("─" * 40)
    logger.info("🔄 Running analysis cycle...")

    if not TELEGRAM_BOT_TOKEN or not TWELVE_DATA_API_KEY:
        logger.error("Missing API keys in environment")
        return

    bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    fetcher = DataFetcher()

    data = fetcher.fetch_all_timeframes()

    if not data:
        logger.warning("No data fetched — skipping")
        return

    for tf, df in data.items():
        if not df.empty:
            latest = df.iloc[-1]
            logger.info(f"📊 {tf}: Close={latest['close']:.2f} | {latest['datetime']}")

    await bot.send_message(
        f"💓 <b>Heartbeat</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.now(UTC).strftime('%H:%M UTC')}\n"
        f"📊 Data: {len(data)}/{len(TIMEFRAMES)} timeframes\n"
        f"🟢 Alive — analysis engine loading\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    logger.info("✅ Cycle complete")

if __name__ == "__main__":
    asyncio.run(run_one_cycle())