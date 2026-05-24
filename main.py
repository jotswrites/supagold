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
from engine.quality_gate import calculate_confidence
from engine.news_filter import is_high_impact_news_within
from engine.ghost_trader import simulate_ghost_trade
from storage.database import (
    init_db, log_signal, log_journal, update_journal_outcome,
    open_position, get_position, close_position, update_position_sl
)

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

SYMBOLS = ["XAU/USD", "GBP/USD"]
TIMEFRAMES = ["1day", "4h", "1h", "15min", "5min", "1min"]
TF_LABELS = {"1day": "1D", "4h": "4H", "1h": "1H", "15min": "15M", "5min": "5M", "1min": "1M"}

CONFIDENCE_THRESHOLD = 75
CONFIDENCE_EXIT_THRESHOLD = 40

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
        "atr": latest["atr_14"], "rsi": latest["rsi_14"], "patterns": active[:5],
        "bias": "🟢" if latest["close"] > latest["ema_21"] > latest["ema_55"] else
                "🔴" if latest["close"] < latest["ema_21"] < latest["ema_55"] else "⚪",
        "bias_dir": "LONG" if latest["close"] > latest["ema_21"] > latest["ema_55"] else
                    "SHORT" if latest["close"] < latest["ema_21"] < latest["ema_55"] else "NEUTRAL"
    }

def classify_trade_type(results):
    if "1D" not in results or "4H" not in results:
        return "SCALP"
    daily_bias = results["1D"]["bias_dir"]
    h4_bias = results["4H"]["bias_dir"]
    primary_bias = results.get("15M", results.get("1H"))["bias_dir"]
    if daily_bias == primary_bias and h4_bias == primary_bias:
        return "SWING"
    elif h4_bias == primary_bias:
        return "SWING_LITE"
    return "SCALP"

def calculate_sl_tp(price, atr, bias_dir, trade_type):
    mult_sl = 1.5
    if trade_type == "SWING":
        mult_tp1, mult_tp2 = 3, 5
    elif trade_type == "SWING_LITE":
        mult_tp1, mult_tp2 = 2.5, 4
    else:
        mult_tp1, mult_tp2 = 1.5, 2.5
    if bias_dir == "LONG":
        return {"sl": round(price - atr * mult_sl, 2), "tp1": round(price + atr * mult_tp1, 2), "tp2": round(price + atr * mult_tp2, 2)}
    elif bias_dir == "SHORT":
        return {"sl": round(price + atr * mult_sl, 2), "tp1": round(price - atr * mult_tp1, 2), "tp2": round(price - atr * mult_tp2, 2)}
    return None

