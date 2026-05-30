"""
Supagold Scalper v2 — Clean, Actionable, Self-Learning
"""
import asyncio, sys, os, json, time, requests
from datetime import datetime, timezone, timedelta
from loguru import logger
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from bot_config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TWELVE_DATA_API_KEY
from bot_messages.bot import SignalBot
from data.fetcher import DataFetcher
from analysis.indicators import calculate_ema, calculate_atr

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

# ─── CONFIG ───────────────────────────────
PAIRS = ["XAUUSD", "GBPUSD"]
TIMEFRAMES = {"main": "15min", "trigger": "1min"}
SESSION_HOURS = (8, 21)
SL_ATR_MULT = 1.0
TP1_ATR_MULT = 1.5
TP2_ATR_MULT = 2.5
MEMORY_FILE = "scalper_memory.json"
ANTI_FLIP_MINUTES = 30
LOCK_HOURS = 2  # auto-expire lock after this many hours
TELEGRAM_OFFSET_FILE = "telegram_offset.txt"

# ─── MEMORY ───────────────────────────────
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE) as f:
        memory = json.load(f)
else:
    memory = {"patterns": {}, "pairs": {}, "signals": {}, "locks": {}}

def save_memory():
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def update_memory(pair, pattern, outcome):
    if pair not in memory["pairs"]:
        memory["pairs"][pair] = {"wins": 0, "trades": 0}
    memory["pairs"][pair]["trades"] += 1
    if outcome == "win":
        memory["pairs"][pair]["wins"] += 1

    if pattern not in memory["patterns"]:
        memory["patterns"][pattern] = {"wins": 0, "trades": 0}
    memory["patterns"][pattern]["trades"] += 1
    if outcome == "win":
        memory["patterns"][pattern]["wins"] += 1
    save_memory()

def pattern_win_rate(pattern):
    stats = memory["patterns"].get(pattern)
    if stats and stats["trades"] >= 5:
        return stats["wins"] / stats["trades"]
    return 0.55

def pair_win_rate(pair):
    stats = memory["pairs"].get(pair)
    if stats and stats["trades"] >= 5:
        return stats["wins"] / stats["trades"]
    return 0.55

def is_pair_locked(pair):
    lock = memory["locks"].get(pair)
    if not lock:
        return False
    lock_time = datetime.fromisoformat(lock["time"])
    if datetime.now(timezone.utc) - lock_time > timedelta(hours=LOCK_HOURS):
        # Auto-expire lock
        signal_id = lock.get("signal_id")
        if signal_id and signal_id in memory["signals"]:
            memory["signals"][signal_id]["outcome"] = "expired"
        del memory["locks"][pair]
        save_memory()
        return False
    return True

def lock_pair(pair, signal_id):
    memory["locks"][pair] = {"time": datetime.now(timezone.utc).isoformat(), "signal_id": signal_id}
    save_memory()

def unlock_pair(pair):
    if pair in memory["locks"]:
        del memory["locks"][pair]
        save_memory()

# ─── TELEGRAM FEEDBACK POLLING ────────────
def get_offset():
    if os.path.exists(TELEGRAM_OFFSET_FILE):
        with open(TELEGRAM_OFFSET_FILE) as f:
            return int(f.read().strip())
    return 0

def save_offset(offset):
    with open(TELEGRAM_OFFSET_FILE, "w") as f:
        f.write(str(offset))

def process_feedback():
    """Check Telegram for /win or /loss replies and update memory."""
    token = TELEGRAM_BOT_TOKEN
    offset = get_offset()
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"offset": offset, "timeout": 5}
    try:
        r = requests.get(url, params=params)
        data = r.json()
        if not data.get("ok"):
            return
        for update in data["result"]:
            update_id = update["update_id"]
            if update_id >= offset:
                offset = update_id + 1
            msg = update.get("message", {})
            text = msg.get("text", "")
            reply_to = msg.get("reply_to_message", {})
            if not text or not reply_to:
                continue
            original_text = reply_to.get("text", "")
            # Check if replying to a signal message (contains a signal ID)
            signal_id = None
            for word in original_text.split():
                if word.startswith("#SCALP-"):
                    signal_id = word.strip("#")
                    break
            if not signal_id or signal_id not in memory["signals"]:
                continue
            # Process /win or /loss
            if text.strip().lower().startswith("/win"):
                outcome = "win"
            elif text.strip().lower().startswith("/loss"):
                outcome = "loss"
            else:
                continue
            # Only update if not already logged
            if memory["signals"][signal_id].get("outcome") is None:
                memory["signals"][signal_id]["outcome"] = outcome
                pair = memory["signals"][signal_id]["pair"]
                pattern = memory["signals"][signal_id]["pattern"]
                update_memory(pair, pattern, outcome)
                unlock_pair(pair)
                logger.info(f"Feedback: {signal_id} marked as {outcome}")
        save_offset(offset)
    except Exception as e:
        logger.error(f"Feedback error: {e}")

