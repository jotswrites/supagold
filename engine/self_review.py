"""
Self-Review Engine — Analyzes the journal weekly and proposes
parameter adjustments with strict guardrails.
"""
from datetime import datetime, timedelta, timezone
from storage.database import get_recent_journal
from loguru import logger

# Guardrails
MIN_SAMPLE_SIZE = 50        # Minimum trades before any adjustment
MAX_ADJUSTMENT = 2           # Maximum change per parameter per week
SAFE_BOUNDS = {
    "confidence_threshold": (65, 85),
    "session_weight_asian": (0, 5),
    "session_weight_london": (8, 10),
    "session_weight_ny": (6, 10),
    "pattern_weight": (15, 25),
    "location_weight": (15, 25),
    "volume_weight": (10, 20),
    "mtf_weight": (25, 35),
}


def analyze_journal():
    """Analyze the journal and return insights + proposed adjustments."""
    recent = get_recent_journal(hours=168)  # 7 days
    
    if len(recent) < MIN_SAMPLE_SIZE:
        return {
            "ready": False,
            "message": f"Only {len(recent)} trades logged. Need {MIN_SAMPLE_SIZE} before adjustments.",
            "adjustments": {}
        }
    
    # --- Session analysis ---
    session_stats = {"London": {"wins": 0, "total": 0}, "NY": {"wins": 0, "total": 0}, "Asian": {"wins": 0, "total": 0}}
    for entry in recent:
        timestamp = entry.get("timestamp", "")
        try:
            hour = datetime.fromisoformat(timestamp).hour
            if 8 <= hour <= 17:
                session = "London"
            elif 13 <= hour <= 21:
                session = "NY"
            else:
                session = "Asian"
        except:
            continue
        
        outcome = entry.get("ghost_outcome", "")
        if outcome in ("tp1_hit", "tp2_hit", "sl_hit"):
            session_stats[session]["total"] += 1
            if outcome in ("tp1_hit", "tp2_hit"):
                session_stats[session]["wins"] += 1
    
    # --- Pattern analysis ---
    pattern_stats = {}
    for entry in recent:
        patterns = entry.get("patterns", "").split(",")
        outcome = entry.get("ghost_outcome", "")
        for p in patterns:
            p = p.strip().lower()
            if not p:
                continue
            if p not in pattern_stats:
                pattern_stats[p] = {"wins": 0, "total": 0}
            if outcome in ("tp1_hit", "tp2_hit", "sl_hit"):
                pattern_stats[p]["total"] += 1
                if outcome in ("tp1_hit", "tp2_hit"):
                    pattern_stats[p]["wins"] += 1
    
    # --- Confidence tier analysis ---
    confidence_tiers = {"low": {"wins": 0, "total": 0}, "mid": {"wins": 0, "total": 0}, "high": {"wins": 0, "total": 0}}
    for entry in recent:
        conf = entry.get("confidence", 0)
        outcome = entry.get("ghost_outcome", "")
        if conf < 60:
            tier = "low"
        elif conf < 75:
            tier = "mid"
        else:
            tier = "high"
        if outcome in ("tp1_hit", "tp2_hit", "sl_hit"):
            confidence_tiers[tier]["total"] += 1
            if outcome in ("tp1_hit", "tp2_hit"):
                confidence_tiers[tier]["wins"] += 1
    
    # --- Generate adjustments ---
    adjustments = {}
    insights = []
    
    # Session adjustments
    for session, stats in session_stats.items():
        if stats["total"] >= 15:  # Minimum trades per session
            win_rate = stats["wins"] / stats["total"] * 100
            key = f"session_weight_{session.lower()}"
            current = SAFE_BOUNDS.get(key, (5, 10))
            
            if win_rate < 40 and current[0] > 0:
                adjustments[key] = max(current[0], current[1] - MAX_ADJUSTMENT)
                insights.append(f"{session} session win rate {round(win_rate)}% — reducing weight to {adjustments[key]}")
            elif win_rate > 65 and current[1] < 10:
                adjustments[key] = min(current[1], current[1] + MAX_ADJUSTMENT)
                insights.append(f"{session} session win rate {round(win_rate)}% — increasing weight to {adjustments[key]}")
    
    # Confidence threshold adjustment
    for tier, stats in confidence_tiers.items():
        if stats["total"] >= 20:
            win_rate = stats["wins"] / stats["total"] * 100
            if tier == "low" and win_rate < 35:
                insights.append(f"Low confidence trades ({tier}) win rate only {round(win_rate)}%. Threshold should stay high.")
            elif tier == "mid" and win_rate > 60:
                adjustments["confidence_threshold"] = max(SAFE_BOUNDS["confidence_threshold"][0],
                                                          SAFE_BOUNDS["confidence_threshold"][1] - MAX_ADJUSTMENT)
                insights.append(f"Mid-confidence trades performing well ({round(win_rate)}%) — lowering threshold to {adjustments['confidence_threshold']}")
    
    # Best patterns insight
    best_patterns = sorted(pattern_stats.items(), key=lambda x: x[1]["wins"] / max(x[1]["total"], 1), reverse=True)
    if best_patterns:
        top = best_patterns[0]
        if top[1]["total"] >= 10:
            insights.append(f"Best pattern: {top[0].title()} — {round(top[1]['wins']/top[1]['total']*100)}% win rate over {top[1]['total']} trades")
    
    return {
        "ready": True,
        "message": "\n".join([f"• {i}" for i in insights]) if insights else "No significant patterns detected yet.",
        "adjustments": adjustments,
        "session_stats": {s: {"win_rate": round(stats["wins"]/max(stats["total"],1)*100), "total": stats["total"]}
                         for s, stats in session_stats.items()},
        "best_pattern": best_patterns[0][0].title() if best_patterns and best_patterns[0][1]["total"] >= 5 else None,
    }


def apply_adjustments(adjustments):
    """Apply approved adjustments to the quality gate weights."""
    if not adjustments:
        return False
    
    # Read current weights from settings
    import sys
    sys.path.insert(0, '/home/runner/work/supagold/supagold')
    from bot_config.settings import STRATEGY_WEIGHTS
    
    changed = False
    for key, value in adjustments.items():
        if key in STRATEGY_WEIGHTS:
            old = STRATEGY_WEIGHTS[key]
            STRATEGY_WEIGHTS[key] = value
            logger.info(f"Adjusted {key}: {old} → {value}")
            changed = True
    
    return changed
