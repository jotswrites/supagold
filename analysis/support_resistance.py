import pandas as pd
import numpy as np

def find_round_numbers(price, interval=50):
    lower = np.floor(price / interval) * interval
    upper = lower + interval
    return lower, upper

def daily_levels(df):
    if len(df) < 2:
        return None
    prev_day = df.iloc[-2]
    return {"prev_high": prev_day["high"], "prev_low": prev_day["low"], "prev_close": prev_day["close"]}

def pivot_points(df):
    if len(df) < 2:
        return None
    prev = df.iloc[-2]
    h, l, c = prev["high"], prev["low"], prev["close"]
    pp = (h + l + c) / 3
    r1, s1 = 2*pp - l, 2*pp - h
    r2, s2 = pp + (h-l), pp - (h-l)
    return {"pp": pp, "r1": r1, "s1": s1, "r2": r2, "s2": s2}

def find_sr_levels(df, min_touches=2, tolerance_pct=0.1):
    highs, lows = df["high"].values, df["low"].values
    levels = []
    for i in range(2, len(df)-2):
        if highs[i] == max(highs[i-2:i+3]):
            levels.append(highs[i])
        if lows[i] == min(lows[i-2:i+3]):
            levels.append(lows[i])
    if not levels:
        return [], []
    clustered = []
    levels = sorted(levels)
    current_cluster = [levels[0]]
    for lvl in levels[1:]:
        if abs(lvl - current_cluster[-1]) / current_cluster[-1] * 100 <= tolerance_pct:
            current_cluster.append(lvl)
        else:
            if len(current_cluster) >= min_touches:
                clustered.append(np.mean(current_cluster))
            current_cluster = [lvl]
    if len(current_cluster) >= min_touches:
        clustered.append(np.mean(current_cluster))
    price = df["close"].iloc[-1]
    supports = [l for l in clustered if l < price]
    resistances = [l for l in clustered if l > price]
    return sorted(supports, reverse=True)[:3], sorted(resistances)[:3]

def analyze_sr(df):
    price = df["close"].iloc[-1]
    round_low, round_high = find_round_numbers(price, 50)
    supports, resistances = find_sr_levels(df)
    daily = daily_levels(df)
    pivots = pivot_points(df)
    return {
        "round_support": round_low, "round_resistance": round_high,
        "swing_supports": supports, "swing_resistances": resistances,
        "daily_high": daily["prev_high"] if daily else None,
        "daily_low": daily["prev_low"] if daily else None,
        "pivot_r1": pivots["r1"] if pivots else None,
        "pivot_s1": pivots["s1"] if pivots else None
    }
