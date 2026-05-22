"""
Quality Gate — Scores a trade setup 0-100.
Only setups scoring ≥ 75 become signals.
"""

def score_mtf_alignment(results):
    """Score multi-timeframe alignment (0-30)."""
    biases = []
    for tf in ["1D", "4H", "1H"]:
        if tf in results:
            biases.append(results[tf]["bias_dir"])
    
    if not biases:
        return 0
    
    # Count how many agree with the primary (15M or 1H)
    primary = results.get("15M", results.get("1H", {}))
    primary_bias = primary.get("bias_dir", "NEUTRAL")
    
    if primary_bias == "NEUTRAL":
        return 0
    
    agreement = sum(1 for b in biases if b == primary_bias)
    
    if agreement >= 3:
        return 30
    elif agreement >= 2:
        return 20
    elif agreement >= 1:
        return 10
    return 0


def score_pattern_quality(patterns, bias_dir):
    """Score candlestick pattern quality (0-20)."""
    if not patterns:
        return 0
    
    high_quality = {
        "morning star", "evening star", "three white soldiers",
        "three black crows", "bullish engulfing", "bearish engulfing",
        "piercing line", "dark cloud cover"
    }
    medium_quality = {
        "hammer", "shooting star", "tweezer top", "tweezer bottom",
        "three inside up", "three inside down"
    }
    
    score = 0
    for pattern in patterns:
        name = pattern.lower()
        if name in high_quality:
            score += 15
        elif name in medium_quality:
            score += 8
        else:
            score += 3
    
    # Check if pattern direction matches bias
    bullish_patterns = {"hammer", "bullish engulfing", "morning star", "three white soldiers",
                        "piercing line", "tweezer bottom", "three inside up"}
    bearish_patterns = {"shooting star", "bearish engulfing", "evening star", "three black crows",
                        "dark cloud cover", "tweezer top", "three inside down"}
    
    pattern_direction_match = False
    for pattern in patterns:
        name = pattern.lower()
        if bias_dir == "LONG" and name in bullish_patterns:
            pattern_direction_match = True
            break
        if bias_dir == "SHORT" and name in bearish_patterns:
            pattern_direction_match = True
            break
    
    if not pattern_direction_match and bias_dir != "NEUTRAL":
        score = max(0, score - 10)  # Penalty if pattern contradicts bias
    
    return min(score, 20)


def score_location(fib_data, sr_data, bias_dir):
    """Score how good the entry location is (0-20)."""
    score = 0
    
    if fib_data and fib_data.get("level_618"):
        # Check if price is near 61.8% retracement
        level_618 = fib_data["level_618"]
        swing_high = fib_data["swing_high"]
        swing_low = fib_data["swing_low"]
        if swing_high and swing_low and swing_high > swing_low:
            range_size = swing_high - swing_low
            if range_size > 0:
                distance_pct = abs(level_618 - swing_low) / range_size  # approximate
                if distance_pct < 0.05:  # within 5% of range
                    score += 10
    
    if sr_data:
        supports = sr_data.get("swing_supports", [])
        resistances = sr_data.get("swing_resistances", [])
        
        if bias_dir == "LONG" and supports:
            score += 5  # Buying near support
        elif bias_dir == "SHORT" and resistances:
            score += 5  # Selling near resistance
        
        # Check round number proximity
        round_support = sr_data.get("round_support")
        round_resistance = sr_data.get("round_resistance")
        if bias_dir == "LONG" and round_support:
            score += 3
        elif bias_dir == "SHORT" and round_resistance:
            score += 3
    
    return min(score, 20)


def score_volume(vol_data):
    """Score volume confirmation (0-15)."""
    if not vol_data:
        return 5  # neutral if no data
    
    if vol_data.get("volume_surge"):
        return 15
    elif vol_data.get("volume_ratio", 1.0) > 1.2:
        return 10
    else:
        return 5


def score_session():
    """Score based on trading session (0-10)."""
    from datetime import datetime
    hour = datetime.utcnow().hour
    
    # London: 08-17, NY: 13-21, Overlap: 13-17
    if 8 <= hour <= 17:
        return 10  # London or overlap
    elif 13 <= hour <= 21:
        return 8   # NY
    elif 7 <= hour < 8 or 17 < hour <= 22:
        return 5   # Early London or late NY
    else:
        return 2   # Asian — reduced weight


def score_regime(results):
    """Score regime fit (0-5)."""
    if "1D" not in results:
        return 3
    
    daily_atr = results["1D"].get("atr", 0)
    daily_rsi = results["1D"].get("rsi", 50)
    
    # Strong trend = higher score for swing potential
    if daily_rsi > 60 or daily_rsi < 40:
        return 5  # Trending
    elif 45 <= daily_rsi <= 55:
        return 2  # Ranging — lower conviction
    return 3


def calculate_confidence(results, patterns, fib_data, sr_data, vol_data):
    """Calculate total confidence score (0-100)."""
    if not results:
        return 0
    
    primary = results.get("15M", results.get("1H"))
    if not primary:
        return 0
    
    bias_dir = primary.get("bias_dir", "NEUTRAL")
    if bias_dir == "NEUTRAL":
        return 0
    
    scores = {
        "mtf_alignment": score_mtf_alignment(results),
        "pattern_quality": score_pattern_quality(patterns, bias_dir),
        "location": score_location(fib_data, sr_data, bias_dir),
        "volume": score_volume(vol_data),
        "session": score_session(),
        "regime": score_regime(results),
    }
    
    total = sum(scores.values())
    return min(total, 100), scores