async def analyze_symbol(symbol, bot):
    # --- News filter check ---
    blackout, event_name = is_high_impact_news_within()
    if blackout:
        logger.info(f"{symbol}: News blackout ({event_name}). Skipping.")
        return

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

    primary = results.get("15M", results.get("1H", results.get("4H")))
    patterns = primary.get("patterns", [])
    fib_1h = analyze_fibonacci(data.get("1h")) if "1h" in data else None
    sr_1h = analyze_sr(data.get("1h")) if "1h" in data else None
    vol_15m = analyze_volume(data.get("15min")) if "15min" in data else None

    confidence, score_breakdown = calculate_confidence(results, patterns, fib_1h, sr_1h, vol_15m)

    # Journal EVERY signal thought (live or ghost)
    trade_type = classify_trade_type(results) if primary["bias_dir"] != "NEUTRAL" else "NONE"
    journal_id = log_journal(symbol, primary["bias_dir"], confidence, score_breakdown, patterns, trade_type)

    # --- Manage existing position ---
    active_position = get_position(symbol)
    if active_position:
        current_price = primary["price"]
        direction = active_position["direction"]
        entry = active_position["entry"]
        sl = active_position["sl"]
        tp1 = active_position["tp1"]
        tp2 = active_position["tp2"]

        if direction == "LONG":
            if current_price >= tp2:
                close_position(symbol, "tp2", round(tp2 - entry, 2))
                await bot.send_message(f"✅ {symbol} — TP2 HIT\nProfit: {round(tp2 - entry, 2)} pips")
                return
            elif current_price >= tp1:
                update_position_sl(symbol, entry)
                await bot.send_message(f"🔄 {symbol} — TP1 HIT, SL trailed to entry")
                return
            elif current_price <= sl:
                close_position(symbol, "sl", round(entry - sl, 2))
                await bot.send_message(f"❌ {symbol} — SL HIT\nLoss: {round(entry - sl, 2)} pips")
                return
        else:
            if current_price <= tp2:
                close_position(symbol, "tp2", round(entry - tp2, 2))
                await bot.send_message(f"✅ {symbol} — TP2 HIT\nProfit: {round(entry - tp2, 2)} pips")
                return
            elif current_price <= tp1:
                update_position_sl(symbol, entry)
                await bot.send_message(f"🔄 {symbol} — TP1 HIT, SL trailed to entry")
                return
            elif current_price >= sl:
                close_position(symbol, "sl", round(sl - entry, 2))
                await bot.send_message(f"❌ {symbol} — SL HIT\nLoss: {round(sl - entry, 2)} pips")
                return

        if confidence < CONFIDENCE_EXIT_THRESHOLD:
            pnl = round(current_price - entry, 2) if direction == "LONG" else round(entry - current_price, 2)
            close_position(symbol, "confidence_exit", pnl)
            await bot.send_message(f"⚠️ {symbol} — Exit (confidence {confidence}%)\nPnL: {pnl} pips")
            return

        pnl = round(current_price - entry, 2) if direction == "LONG" else round(entry - current_price, 2)
        await bot.send_message(
            f"🔄 {symbol} — Position Update\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"{'🟢 LONG' if direction == 'LONG' else '🔴 SHORT'} from {entry}\n"
            f"Current: {current_price:.4f} ({'+' if pnl > 0 else ''}{pnl} pips)\n"
            f"SL: {sl} | TP1: {tp1} | TP2: {tp2}\n"
            f"Confidence: {confidence}%\n"
            f"━━━━━━━━━━━━━━━━━"
        )
        return

    # --- Ghost trade simulation (all signals) ---
    one_min_data = data.get("1min", None)
    if one_min_data is not None and not one_min_data.empty and primary["bias_dir"] != "NEUTRAL":
        sl_tp = calculate_sl_tp(primary["price"], primary["atr"], primary["bias_dir"], trade_type)
        if sl_tp:
            outcome, pnl = simulate_ghost_trade(
                symbol, one_min_data, primary["bias_dir"],
                primary["price"], sl_tp["sl"], sl_tp["tp1"], sl_tp["tp2"],
                confidence, trade_type
            )
            update_journal_outcome(journal_id, outcome, pnl)

    # --- New signal check ---
    if confidence < CONFIDENCE_THRESHOLD:
        logger.info(f"{symbol}: Confidence {confidence}% — below threshold, no signal")
        return

    bias_dir = primary["bias_dir"]
    if bias_dir == "NEUTRAL":
        return

    sl_tp = calculate_sl_tp(primary["price"], primary["atr"], bias_dir, trade_type)
    if not sl_tp:
        return

    log_signal(symbol, "BUY" if bias_dir == "LONG" else "SELL",
               primary["price"], sl_tp["sl"], sl_tp["tp1"], sl_tp["tp2"],
               confidence, trade_type)
    open_position(symbol, "LONG" if bias_dir == "LONG" else "SHORT",
                  primary["price"], sl_tp["sl"], sl_tp["tp1"], sl_tp["tp2"],
                  confidence, trade_type)

    emoji = "🐋" if trade_type == "SWING" else "🐟"
    direction_text = "BUY" if bias_dir == "LONG" else "SELL"
    mtf_lines = "\n".join([f"{r['bias']} {lbl}: {r['price']:.4f}" for lbl, r in results.items() if lbl in ["1D","4H","1H","15M"]])

    message = (
        f"{emoji} {trade_type} SIGNAL — {symbol}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🎯 {direction_text} at {primary['price']:.4f}\n"
        f"🛑 SL: {sl_tp['sl']:.4f}\n"
        f"✅ TP1: {sl_tp['tp1']:.4f}\n"
        f"✅ TP2: {sl_tp['tp2']:.4f}\n"
        f"📊 Confidence: {confidence}%\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📐 Multi-TF:\n{mtf_lines}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Breakdown: MTF:{score_breakdown['mtf_alignment']} | "
        f"Pattern:{score_breakdown['pattern_quality']} | "
        f"Location:{score_breakdown['location']} | "
        f"Vol:{score_breakdown['volume']} | "
        f"Session:{score_breakdown['session']} | "
        f"Regime:{score_breakdown['regime']}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🕯️ Patterns: {', '.join(patterns[:3]) if patterns else 'None'}"
    )
    await bot.send_message(message)

async def run_one_cycle():
    logger.info("─" * 40)
    logger.info("🔄 v4.0 — Position-aware + News filter + Ghost trading")
    init_db()

    bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

    for symbol in SYMBOLS:
        try:
            await analyze_symbol(symbol, bot)
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")

if __name__ == "__main__":
    asyncio.run(run_one_cycle())
