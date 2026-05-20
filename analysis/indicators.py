import pandas as pd
import numpy as np
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, level="INFO")


def calculate_ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    return df[column].ewm(span=period, adjust=False).mean()


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"].shift(1)
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(span=period, adjust=False).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    delta = df[column].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = calculate_ema(df, fast)
    ema_slow = calculate_ema(df, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(pd.DataFrame({"close": macd_line}), signal, column="close")
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> dict:
    sma = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    bandwidth = (upper - lower) / sma * 100
    return {"upper": upper, "lower": lower, "middle": sma, "bandwidth": bandwidth}
