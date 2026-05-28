"""
Supagold Scalper v1.0
5-minute cycle, London/NY only, strict risk controls.
"""
import asyncio
import sys
import time
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

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

# === SCALPER CONFIGURATION ===
SYMBOLS = ["XAU/USD"]
SCALP_TIMEFRAMES = ["15min", "5min", "1min"]
MAX_CONSECUTIVE_LOSSES = 3
DAILY_PROFIT_TARGET = 30   # pips
DAILY_LOSS_LIMIT = 15      # pips
RISK_PER_TRADE = 0.5       # % of account (for position sizing later)
MIN_RR_RATIO = 1.5         # minimum risk:reward

# Session tracking
session_pnl = 0
consecutive_losses = 0
active_trade = None

def is_trading_session():
    """Only trade London/NY: 07:00-21:00 UTC."""
    hour = datetime.now(UTC).hour
    return 7 <= hour <= 21

async def analyze_and_signal():
    global session_pnl, consecutive_losses, active_trade
    
    logger.info("─" * 30)
    logger.info("⚡ Scalper cycle...")
    
    if not is_trading_session():
        logger.info("Outside trading hours. Skipping.")
        return
    
    if session_pnl >= DAILY_PROFIT_TARGET:
        logger.info(f"Daily profit target reached (+{session_pnl} pips). Shutting down for today.")
        return
    
    if session_pnl <= -DAILY_LOSS_LIMIT:
        logger.info(f"Daily loss limit hit ({session_pnl} pips). Shutting down for today.")
        return
    
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        logger.info(f"Max consecutive losses ({MAX_CONSECUTIVE_LOSSES}). Pausing for session.")
        return
    
    bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    
    for symbol in SYMBOLS:
        try:
            fetcher = DataFetcher(symbol)
            data = {}
            for tf in SCALP_TIMEFRAMES:
                df = fetcher.fetch_candles(tf, outputsize=100)
                if not df.empty:
                    data[tf] = df
            
            if len(data) < 3:
                continue
            
            # === 15M Momentum ===
            df15 = data["15min"]
            df15["ema_21"] = calculate_ema(df15, 21)
            df15["ema_55"] = calculate_ema(df15, 55)
            latest_15 = df15.iloc[-1]
            
            if latest_15["close"] > latest_15["ema_21"] > latest_15["ema_55"]:
                momentum = "LONG"
            elif latest_15["close"] < latest_15["ema_21"] < latest_15["ema_55"]:
                momentum = "SHORT"
            else:
                continue  # No clear momentum, skip
            
            # === 5M Pullback Check ===
            df5 = data["5min"]
            df5["ema_21"] = calculate_ema(df5, 21)
            df5["atr_14"] = calculate_atr(df5, 14)
            latest_5 = df5.iloc[-1]
            prev_5 = df5.iloc[-2]
            
            atr_5m = latest_5["atr_14"]
            if atr_5m <= 0:
                continue
            
            # Pullback condition: price pulled back to EMA 21
            pullback = False
            if momentum == "LONG" and latest_5["close"] > latest_5["ema_21"] and prev_5["close"] <= prev_5["ema_21"]:
                pullback = True
            elif momentum == "SHORT" and latest_5["close"] < latest_5["ema_21"] and prev_5["close"] >= prev_5["ema_21"]:
                pullback = True
            
            if not pullback:
                continue
            
            # === 1M Entry Trigger ===
            df1 = data["1min"]
            if len(df1) < 5:
                continue
            
            df1["rsi_7"] = calculate_rsi(df1, 7)
            patterns = CandlestickPatterns(df1)
            all_p = patterns.get_all_patterns()
            latest_p = all_p.iloc[-1]
            active_patterns = [n.replace("_"," ").title() for n,d in latest_p.items() if d]
            
            latest_1 = df1.iloc[-1]
            
            # Entry filter: RSI not overbought/oversold
            if momentum == "LONG" and latest_1["rsi_7"] > 70:
                continue
            if momentum == "SHORT" and latest_1["rsi_7"] < 30:
                continue
            
            # Pattern or volume confirmation
            bullish_triggers = ["hammer", "bullish engulfing", "piercing line", "morning star", "tweezer bottom"]
            bearish_triggers = ["shooting star", "bearish engulfing", "dark cloud cover", "evening star", "tweezer top"]
            
            has_trigger = False
            for p in active_patterns:
                name = p.lower()
                if momentum == "LONG" and name in bullish_triggers:
                    has_trigger = True
                    break
                if momentum == "SHORT" and name in bearish_triggers:
                    has_trigger = True
                    break
            
            if not has_trigger:
                continue
            
            # === Calculate Entry, SL, TP ===
            entry = latest_1["close"]
            sl_distance = atr_5m * 1.0  # Tight stop using 5M ATR
            tp1_distance = sl_distance * MIN_RR_RATIO
            tp2_distance = sl_distance * (MIN_RR_RATIO + 0.5)
            
            if momentum == "LONG":
                sl = entry - sl_distance
                tp1 = entry + tp1_distance
                tp2 = entry + tp2_distance
            else:
                sl = entry + sl_distance
                tp1 = entry - tp1_distance
                tp2 = entry - tp2_distance
            
            # === Send Signal ===
            direction = "BUY" if momentum == "LONG" else "SELL"
            message = (
                f"⚡ <b>SCALP — {symbol}</b>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🎯 {direction} at {entry:.4f}\n"
                f"🛑 SL: {sl:.4f} ({abs(entry-sl):.1f} pts)\n"
                f"✅ TP1: {tp1:.4f} (+{abs(tp1-entry):.1f} pts)\n"
                f"✅ TP2: {tp2:.4f} (+{abs(tp2-entry):.1f} pts)\n"
                f"📊 R:R = 1:{MIN_RR_RATIO}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"📈 15M: {'🟢' if momentum=='LONG' else '🔴'} {momentum} | 5M: Pullback to EMA\n"
                f"🕯️ 1M Trigger: {', '.join(active_patterns[:2]) if active_patterns else 'Price action'}\n"
                f"⏱️ Max hold: 15 minutes\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"💰 Session P&L: {session_pnl:+.1f} pips | "
                f"{'🟢' if consecutive_losses==0 else '🔴' if consecutive_losses>=2 else '🟡'} Loss streak: {consecutive_losses}"
            )
            await bot.send_message(message)
            logger.info(f"⚡ Scalp signal sent: {symbol} {direction}")
            
            # Track state (will be refined with ghost trading later)
            active_trade = {
                "symbol": symbol, "direction": momentum, "entry": entry,
                "sl": sl, "tp1": tp1, "tp2": tp2, "time": datetime.now(UTC)
            }
            
        except Exception as e:
            logger.error(f"Scalper error on {symbol}: {e}")

async def run_scalper():
    logger.info("=" * 45)
    logger.info("   SUPAGOLD SCALPER v1.0 STARTED")
    logger.info("   5-minute cycle | London/NY only")
    logger.info("=" * 45)
    
    bot = SignalBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    
    # Startup message only once per session
    if is_trading_session():
        await bot.send_message(
            "⚡ <b>Supagold Scalper Online</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            "⏱️ 5-min checks | XAU/USD\n"
            f"🎯 Profit target: +{DAILY_PROFIT_TARGET} pips\n"
            f"🛑 Loss limit: -{DAILY_LOSS_LIMIT} pips\n"
            f"❌ Max consecutive losses: {MAX_CONSECUTIVE_LOSSES}"
        )
    
    await analyze_and_signal()

if __name__ == "__main__":
    asyncio.run(run_scalper())
