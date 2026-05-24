def score_mtf_alignment(results):
    biases = []
    for tf in ["1D", "4H", "1H"]:
        if tf in results:
            biases.append(results[tf]["bias_dir"])
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
    if not patterns:
        return 0
    high_quality = {"morning star", "evening star", "three white soldiers", "three black crows", "bullish engulfing", "bearish engulfing", "piercing line", "dark cloud cover"}
    medium_quality = {"hammer", "shooting star", "tweezer top", "tweezer bottom", "three inside up", "three inside down"}
    score = 0
    for pattern in patterns:
        name = pattern.lower()
        if name in high_quality:
            score += 15
        elif name in medium_quality:
            score += 8
        else:
            score += 3
    bullish_patterns = {"hammer", "bullish engulfing", "morning star", "three white soldiers", "piercing line", "tweezer bottom", "three inside up"}
    bearish_patterns = {"shooting star", "bearish engulfing", "evening star", "three black crows", "dark cloud cover", "tweezer top", "three inside down"}
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
        score = max(0, score - 10)
    return min(score, 20)

def score_location(fib_data, sr_data, bias_dir):
    score = 0
    if fib_data and fib_data.get("level_618"):
        score += 10
    if sr_data:
        supports = sr_data.get("swing_supports", [])
        resistances = sr_data.get("swing_resistances", [])
        if bias_dir == "LONG" and supports:
            score += 5
        elif bias_dir == "SHORT" and resistances:
            score += 5
        round_support = sr_data.get("round_support")
        round_resistance = sr_data.get("round_resistance")
        if bias_dir == "LONG" and round_support:
            score += 3
        elif bias_dir == "SHORT" and round_resistance:
            score += 3
    return min(score, 20)

def score_volume(vol_data):
    if not vol_data:
        return 5
    if vol_data.get("volume_surge"):
        return 15
    elif vol_data.get("volume_ratio", 1.0) > 1.2:
        return 10
    return 5

def score_session():
    from datetime import datetime
    hour = datetime.utcnow().hour
    if 8 <= hour <= 17:
        return 10
    elif 13 <= hour <= 21:
        return 8
    elif 7 <= hour < 8 or 17 < hour <= 22:
        return 5
    return 2

def score_regime(results):
    if "1D" not in results:
        return 3
    daily_rsi = results["1D"].get("rsi", 50)
    if daily_rsi > 60 or daily_rsi < 40:
        return 5
    elif 45 <= daily_rsi <= 55:
        return 2
    return 3

def calculate_confidence(results, patterns, fib_data, sr_data, vol_data):
    if not results:
        return 0, {}
    primary = results.get("15M", results.get("1H"))
    if not primary:
        return 0, {}
    bias_dir = primary.get("bias_dir", "NEUTRAL")
    if bias_dir == "NEUTRAL":
        return 0, {}
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
