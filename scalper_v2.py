"""
Supagold Scalper v2 — Elite Standard
1H Bias Filter | Session-Aware | Volume Proxy | Two-Candle Patterns | Spread Aware | ATR Floor
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
SESSION_HOURS = (0, 24)  # All sessions

# Session profiles: (SL_mult, TP1_mult, TP2_mult, min_atr, spread_allowance_pct, require_stronger_pattern)
SESSION_PROFILES = {
    "ASIAN":   {"sl_mult": 0.8, "tp1_mult": 1.3, "tp2_mult": 2.0, "min_atr": 2.0, "max_spread_pct": 25, "strong_pattern": True},
    "LONDON":  {"sl_mult": 1.0, "tp1_mult": 1.5, "tp2_mult": 2.5, "min_atr": 3.0, "max_spread_pct": 20, "strong_pattern": False},
    "NY":      {"sl_mult": 1.1, "tp1_mult": 1.6, "tp2_mult": 2.8, "min_atr": 3.5, "max_spread_pct": 20, "strong_pattern": False},
    "DEFAULT": {"sl_mult": 1.0, "tp1_mult": 1.5, "tp2_mult": 2.5, "min_atr": 2.5, "max_spread_pct": 25, "strong_pattern": False},
}

# Per-pair spread assumptions (in pips converted to price)
SPREADS = {"XAUUSD": 0.25, "GBPUSD": 0.00012}  # Gold $0.25, Cable 1.2 pips

MEMORY_FILE = "scalper_memory.json"
ANTI_FLIP_MINUTES = 30
LOCK_HOURS = 2
TELEGRAM_OFFSET_FILE = "telegram_offset.txt"
MIN_CONFIDENCE = 50

# ─── SESSION DETECTION ────────────────────
def get_current_session():
    hour = datetime.now(timezone.utc).hour
    if 0 <= hour < 8:
        return "ASIAN"
    elif 8 <= hour < 16:
        return "LONDON"
    elif 13 <= hour < 21:
        return "NY"
    else:
        return "DEFAULT"

def get_session_profile():
    session = get_current_session()
    return SESSION_PROFILES.get(session, SESSION_PROFILES["DEFAULT"]), session

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
    if stats and stats["trades"] >= 3:
        return stats["wins"] / stats["trades"]
    return 0.55

def pair_win_rate(pair):
    stats = memory["pairs"].get(pair)
    if stats and stats["trades"] >= 3:
        return stats["wins"] / stats["trades"]
    return 0.55

def is_pair_locked(pair):
    lock = memory["locks"].get(pair)
    if not lock:
        return False
    lock_time = datetime.fromisoformat(lock["time"])
    if datetime.now(timezone.utc) - lock_time > timedelta(hours=LOCK_HOURS):
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

# ─── TELEGRAM FEEDBACK ────────────────────
def get_offset():
    if os.path.exists(TELEGRAM_OFFSET_FILE):
        with open(TELEGRAM_OFFSET_FILE) as f:
            return int(f.read().strip())
    return 0

def save_offset(offset):
    with open(TELEGRAM_OFFSET_FILE, "w") as f:
        f.write(str(offset))

def process_feedback():
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
            signal_id = None
            for word in original_text.split():
                if word.startswith("#SCALP-"):
                    signal_id = word.strip("#")
                    break
            if not signal_id or signal_id not in memory["signals"]:
                continue
            if text.strip().lower().startswith("/win"):
                outcome = "win"
            elif text.strip().lower().startswith("/loss"):
                outcome = "loss"
            else:
                continue
            if memory["signals"][signal_id].get("outcome") is None:
                memory["signals"][signal_id]["outcome"] = outcome
                pair = memory["signals"][signal_id]["pair"]
                pattern = memory["signals"][signal_id]["pattern"]
                update_memory(pair, pattern, outcome)
                unlock_pair(pair)
                logger.info(f"Feedback: {signal_id} → {outcome}")
        save_offset(offset)
    except Exception as e:
        logger.error(f"Feedback error: {e}")

def check_stats_command():
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
                stats_msg += "━━━━━━━━━━━━━━━━━\n<b>Top Patterns:</b>\n"
                for pat, s in sorted(memory["patterns"].items(), key=lambda x: x[1]["trades"], reverse=True)[:5]:
                    wr = (s["wins"]/s["trades"]*100) if s["trades"]>0 else 0
                    stats_msg += f"• {pat}: {wr:.0f}% ({s['trades']}T)\n"
                send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                requests.post(send_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": stats_msg, "parse_mode": "HTML"})
        save_offset(offset)
    except Exception as e:
        logger.error(f"Stats error: {e}")

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
            if abs(lvl - current[-1]) / max(current[-1], 0.0001) < 0.001:
                current.append(lvl)
            else:
                clusters.append(np.mean(current))
                current = [lvl]
        clusters.append(np.mean(current))
        return sorted(clusters)
    return cluster(support_levels), cluster(resistance_levels)

# ─── VOLUME PROXY ─────────────────────────
def candle_range_expansion(df1, lookback=5, multiplier=1.5):
    """Volume proxy: current 1M candle range vs average of last N candles."""
    if len(df1) < lookback + 1:
        return False, 1.0
    current_range = df1["high"].iloc[-1] - df1["low"].iloc[-1]
    avg_range = (df1["high"] - df1["low"]).iloc[-lookback-1:-1].mean()
    if avg_range <= 0:
        return False, 1.0
    ratio = current_range / avg_range
    return ratio >= multiplier, ratio

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

def detect_two_candle_patterns(prev, curr):
    """Tweezer Tops/Bottoms, Piercing Line, Dark Cloud Cover"""
    patterns = []
    # Tweezer Bottom
    if (prev["close"] < prev["open"] and curr["close"] > curr["open"] and
        abs(prev["low"] - curr["low"]) <= (prev["high"] - prev["low"]) * 0.1):
        patterns.append(("tweezer_bottom", 0.7))
    # Tweezer Top
    if (prev["close"] > prev["open"] and curr["close"] < curr["open"] and
        abs(prev["high"] - curr["high"]) <= (prev["high"] - prev["low"]) * 0.1):
        patterns.append(("tweezer_top", 0.7))
    # Piercing Line
    if (prev["close"] < prev["open"] and curr["close"] > curr["open"] and
        curr["open"] < prev["low"] and
        curr["close"] > (prev["open"] + prev["close"]) / 2 and
        curr["close"] < prev["open"]):
        patterns.append(("piercing_line", 0.75))
    # Dark Cloud Cover
    if (prev["close"] > prev["open"] and curr["close"] < curr["open"] and
        curr["open"] > prev["high"] and
        curr["close"] < (prev["open"] + prev["close"]) / 2 and
        curr["close"] > prev["open"]):
        patterns.append(("dark_cloud_cover", 0.75))
    return patterns

def is_strong_pattern(pattern_name):
    """Check if pattern is considered 'strong' for session filtering."""
    strong = {"bullish_engulfing", "bearish_engulfing", "piercing_line", "dark_cloud_cover",
              "bullish_pinbar", "bearish_pinbar", "morning_star", "evening_star"}
    return pattern_name in strong

# ─── 1H BIAS FILTER ───────────────────────
def get_1h_bias(df1h):
    """Determine 1H directional bias using EMA 21/55 alignment."""
    if df1h.empty or len(df1h) < 55:
        return "NEUTRAL"
    df1h["ema_21"] = calculate_ema(df1h, 21)
    df1h["ema_55"] = calculate_ema(df1h, 55)
    latest = df1h.iloc[-1]
    if latest["close"] > latest["ema_21"] > latest["ema_55"]:
        return "LONG"
    elif latest["close"] < latest["ema_21"] < latest["ema_55"]:
        return "SHORT"
    return "NEUTRAL"

# ─── SIGNAL GENERATION ─────────────────────
last_signal_time = {}

async def analyze_pair(symbol, bot):
    if is_pair_locked(symbol):
        return

    profile, session_name = get_session_profile()

    fetcher = DataFetcher(symbol)
    df1h = fetcher.fetch_candles("1h", outputsize=100)
    df15 = fetcher.fetch_candles("15min", outputsize=100)
    df1 = fetcher.fetch_candles("1min", outputsize=60)

    if df15.empty or df1.empty:
        return

    # ── 1H Bias Filter ──
    h1_bias = get_1h_bias(df1h) if not df1h.empty else "NEUTRAL"

    # ── Session info ──
    hour = datetime.now(timezone.utc).hour
    if not (SESSION_HOURS[0] <= hour < SESSION_HOURS[1]):
        return

    # ── ATR Floor ──
    df15["atr_14"] = calculate_atr(df15, 14)
    atr = df15["atr_14"].iloc[-1]
    if atr < profile["min_atr"]:
        return

    # ── S/R ──
    supports, resistances = find_swing_levels(df15)
    price = df1["close"].iloc[-1]
    nearest_support = max([s for s in supports if s < price], default=None)
    nearest_resistance = min([r for r in resistances if r > price], default=None)

    # ── 15M Trend ──
    df15["ema_21"] = calculate_ema(df15, 21)
    ema21 = df15["ema_21"].iloc[-1]
    trend = "UP" if price > ema21 else "DOWN"

    # ── Spread Check ──
    spread = SPREADS.get(symbol, 0.00015)
    sl_distance_potential = atr * profile["sl_mult"]
    if spread / max(sl_distance_potential, 0.0001) * 100 > profile["max_spread_pct"]:
        return

    # ── Pattern Detection ──
    curr = df1.iloc[-1]
    prev = df1.iloc[-2]
    candle_type, _ = detect_candle(curr)
    pinbar_type, _ = detect_pinbar(curr)
    engulfing_type, engulf_strength = detect_engulfing(prev, curr)
    two_candle_patterns = detect_two_candle_patterns(prev, curr)

    # ── Volume Proxy ──
    has_volume, vol_ratio = candle_range_expansion(df1)

    # ── Build pattern list ──
    active_patterns = []
    if engulfing_type:
        active_patterns.append(engulfing_type)
    if pinbar_type:
        active_patterns.append(pinbar_type)
    if candle_type:
        active_patterns.append(candle_type)
    for pname, _ in two_candle_patterns:
        active_patterns.append(pname)

    signal = None
    pattern_used = None
    entry = price

    # ── 1H Bias Agreement ──
    bias_ok_long = h1_bias in ("LONG", "NEUTRAL")
    bias_ok_short = h1_bias in ("SHORT", "NEUTRAL")

    # ── Bullish Setups ──
    if trend == "UP" and bias_ok_long:
        near_support = nearest_support and price <= nearest_support * 1.005
        near_ema = price <= ema21 * 1.002
        bounce_zone = near_support or near_ema

        if bounce_zone:
            # Engulfing + Volume
            if engulfing_type == "bullish_engulfing" and engulf_strength > 0.5 and has_volume:
                signal = "BUY"
                pattern_used = f"Bullish Engulfing + Vol @ {'Support' if near_support else 'EMA 21'}"
            # Pin Bar
            elif pinbar_type == "bullish_pinbar":
                signal = "BUY"
                pattern_used = f"Bullish Pin Bar @ {'Support' if near_support else 'EMA 21'}"
            # Two-candle patterns
            elif "piercing_line" in active_patterns and has_volume:
                signal = "BUY"
                pattern_used = f"Piercing Line @ {'Support' if near_support else 'EMA 21'}"
            elif "tweezer_bottom" in active_patterns and has_volume:
                signal = "BUY"
                pattern_used = f"Tweezer Bottom @ {'Support' if near_support else 'EMA 21'}"
            # Single candle (requires volume in Asian)
            elif candle_type in ("hammer", "dragonfly_doji"):
                if profile["strong_pattern"] and not has_volume:
                    pass  # Skip — weak confirmation in Asian
                else:
                    signal = "BUY"
                    pattern_used = f"{candle_type.replace('_',' ').title()} @ {'Support' if near_support else 'EMA 21'}"
            elif candle_type == "bullish_marubozu" and near_support and has_volume:
                signal = "BUY"
                pattern_used = "Bullish Marubozu @ Support"

    # ── Bearish Setups ──
    if trend == "DOWN" and bias_ok_short:
        near_resistance = nearest_resistance and price >= nearest_resistance * 0.995
        near_ema = price >= ema21 * 0.998
        rejection_zone = near_resistance or near_ema

        if rejection_zone:
            if engulfing_type == "bearish_engulfing" and engulf_strength > 0.5 and has_volume:
                signal = "SELL"
                pattern_used = f"Bearish Engulfing + Vol @ {'Resistance' if near_resistance else 'EMA 21'}"
            elif pinbar_type == "bearish_pinbar":
                signal = "SELL"
                pattern_used = f"Bearish Pin Bar @ {'Resistance' if near_resistance else 'EMA 21'}"
            elif "dark_cloud_cover" in active_patterns and has_volume:
                signal = "SELL"
                pattern_used = f"Dark Cloud Cover @ {'Resistance' if near_resistance else 'EMA 21'}"
            elif "tweezer_top" in active_patterns and has_volume:
                signal = "SELL"
                pattern_used = f"Tweezer Top @ {'Resistance' if near_resistance else 'EMA 21'}"
            elif candle_type in ("shooting_star", "gravestone_doji"):
                if profile["strong_pattern"] and not has_volume:
                    pass
                else:
                    signal = "SELL"
                    pattern_used = f"{candle_type.replace('_',' ').title()} @ {'Resistance' if near_resistance else 'EMA 21'}"
            elif candle_type == "bearish_marubozu" and near_resistance and has_volume:
                signal = "SELL"
                pattern_used = "Bearish Marubozu @ Resistance"

    if not signal:
        return

    # ── Anti-Flip ──
    now = datetime.now(timezone.utc)
    if symbol in last_signal_time:
        last_time, last_dir = last_signal_time[symbol]
        if (now - last_time).seconds < ANTI_FLIP_MINUTES * 60 and last_dir != signal:
            return
    last_signal_time[symbol] = (now, signal)

    # ── Confidence ──
    pat_win = pattern_win_rate(pattern_used) if pattern_used else 0.55
    pair_win = pair_win_rate(symbol)
    confidence = int((pat_win * 0.6 + pair_win * 0.4) * 100)
    if confidence < MIN_CONFIDENCE:
        return

    # ── SL/TP ──
    sl_distance = atr * profile["sl_mult"]
    tp1_distance = atr * profile["tp1_mult"]
    tp2_distance = atr * profile["tp2_mult"]
    if signal == "BUY":
        sl = round(entry - sl_distance, 5)
        tp1 = round(entry + tp1_distance, 5)
        tp2 = round(entry + tp2_distance, 5)
    else:
        sl = round(entry + sl_distance, 5)
        tp1 = round(entry - tp1_distance, 5)
        tp2 = round(entry - tp2_distance, 5)

    signal_id 
