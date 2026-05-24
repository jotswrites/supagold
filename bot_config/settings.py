import os

TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SYMBOL = "XAU/USD"
TIMEFRAMES = ["1day", "4h", "1h", "15min", "5min", "1min"]
PRIMARY_TIMEFRAME = "15min"

CONFIDENCE_THRESHOLD = 70
RISK_PERCENT = 1.0
SIGNAL_INTERVAL_MINUTES = 30

STRATEGY_WEIGHTS = {
    "candlestick_patterns": 0.20,
    "price_action": 0.15,
    "supply_demand": 0.10,
    "support_resistance": 0.15,
    "fibonacci": 0.10,
    "moving_averages": 0.10,
    "volume": 0.05,
    "momentum": 0.10,
    "harmonic_patterns": 0.05
}

LOG_LEVEL = "INFO"
LOG_FILE = "logs/bot.log"

# === Self-Learning (updated weekly by self-review engine) ===
# These weights are adjusted automatically based on journal performance.
# Do not edit manually unless resetting.
