from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from loguru import logger
import sys
from storage.database import get_stats, init_db

logger.remove()
logger.add(sys.stdout, level="INFO")

class SignalBot:
    def __init__(self, token, chat_id):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.app = Application.builder().token(token).build()
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("signal", self.signal_command))
        init_db()

    async def send_message(self, text: str) -> bool:
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
            return True
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = get_stats()
        message = (
            f"📊 <b>Performance</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🔢 Total: {stats['total']} | ✅ {stats['wins']} | ❌ {stats['losses']}\n"
            f"📈 Win Rate: {stats['win_rate']}%\n"
            f"💰 PnL: {stats['total_pnl']} pips"
        )
        await update.message.reply_text(message, parse_mode="HTML")

    async def signal_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Force an immediate analysis and return the current signal status."""
        await update.message.reply_text("🔍 Running analysis...")
        
        # Import here to avoid circular imports
        import asyncio
        from main import analyze_symbol, SYMBOLS, TF_LABELS
        from data.fetcher import DataFetcher
        from analysis.indicators import calculate_ema, calculate_atr, calculate_rsi
        from analysis.candlestick_patterns import CandlestickPatterns
        from analysis.fibonacci import analyze_fibonacci
        from analysis.support_resistance import analyze_sr
        from analysis.volume_analysis import analyze_volume
        from engine.quality_gate import calculate_confidence
        from datetime import datetime
        from pytz import UTC
        
        for symbol in SYMBOLS:
            fetcher = DataFetcher(symbol)
            data = fetcher.fetch_all_timeframes()
            if not data:
                await update.message.reply_text(f"⚠️ {symbol}: No data")
                continue
            
            tf_labels = {"1day": "1D", "4h": "4H", "1h": "1H", "15min": "15M", "5min": "5M", "1min": "1M"}
            results = {}
            for tf, df in data.items():
                label = tf_labels.get(tf, tf)
                if len(df) >= 55:
                    df["ema_21"] = calculate_ema(df, 21)
                    df["ema_55"] = calculate_ema(df, 55)
                    df["atr_14"] = calculate_atr(df, 14)
                    df["rsi_14"] = calculate_rsi(df, 14)
                    patterns = CandlestickPatterns(df)
                    all_p = patterns.get_all_patterns()
                    latest_p = all_p.iloc[-1]
                    active = [n.replace("_", " ").title() for n, d in latest_p.items() if d]
                    latest = df.iloc[-1]
                    bias_dir = "LONG" if latest["close"] > latest["ema_21"] > latest["ema_55"] else "SHORT" if latest["close"] < latest["ema_21"] < latest["ema_55"] else "NEUTRAL"
                    results[label] = {
                        "price": latest["close"], "atr": latest["atr_14"], "rsi": latest["rsi_14"],
                        "bias_dir": bias_dir, "patterns": active,
                        "bias": "🟢" if bias_dir == "LONG" else "🔴" if bias_dir == "SHORT" else "⚪"
                    }
            
            if not results:
                await update.message.reply_text(f"⚠️ {symbol}: Could not analyze")
                continue
            
            primary = results.get("15M", results.get("1H", results.get("4H")))
            fib_1h = analyze_fibonacci(data.get("1h")) if "1h" in data else None
            sr_1h = analyze_sr(data.get("1h")) if "1h" in data else None
            vol_15m = analyze_volume(data.get("15min")) if "15min" in data else None
            
            confidence, breakdown = calculate_confidence(results, primary.get("patterns", []), fib_1h, sr_1h, vol_15m)
            
            mtf_lines = "\n".join([f"{r['bias']} {lbl}: {r['price']:.4f} | RSI {r['rsi']:.0f}" for lbl, r in results.items() if lbl in ["1D","4H","1H","15M"]])
            
            msg = (
                f"🔍 {symbol} — {datetime.now(UTC).strftime('%H:%M UTC')}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"Bias: {primary['bias_dir']}\n"
                f"Confidence: {confidence}% (threshold: 75%)\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"{mtf_lines}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"MTF:{breakdown.get('mtf_alignment',0)} | Pat:{breakdown.get('pattern_quality',0)} | "
                f"Loc:{breakdown.get('location',0)} | Vol:{breakdown.get('volume',0)} | "
                f"Ses:{breakdown.get('session',0)} | Reg:{breakdown.get('regime',0)}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"Patterns: {', '.join(primary.get('patterns', [])[:3]) if primary.get('patterns') else 'None'}"
            )
            await update.message.reply_text(msg, parse_mode="HTML")

    async def start_polling(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

    async def send_startup_message(self):
        message = (
            "🤖 <b>GoldBot v4.0 — Self-Learning Strategist</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            "Commands:\n"
            "/signal — Get current analysis now\n"
            "/stats — View performance"
        )
        await self.send_message(message)
