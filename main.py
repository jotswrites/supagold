import asyncio
import sys
from datetime import datetime
from loguru import logger
from pytz import UTC
import os

sys.path.insert(0, os.path.dirname(__file__))

from bot_config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TWELVE_DATA_API_KEY
from bot_messages.bot import SignalBot
from data.fetcher import DataFetcher
from analysis.indicators import calculate_ema, calculate_atr, calculate_rsi
from analysis.candlestick_patterns import CandlestickPatterns
from analysis.fibonacci import analyze_fibonacci
from analysis.support_resistance import analyze_sr
from analysis.volume_analysis import analyze_volume
from analysis.harmonic_patterns import analyze_harmonic
from storage.database import log_signal

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

SYMBOLS = ["XAU/USD", "GBP/USD"]
TIMEFRAMES = ["1day", "4h", "1h", "15min", "5min", "1min"]
TF_LABELS = {"1day": "1D", "4h": "4H", "1h": "1H", "15min": "15M", "5min": "5M", "1min": "1M"}

def analyze_timeframe(df, label):
    if df.empty or len(df) < 55:
        return None
    df["ema_21"] = calculate_ema(df, 21)
    df["ema_55"] = calculate_ema(df, 55)
    df["atr_14"] = calculate_atr(df, 14)
    df["rsi_14"] = calculate_rsi(df, 14)
    patterns = CandlestickPatterns(df)
    all_patterns = patterns.get_all_patterns()
    latest_p = all_patterns.iloc[-1]
    active = [name.replace("_", " ").title() for name, d in latest_p.items() if d]
    latest = df.iloc[-1]
    return {
        "price": latest["close"], "ema21": latest["ema_21"], "ema55": latest["ema_55"],
        "atr": latest["atr_14"], "rsi": latest["rsi_14"], "patterns": active[:3],
        "bias": "🟢" if latest["close"] > latest["ema_21"] > latest["ema_55"] else
                "🔴" if latest["close"] < latest["ema_21"] < latest["ema_55"] else "⚪",
        "bias_dir": "LONG" if latest["close"] > latest["ema_21"] > latest["ema_55"] else
                    "SHORT" if latest["close"] < latest["ema_21"] < latest["ema_55"] else "NEUTRAL"
    }

def calculate_sl_tp(price, atr, bias_dir, multiplier=1.5):
    if bias_dir == "LONG":
        return {"sl": round(price - atr*multiplier, 2), "tp1": round(price + atr*2, 2), "tp2": round(price + atr*3, 2)}
    elif bias_dir == "SHORT":
        return {"sl": round(price + atr*multiplier, 2), "tp1": round(price - atr*2, 2), "tp2": round(price - atr*3, 2)}
    return None

async def analyze_symbol(symbol, bot):
    fetcher = DataFetcher(symbol)
    data = fetcher.fetch_all_timeframes()
    if not data:
        return

    results = {}
    for tf, df in data.items():
        label = TF_LABELS.get(tf, tf)
        r = analyze_timeframe(df, label)
        if r:
            results[label] = r

    if not results:
        return

    lines = []
    for label in ["1D", "4H", "1H", "15M", "5M", "1M"]:
        if label in results:
            r = results[label]
            lines.append(f"{r['bias']} {label}: {r['price']:.4f} | RSI {r['rsi']:.0f} | ATR {r['atr']:.2f}")

    primary = results.get("15M", results.get("1H", results.get("4H")))
    patterns_text = "\n".join([f"• {p}" for p in primary["patterns"]]) if primary["patterns"] else "• None"

    fib_1h = analyze_fibonacci(data.get("1h")) if "1h" in data and not data["1h"].empty else None
    sr_1h = analyze_sr(data.get("1h")) if "1h" in data and not data["1h"].empty else None
    vol_15m = analyze_volume(data.get("15min")) if "15min" in data and not data["15min"].empty else None
    harmonic_4h = analyze_harmonic(data.get("4h")) if "4h" in data and not data["4h"].empty else []

    sl_tp = calculate_sl_tp(primary["price"], primary["atr"], primary["bias_dir"])

    if primary["bias_dir"] != "NEUTRAL" and sl_tp:
        direction = "BUY" if primary["bias_dir"] == "LONG" else "SELL"
        signal_line = f"🎯 <b>SIGNAL: {direction}</b>"
        sl_tp_lines = f"🛑 <b>SL:</b> {sl_tp['sl']:.4f}\n✅ <b>TP1:</b> {sl_tp['tp1']:.4f}\n✅ <b>TP2:</b> {sl_tp['tp2']:.4f}"
        log_signal(symbol, direction, primary["price"], sl_tp['sl'], sl_tp['tp1'], sl_tp['tp2'])
    else:
        signal_line = "⚪ <b>NO TRADE</b>"
        sl_tp_lines = "Wait for clearer setup"

    fib_lines = ""
    if fib_1h:
        fib_lines = f"📐 <b>Fibonacci (1H):</b>\n• Swing: {fib_1h['swing_low']:.4f} → {fib_1h['swing_high']:.4f}\n• 61.8%: {fib_1h['level_618']:.4f}\n• 38.2%: {fib_1h['level_382']:.4f}\n"

    sr_lines = ""
    if sr_1h:
        sr_lines = f"📏 <b>S/R Levels (1H):</b>\n• Round: {sr_1h['round_support']:.0f} / {sr_1h['round_resistance']:.0f}\n"
        if sr_1h["swing_supports"]:
            sr_lines += f"• Support: {sr_1h['swing_supports'][0]:.4f}\n"
        if sr_1h["swing_resistances"]:
            sr_lines += f"• Resistance: {sr_1h['swing_resistances'][0]:.4f}\n"

    vol_line = f"📊 <b>Volume:</b> {vol_15m['description']} ({vol_15m['volume_ratio']}x avg)\n" if vol_15m else ""

    harmonic_lines = ""
    if harmonic_4h:
        harmonic_lines = "🔮 <b>Harmonic (4H):</b>\n"
        for name, dir_, price in harmonic_4h[-2:]:
            harmonic_lines += f"• {name} ({dir_}) @ {price:.4f}\n"

    message = (
        f"📊 <b>{symbol} — Full Analysis</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.now(UTC).strftime('%H:%M UTC')}\n"
        f"{signal_line}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines) +
        f"\n━━━━━━━━━━━━━━━━━\n"
        f"{sl_tp_lines}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{fib_lines}"
        f"{sr_lines}"
        f"{vol_line}"
        f"{harmonic_lines}"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🕯️ <b>15M Patterns:</b>\n{patterns_text}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⏰ Next update in 30 min"
    )

    await bot.send_message(message)

async def run_one_cycle():
    logger.info("─" * 40)
    logger.info("🔄 Running analysis for all symbols...")

    bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

    for symbol in SYMBOLS:
        try:
            await analyze_symbol(symbol, bot)
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")

if __name__ == "__main__":
    asyncio.run(run_one_cycle())
