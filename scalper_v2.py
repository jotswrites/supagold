import asyncio, sys, os
from datetime import datetime, timezone
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO")

async def main():
    logger.info("=" * 40)
    logger.info("DEBUG: Bot started")

    # Test imports one by one
    try:
        from bot_config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TWELVE_DATA_API_KEY
        logger.info("✅ bot_config loaded")
    except Exception as e:
        logger.error(f"❌ bot_config: {e}")
        return

    try:
        from bot_messages.bot import SignalBot
        logger.info("✅ bot_messages loaded")
    except Exception as e:
        logger.error(f"❌ bot_messages: {e}")
        return

    try:
        from data.fetcher import DataFetcher
        logger.info("✅ data.fetcher loaded")
    except Exception as e:
        logger.error(f"❌ data.fetcher: {e}")
        return

    try:
        from analysis.indicators import calculate_ema, calculate_atr
        logger.info("✅ analysis.indicators loaded")
    except Exception as e:
        logger.error(f"❌ analysis.indicators: {e}")
        return

    # Test data fetch
    try:
        fetcher = DataFetcher("XAUUSD")
        df = fetcher.fetch_candles("15min", outputsize=10)
        if not df.empty:
            logger.info(f"✅ Data fetch OK: {len(df)} candles, last close: {df['close'].iloc[-1]}")
        else:
            logger.error("❌ Data fetch returned empty")
    except Exception as e:
        logger.error(f"❌ Data fetch: {e}")
        return

    # Test Telegram
    try:
        bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        await bot.send_message("🧪 Debug: Bot is alive and data flows.")
        logger.info("✅ Telegram message sent")
    except Exception as e:
        logger.error(f"❌ Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(main())
