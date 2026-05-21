import pandas as pd
import numpy as np

def volume_surge(df, period=20, multiplier=1.5):
    if "volume" not in df.columns or df["volume"].sum() == 0:
        return False, 1.0
    avg_vol = df["volume"].rolling(period).mean().iloc[-1]
    current_vol = df["volume"].iloc[-1]
    if avg_vol > 0:
        ratio = current_vol / avg_vol
        return ratio > multiplier, ratio
    return False, 1.0

def analyze_volume(df):
    surge, ratio = volume_surge(df)
    return {
        "volume_surge": surge,
        "volume_ratio": round(ratio, 2),
        "description": "High volume" if surge else "Normal volume"
    }
