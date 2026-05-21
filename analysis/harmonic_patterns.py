import pandas as pd
import numpy as np

def find_zigzag(df, min_swing=5):
    highs = df['high'].values
    lows = df['low'].values
    swings = []
    
    for i in range(min_swing, len(df) - min_swing):
        if highs[i] == max(highs[i-min_swing:i+min_swing+1]):
            swings.append(('H', i, highs[i]))
        if lows[i] == min(lows[i-min_swing:i+min_swing+1]):
            swings.append(('L', i, lows[i]))
    
    return sorted(swings, key=lambda x: x[1])

def is_ratio(val, target, tolerance=0.08):
    return abs(val - target) <= tolerance

def detect_gartley(swings):
    patterns = []
    for i in range(len(swings) - 4):
        x, a, b, c, d = swings[i:i+5]
        if x[0] == 'H' and a[0] == 'L' and b[0] == 'H' and c[0] == 'L' and d[0] == 'H':
            xa = abs(x[2] - a[2])
            ab = abs(a[2] - b[2])
            cd = abs(c[2] - d[2])
            if xa > 0 and is_ratio(ab/xa, 0.618) and is_ratio(cd/xa, 0.786):
                patterns.append(('Gartley', 'SELL', d[2]))
        elif x[0] == 'L' and a[0] == 'H' and b[0] == 'L' and c[0] == 'H' and d[0] == 'L':
            xa = abs(x[2] - a[2])
            ab = abs(a[2] - b[2])
            cd = abs(c[2] - d[2])
            if xa > 0 and is_ratio(ab/xa, 0.618) and is_ratio(cd/xa, 0.786):
                patterns.append(('Gartley', 'BUY', d[2]))
    return patterns

def detect_bat(swings):
    patterns = []
    for i in range(len(swings) - 4):
        x, a, b, c, d = swings[i:i+5]
        if x[0] == 'H' and a[0] == 'L' and b[0] == 'H' and c[0] == 'L' and d[0] == 'H':
            xa = abs(x[2] - a[2])
            ab = abs(a[2] - b[2])
            cd = abs(c[2] - d[2])
            if xa > 0 and is_ratio(ab/xa, 0.5, 0.12) and is_ratio(cd/xa, 0.886):
                patterns.append(('Bat', 'SELL', d[2]))
        elif x[0] == 'L' and a[0] == 'H' and b[0] == 'L' and c[0] == 'H' and d[0] == 'L':
            xa = abs(x[2] - a[2])
            ab = abs(a[2] - b[2])
            cd = abs(c[2] - d[2])
            if xa > 0 and is_ratio(ab/xa, 0.5, 0.12) and is_ratio(cd/xa, 0.886):
                patterns.append(('Bat', 'BUY', d[2]))
    return patterns

def detect_crab(swings):
    patterns = []
    for i in range(len(swings) - 4):
        x, a, b, c, d = swings[i:i+5]
        if x[0] == 'H' and a[0] == 'L' and b[0] == 'H' and c[0] == 'L' and d[0] == 'H':
            xa = abs(x[2] - a[2])
            ab = abs(a[2] - b[2])
            cd = abs(c[2] - d[2])
            if xa > 0 and is_ratio(ab/xa, 0.618, 0.15) and is_ratio(cd/xa, 1.618):
                patterns.append(('Crab', 'SELL', d[2]))
        elif x[0] == 'L' and a[0] == 'H' and b[0] == 'L' and c[0] == 'H' and d[0] == 'L':
            xa = abs(x[2] - a[2])
            ab = abs(a[2] - b[2])
            cd = abs(c[2] - d[2])
            if xa > 0 and is_ratio(ab/xa, 0.618, 0.15) and is_ratio(cd/xa, 1.618):
                patterns.append(('Crab', 'BUY', d[2]))
    return patterns

def detect_abcd(swings):
    patterns = []
    for i in range(len(swings) - 3):
        a, b, c, d = swings[i:i+4]
        if a[0] == b[0] or c[0] == d[0]:
            continue
        ab = abs(a[2] - b[2])
        cd = abs(c[2] - d[2])
        if ab > 0 and is_ratio(cd/ab, 1.0, 0.1):
            if d[0] == 'H':
                patterns.append(('AB=CD', 'SELL', d[2]))
            else:
                patterns.append(('AB=CD', 'BUY', d[2]))
    return patterns

def analyze_harmonic(df):
    if len(df) < 20:
        return []
    swings = find_zigzag(df)
    patterns = []
    patterns.extend(detect_gartley(swings))
    patterns.extend(detect_bat(swings))
    patterns.extend(detect_crab(swings))
    patterns.extend(detect_abcd(swings))
    return patterns