def check_stats_command():
    """If someone typed /stats, reply with current performance."""
    token = TELEGRAM_BOT_TOKEN
    offset = get_offset()
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"offset": offset, "timeout": 5}
    try:
        r = requests.get(url, params=params)
        data = r.json()
        if not data.get("ok"):
            return
        for update in data["result"]:
            update_id = update["update_id"]
            if update_id >= offset:
                offset = update_id + 1
            msg = update.get("message", {})
            text = msg.get("text", "")
            if text.strip().lower().startswith("/stats"):
                stats_msg = "📊 <b>Scalper Memory</b>\n━━━━━━━━━━━━━━━━━\n"
                for pair in PAIRS:
                    s = memory["pairs"].get(pair, {"wins":0,"trades":0})
                    wr = (s["wins"]/s["trades"]*100) if s["trades"]>0 else 0
                    stats_msg += f"<b>{pair}</b>: {s['wins']}W/{s['trades']}T ({wr:.0f}%)\n"
                stats_msg += "━━━━━━━━━━━━━━━━━\n<b>Patterns:</b>\n"
                for pat, s in sorted(memory["patterns"].items(), key=lambda x: x[1]["trades"], reverse=True)[:5]:
                    wr = (s["wins"]/s["trades"]*100) if s["trades"]>0 else 0
                    stats_msg += f"• {pat}: {wr:.0f}% ({s['trades']} trades)\n"
                # Send reply
                send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                requests.post(send_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": stats_msg, "parse_mode": "HTML"})
        save_offset(offset)
    except Exception as e:
        logger.error(f"Stats command error: {e}")

# ─── S/R DETECTION ─────────────────────────
def find_swing_levels(df, window=5):
    highs, lows = df["high"].values, df["low"].values
    resistance_levels = []
    support_levels = []
    for i in range(window, len(df) - window):
        if highs[i] == max(highs[i-window:i+window+1]):
            resistance_levels.append(highs[i])
        if lows[i] == min(lows[i-window:i+window+1]):
            support_levels.append(lows[i])
    def cluster(levels):
        if not levels:
            return []
        levels = sorted(set(levels))
        clusters = []
        current = [levels[0]]
        for lvl in levels[1:]:
            if abs(lvl - current[-1]) / current[-1] < 0.001:
                current.append(lvl)
            else:
                clusters.append(np.mean(current))
                current = [lvl]
        clusters.append(np.mean(current))
        return sorted(clusters)
    return cluster(support_levels), cluster(resistance_levels)

# ─── PATTERN DETECTION ─────────────────────
def detect_candle(row):
    body = abs(row["close"] - row["open"])
    upper = row["high"] - max(row["open"], row["close"])
    lower = min(row["open"], row["close"]) - row["low"]
    total = row["high"] - row["low"]
    if total == 0:
        return "doji", 0
    if body <= total * 0.1:
        if lower >= total * 0.6:
            return "dragonfly_doji", 0.8
        elif upper >= total * 0.6:
            return "gravestone_doji", 0.8
        return "doji", 0.5
    if body <= total * 0.35:
        if lower >= 2 * body and upper <= body * 0.3:
            return "hammer", 0.75
        if upper >= 2 * body and lower <= body * 0.3:
            return "shooting_star", 0.75
    if body >= total * 0.8:
        if row["close"] > row["open"]:
            return "bullish_marubozu", 0.7
        else:
            return "bearish_marubozu", 0.7
    return None, 0

def detect_engulfing(prev, curr):
    prev_body = abs(prev["close"] - prev["open"])
    curr_body = abs(curr["close"] - curr["open"])
    if curr_body < prev_body:
        return None, 0
    if prev["close"] < prev["open"] and curr["close"] > curr["open"] and curr["open"] <= prev["close"] and curr["close"] >= prev["open"]:
        return "bullish_engulfing", min(1.0, curr_body / (prev_body + 0.00001) * 0.7)
    if prev["close"] > prev["open"] and curr["close"] < curr["open"] and curr["open"] >= prev["close"] and curr["close"] <= prev["open"]:
        return "bearish_engulfing", min(1.0, curr_body / (prev_body + 0.00001) * 0.7)
    return None, 0

def detect_pinbar(row):
    body = abs(row["close"] - row["open"])
    upper = row["high"] - max(row["open"], row["close"])
    lower = min(row["open"], row["close"]) - row["low"]
    total = row["high"] - row["low"]
    if total == 0:
        return None, 0
    if lower >= 3 * body and upper <= body * 0.3:
        return "bullish_pinbar", 0.8
    if upper >= 3 * body and lower <= body * 0.3:
        return "bearish_pinbar", 0.8
    return None, 0

# ─── SIGNAL GENERATION ─────────────────────
last_signal_time = {}

async def analyze_pair(symbol, bot):
    # Skip if pair is locked (unresolved signal)
    if is_pair_locked(symbol):
        logger.info(f"{symbol} locked — waiting for feedback on previous signal.")
        return

    fetcher = DataFetcher(symbol)
    df15 = fetcher.fetch_candles("15min", outputsize=100)
    df1 = fetcher.fetch_candles("1min", outputsize=60)
    if df15.empty or df1.empty:
        return

    hour = datetime.now(timezone.utc).hour
    if not (SESSION_HOURS[0] <= hour < SESSION_HOURS[1]):
        return

    supports, resistances = find_swing_levels(df15)
    price = df1["close"].iloc[-1]
    nearest_support = max([s for s in supports if s < price], default=None)
    nearest_resistance = min([r for r in resistances if r > price], default=None)

    df15["ema_21"] = calculate_ema(df15, 21)
    ema21 = df15["ema_21"].iloc[-1]
    trend = "UP" if price > ema21 else "DOWN"

    df15["atr_14"] = calculate_atr(df15, 14)
    atr = df15["atr_14"].iloc[-1]
    if atr <= 0:
        return

    curr = df1.iloc[-1]
    prev = df1.iloc[-2]
    candle_type, strength = detect_candle(curr)
    pinbar_type, pin_strength = detect_pinbar(curr)
    engulfing_type, engulf_strength = detect_engulfing(prev, curr)

    signal = None
    pattern_used = None
    entry = price
    sl = tp1 = tp2 = 0

    if trend == "UP" and nearest_support and price <= nearest_support * 1.002:
        if engulfing_type == "bullish_engulfing" and engulf_strength > 0.6:
            signal = "BUY"
            pattern_used = "Bullish Engulfing @ Support"
        elif pinbar_type == "bullish_pinbar":
            signal = "BUY"
            pattern_used = "Bullish Pin Bar @ Support"
        elif candle_type in ("hammer", "dragonfly_doji"):
            signal = "BUY"
            pattern_used = f"{candle_type.replace('_',' ').title()} @ Support"

    if trend == "DOWN" and nearest_resistance and price >= nearest_resistance * 0.998:
        if engulfing_type == "bearish_engulfing" and engulf_strength > 0.6:
            signal = "SELL"
            pattern_used = "Bearish Engulfing @ Resistance"
        elif pinbar_type == "bearish_pinbar":
            signal = "SELL"
            pattern_used = "Bearish Pin Bar @ Resistance"
        elif candle_type in ("shooting_star", "gravestone_doji"):
            signal = "SELL"
            pattern_used = f"{candle_type.replace('_',' ').title()} @ Resistance"

    if not signal:
        return

    now = datetime.now(timezone.utc)
    if symbol in last_signal_time:
        last_time, last_dir = last_signal_time[symbol]
        if (now - last_time).seconds < ANTI_FLIP_MINUTES * 60 and last_dir != signal:
            return
    last_signal_time[symbol] = (now, signal)

    pat_win = pattern_win_rate(pattern_used) if pattern_used else 0.55
    pair_win = pair_win_rate(symbol)
    confidence = int((pat_win * 0.6 + pair_win * 0.4) * 100)
    if confidence < 55:
        return

    sl_distance = atr * SL_ATR_MULT
    tp1_distance = atr * TP1_ATR_MULT
    tp2_distance = atr * TP2_ATR_MULT
    if signal == "BUY":
        sl = round(entry - sl_distance, 5)
        tp1 = round(entry + tp1_distance, 5)
        tp2 = round(entry + tp2_distance, 5)
    else:
        sl = round(entry + sl_distance, 5)
        tp1 = round(entry - tp1_distance, 5)
        tp2 = round(entry - tp2_distance, 5)

    # Generate signal ID and lock pair
    signal_id = f"SCALP-{now.strftime('%Y%m%d%H%M%S')}-{symbol}"
    memory["signals"][signal_id] = {
        "pair": symbol, "pattern": pattern_used, "entry": entry,
        "signal": signal, "time": now.isoformat(), "outcome": None
    }
    lock_pair(symbol, signal_id)
    save_memory()

    message = (
        f"⚡ <b>SCALP — {symbol}</b> — <code>#{signal_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🎯 {signal} @ {entry:.5f}\n"
        f"🛑 SL: {sl:.5f} | ✅ TP1: {tp1:.5f} | ✅ TP2: {tp2:.5f}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📐 {pattern_used}\n"
        f"📊 Confidence: {confidence}% | ATR: {atr:.5f}\n"
        f"📈 Trend: {trend} | S: {nearest_support:.5f} | R: {nearest_resistance:.5f}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🤖 Supagold Scalper v2 | ⏰ {now.strftime('%H:%M UTC')}\n"
        f"<i>Reply to this message with /win or /loss</i>"
    )
    await bot.send_message(message)
    logger.info(f"Signal sent: {signal_id}")

async def main():
    process_feedback()
    check_stats_command()

    bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    for pair in PAIRS:
        try:
            await analyze_pair(pair, bot)
        except Exception as e:
            logger.error(f"Error {pair}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
