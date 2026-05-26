import asyncio
import sys
import time
from datetime import datetime
from loguru import logger
from pytz import UTC
import os
import traceback

sys.path.insert(0, os.path.dirname(__file__))

from bot_config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TWELVE_DATA_API_KEY
from bot_messages.bot import SignalBot
from data.fetcher import DataFetcher

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

SYMBOLS = ["XAU/USD", "GBP/USD"]

async def run_one_cycle():
    logger.info("─" * 40)
    logger.info("🔄 DEBUG MODE — Testing Telegram connection")

    # Test 1: Check secrets exist
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN is empty or missing")
        return
    if not TELEGRAM_CHAT_ID:
        logger.error("❌ TELEGRAM_CHAT_ID is empty or missing")
        return
    if not TWELVE_DATA_API_KEY:
        logger.error("❌ TWELVE_DATA_API_KEY is empty or missing")
        return

    logger.info("✅ All secrets present")

    # Test 2: Try sending a simple message
    try:
        bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        await bot.send_message("🧪 <b>DEBUG TEST</b>\n━━━━━━━━━━━━━━━━━\nIf you see this, Telegram works.\n⏰ " + datetime.now(UTC).strftime('%H:%M UTC'))
        logger.info("✅ Test message sent")
    except Exception as e:
        logger.error(f"❌ Telegram send failed: {e}")
        logger.error(traceback.format_exc())
        return

    # Test 3: Fetch data
    for symbol in SYMBOLS:
        try:
            logger.info(f"Testing data fetch for {symbol}...")
            fetcher = DataFetcher(symbol)
            data = fetcher.fetch_all_timeframes()
            if data:
                await bot.send_message(f"✅ {symbol}: Data OK — {len(data)} timeframes fetched")
            else:
                await bot.send_message(f"⚠️ {symbol}: No data returned")
        except Exception as e:
            logger.error(f"❌ Data fetch error for {symbol}: {e}")
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(run_one_cycle())
