import pandas as pd
import numpy as np

def calculate_ema(df, period, column="close"):
    return df[column].ewm(span=period, adjust=False).mean()

def calculate_atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"].shift(1)
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(span=period, adjust=False).mean()

def calculate_rsi(df, period=14, column="close"):
    delta = df[column].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
