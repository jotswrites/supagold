import asyncio, sys, os
from datetime import datetime
from loguru import logger
from pytz import UTC

sys.path.insert(0, os.path.dirname(__file__))

from bot_config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from bot_messages.bot import SignalBot
from data.fetcher import DataFetcher
from analysis.indicators import calculate_ema, calculate_atr, calculate_rsi
from analysis.candlestick_patterns import CandlestickPatterns
from analysis.fibonacci import analyze_fibonacci
from analysis.support_resistance import analyze_sr
from analysis.volume_analysis import analyze_volume
from engine.quality_gate import calculate_confidence

logger.remove()
logger.add(sys.stdout, level="INFO")

SYMBOLS = ["XAU/USD", "GBP/USD"]
TF_LABELS = {"1day":"1D","4h":"4H","1h":"1H","15min":"15M","5min":"5M","1min":"1M"}

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
    active = [name.replace("_"," ").title() for name,d in latest_p.items() if d]
    latest = df.iloc[-1]
    bias_dir = "LONG" if latest["close"] > latest["ema_21"] > latest["ema_55"] else "SHORT" if latest["close"] < latest["ema_21"] < latest["ema_55"] else "NEUTRAL"
    return {
        "price":latest["close"],"ema21":latest["ema_21"],"ema55":latest["ema_55"],
        "atr":latest["atr_14"],"rsi":latest["rsi_14"],"patterns":active,
        "bias":"🟢" if bias_dir=="LONG" else "🔴" if bias_dir=="SHORT" else "⚪",
        "bias_dir":bias_dir
    }

async def force_analysis():
    bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    for symbol in SYMBOLS:
        fetcher = DataFetcher(symbol)
        data = fetcher.fetch_all_timeframes()
        if not data:
            await bot.send_message(f"⚠️ {symbol}: No data")
            continue
        results = {}
        for tf,df in data.items():
            label = TF_LABELS.get(tf,tf)
            r = analyze_timeframe(df,label)
            if r:
                results[label] = r
        if not results:
            await bot.send_message(f"⚠️ {symbol}: Could not analyze")
            continue
        primary = results.get("15M", results.get("1H", results.get("4H")))
        fib_1h = analyze_fibonacci(data.get("1h")) if "1h" in data else None
        sr_1h = analyze_sr(data.get("1h")) if "1h" in data else None
        vol_15m = analyze_volume(data.get("15min")) if "15min" in data else None
        confidence, breakdown = calculate_confidence(results, primary["patterns"], fib_1h, sr_1h, vol_15m)
        mtf_lines = "\n".join([f"{r['bias']} {lbl}: {r['price']:.4f} | RSI {r['rsi']:.0f}" for lbl,r in results.items() if lbl in ["1D","4H","1H","15M"]])
        message = (
            f"⚡ FORCE SIGNAL — {symbol}\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"⏰ {datetime.now(UTC).strftime('%H:%M UTC')}\n"
            f"Bias: {primary['bias_dir']} | Confidence: {confidence}%\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"{mtf_lines}\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"MTF:{breakdown.get('mtf_alignment',0)} | Pat:{breakdown.get('pattern_quality',0)} | "
            f"Loc:{breakdown.get('location',0)} | Vol:{breakdown.get('volume',0)} | "
            f"Ses:{breakdown.get('session',0)} | Reg:{breakdown.get('regime',0)}\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"Patterns: {', '.join(primary['patterns'][:3]) if primary['patterns'] else 'None'}"
        )
        await bot.send_message(message)

if __name__ == "__main__":
    asyncio.run(force_analysis())
