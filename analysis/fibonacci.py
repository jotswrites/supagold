import pandas as pd
import numpy as np

def find_swing_points(df, lookback=5):
    highs, lows = df["high"].values, df["low"].values
    swing_highs, swing_lows = [], []
    for i in range(lookback, len(df) - lookback):
        if highs[i] == max(highs[i-lookback:i+lookback+1]):
            swing_highs.append({"index": i, "price": highs[i], "time": df.index[i]})
        if lows[i] == min(lows[i-lookback:i+lookback+1]):
            swing_lows.append({"index": i, "price": lows[i], "time": df.index[i]})
    return swing_highs, swing_lows

def calculate_fib_retracement(high, low):
    diff = high - low
    return {"0.0": low, "0.236": low+0.236*diff, "0.382": low+0.382*diff, "0.5": low+0.5*diff, "0.618": low+0.618*diff, "0.786": low+0.786*diff, "1.0": high}

def calculate_fib_extension(high, low):
    diff = high - low
    return {"1.272": low+1.272*diff, "1.618": low+1.618*diff, "2.618": low+2.618*diff}

def nearest_fib_levels(price, high, low):
    retrace = calculate_fib_retracement(high, low)
    extend = calculate_fib_extension(high, low)
    all_levels = {**retrace, **extend}
    nearest_support, nearest_resistance = None, None
    for name, level in sorted(all_levels.items(), key=lambda x: x[1]):
        if level < price:
            nearest_support = (name, level)
        if level > price and nearest_resistance is None:
            nearest_resistance = (name, level)
    return nearest_support, nearest_resistance

def analyze_fibonacci(df):
    if len(df) < 20:
        return None
    swing_highs, swing_lows = find_swing_points(df)
    if len(swing_highs) < 1 or len(swing_lows) < 1:
        return None
    last_high = swing_highs[-1]["price"]
    last_low = swing_lows[-1]["price"]
    price = df["close"].iloc[-1]
    if last_high > last_low:
        high, low = last_high, last_low
    else:
        high, low = last_low, last_high
    support, resistance = nearest_fib_levels(price, high, low)
    levels = calculate_fib_retracement(high, low)
    return {"swing_high": last_high, "swing_low": last_low, "nearest_support": support, "nearest_resistance": resistance, "level_618": levels.get("0.618"), "level_382": levels.get("0.382")}
