import asyncio
import sys
from datetime import datetime
from loguru import logger
from pytz import UTC
import os

sys.path.insert(0, os.path.dirname(__file__))

from bot_config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TWELVE_DATA_API_KEY,
    TIMEFRAMES
)
from bot_messages.bot import SignalBot
from data.fetcher import DataFetcher
from analysis.indicators import calculate_ema, calculate_atr, calculate_rsi
from analysis.candlestick_patterns import CandlestickPatterns

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

async def run_one_cycle():
    logger.info("─" * 40)
    logger.info("🔄 Running analysis cycle...")

    if not TELEGRAM_BOT_TOKEN or not TWELVE_DATA_API_KEY:
        logger.error("Missing API keys")
        return

    bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    fetcher = DataFetcher()
    data = fetcher.fetch_all_timeframes()

    if not data:
        logger.warning("No data — skipping")
        return

    # Find the primary timeframe for pattern detection
    primary_tf = "15min"
    if primary_tf not in data or data[primary_tf].empty:
        logger.error("No 15min data available")
        return

    df = data[primary_tf]

    # Calculate indicators
    df["ema_21"] = calculate_ema(df, 21)
    df["ema_55"] = calculate_ema(df, 55)
    df["atr_14"] = calculate_atr(df, 14)
    df["rsi_14"] = calculate_rsi(df, 14)

    # Detect candlestick patterns
    patterns = CandlestickPatterns(df)
    all_patterns = patterns.get_all_patterns()

    # Get the latest candle patterns
    latest = all_patterns.iloc[-1]
    active_patterns = [name.replace("_", " ").title() for name, detected in latest.items() if detected]

    # Get latest price data
    latest_candle = df.iloc[-1]
    price = latest_candle["close"]
    ema21 = latest_candle["ema_21"]
    ema55 = latest_candle["ema_55"]
    atr = latest_candle["atr_14"]
    rsi = latest_candle["rsi_14"]

    # Determine bias
    if price > ema21 and ema21 > ema55:
        bias = "🟢 Bullish"
    elif price < ema21 and ema21 < ema55:
        bias = "🔴 Bearish"
    else:
        bias = "⚪ Neutral"

    # Build signal message
    patterns_text = "\n".join([f"• {p}" for p in active_patterns[:5]]) if active_patterns else "• No significant patterns detected"

    message = (
        f"📊 <b>XAU/USD Signal</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.now(UTC).strftime('%H:%M UTC')}\n"
        f"💰 Price: <b>{price:.2f}</b>\n"
        f"📈 Bias: {bias}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📐 <b>Indicators (15M):</b>\n"
        f"• EMA 21: {ema21:.2f}\n"
        f"• EMA 55: {ema55:.2f}\n"
        f"• ATR(14): {atr:.2f}\n"
        f"• RSI(14): {rsi:.1f}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🕯️ <b>Candlestick Patterns:</b>\n"
        f"{patterns_text}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⏰ Next update in 30 min"
    )

    await bot.send_message(message)
    logger.info("✅ Signal sent")

if __name__ == "__main__":
    asyncio.run(run_one_cycle())
