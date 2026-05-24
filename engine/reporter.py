from datetime import datetime, timedelta, timezone
from storage.database import get_stats
from loguru import logger

def generate_daily_brief():
    """Generate the 7:00 UTC daily brief."""
    stats = get_stats()
    
    # Get last 24 hours of journal entries for pattern analysis
    from storage.database import get_recent_journal
    recent = get_recent_journal(hours=24)
    
    # Count patterns that worked
    pattern_wins = {}
    pattern_losses = {}
    for entry in recent:
        patterns = entry.get("patterns", "").split(",")
        outcome = entry.get("ghost_outcome", "")
        for p in patterns:
            p = p.strip().lower()
            if not p:
                continue
            if outcome in ("tp1_hit", "tp2_hit"):
                pattern_wins[p] = pattern_wins.get(p, 0) + 1
            elif outcome == "sl_hit":
                pattern_losses[p] = pattern_losses.get(p, 0) + 1
    
    best_patterns = sorted(pattern_wins.items(), key=lambda x: x[1], reverse=True)[:3]
    worst_patterns = sorted(pattern_losses.items(), key=lambda x: x[1], reverse=True)[:3]
    
    best_text = "\n".join([f"• {p.title()}: {c} wins" for p, c in best_patterns]) if best_patterns else "• No winning patterns yet"
    worst_text = "\n".join([f"• {p.title()}: {c} losses" for p, c in worst_patterns]) if worst_patterns else "• No losing patterns yet"
    
    # Ghost trade stats
    ghost_wins = sum(1 for e in recent if e.get("ghost_outcome") in ("tp1_hit", "tp2_hit"))
    ghost_losses = sum(1 for e in recent if e.get("ghost_outcome") == "sl_hit")
    ghost_total = ghost_wins + ghost_losses
    ghost_win_rate = (ghost_wins / ghost_total * 100) if ghost_total > 0 else 0
    
    message = (
        f"📅 <b>DAILY BRIEF</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📆 {datetime.now(timezone.utc).strftime('%d %B %Y')}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Live Trades:</b>\n"
        f"• Total: {stats['total']}\n"
        f"• Wins: {stats['wins']} | Losses: {stats['losses']}\n"
        f"• Win Rate: {stats['win_rate']}%\n"
        f"• PnL: {stats['total_pnl']} pips\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👻 <b>Ghost Trades (24h):</b>\n"
        f"• Total: {ghost_total}\n"
        f"• Wins: {ghost_wins} | Losses: {ghost_losses}\n"
        f"• Win Rate: {round(ghost_win_rate,1)}%\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Best Patterns:</b>\n{best_text}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>Struggling Patterns:</b>\n{worst_text}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🤖 <i>Next brief: tomorrow 7:00 UTC</i>"
    )
    return message


def generate_weekly_report():
    """Generate the Friday 20:00 UTC weekly report."""
    stats = get_stats()
    from storage.database import get_recent_journal
    recent = get_recent_journal(hours=168)  # 7 days
    
    # Session analysis
    session_wins = {}
    session_losses = {}
    for entry in recent:
        timestamp = entry.get("timestamp", "")
        if timestamp:
            try:
                hour = datetime.fromisoformat(timestamp).hour
                if 8 <= hour <= 17:
                    session = "London"
                elif 13 <= hour <= 21:
                    session = "NY"
                elif 7 <= hour < 8 or 17 < hour <= 22:
                    session = "Early/Late"
                else:
                    session = "Asian"
            except:
                session = "Unknown"
        else:
            session = "Unknown"
        
        outcome = entry.get("ghost_outcome", "")
        if outcome in ("tp1_hit", "tp2_hit"):
            session_wins[session] = session_wins.get(session, 0) + 1
        elif outcome == "sl_hit":
            session_losses[session] = session_losses.get(session, 0) + 1
    
    session_lines = []
    for session in ["London", "NY", "Asian", "Early/Late"]:
        w = session_wins.get(session, 0)
        l = session_losses.get(session, 0)
        total = w + l
        rate = (w / total * 100) if total > 0 else 0
        session_lines.append(f"• {session}: {round(rate)}% ({w}W/{l}L)")
    
    # Trade type analysis
    swing_wins = sum(1 for e in recent if e.get("trade_type") == "SWING" and e.get("ghost_outcome") in ("tp1_hit", "tp2_hit"))
    swing_losses = sum(1 for e in recent if e.get("trade_type") == "SWING" and e.get("ghost_outcome") == "sl_hit")
    scalp_wins = sum(1 for e in recent if e.get("trade_type") == "SCALP" and e.get("ghost_outcome") in ("tp1_hit", "tp2_hit"))
    scalp_losses = sum(1 for e in recent if e.get("trade_type") == "SCALP" and e.get("ghost_outcome") == "sl_hit")
    
    swing_total = swing_wins + swing_losses
    scalp_total = scalp_wins + scalp_losses
    swing_rate = (swing_wins / swing_total * 100) if swing_total > 0 else 0
    scalp_rate = (scalp_wins / scalp_total * 100) if scalp_total > 0 else 0
    
    ghost_wins = sum(1 for e in recent if e.get("ghost_outcome") in ("tp1_hit", "tp2_hit"))
    ghost_losses = sum(1 for e in recent if e.get("ghost_outcome") == "sl_hit")
    ghost_total = ghost_wins + ghost_losses
    
    message = (
        f"📊 <b>WEEKLY PERFORMANCE REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📆 Week ending {datetime.now(timezone.utc).strftime('%d %B %Y')}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🔢 <b>Live Trades:</b>\n"
        f"• Total: {stats['total']} | Wins: {stats['wins']} | Losses: {stats['losses']}\n"
        f"• Win Rate: {stats['win_rate']}%\n"
        f"• Net PnL: {stats['total_pnl']} pips\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👻 <b>Ghost Trades (7 days):</b>\n"
        f"• Total: {ghost_total} | Win Rate: {round(ghost_wins/ghost_total*100,1) if ghost_total>0 else 0}%\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🐋🐟 <b>By Trade Type:</b>\n"
        f"• SWING: {round(swing_rate)}% ({swing_wins}W/{swing_losses}L)\n"
        f"• SCALP: {round(scalp_rate)}% ({scalp_wins}W/{scalp_losses}L)\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🌍 <b>By Session:</b>\n" + "\n".join(session_lines) + "\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>What the bot learned this week:</b>\n"
        f"• {_generate_insight(recent)}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🤖 <i>Next report: Friday 20:00 UTC</i>"
    )
    return message


def _generate_insight(recent_entries):
    """Generate a human-readable insight from the week's data."""
    if len(recent_entries) < 10:
        return "Not enough data yet. Continuing to observe."
    
    # Find best session
    session_wins = {}
    session_total = {}
    for entry in recent_entries:
        timestamp = entry.get("timestamp", "")
        if timestamp:
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
        else:
            continue
        outcome = entry.get("ghost_outcome", "")
        if outcome in ("tp1_hit", "tp2_hit", "sl_hit"):
            session_total[session] = session_total.get(session, 0) + 1
            if outcome in ("tp1_hit", "tp2_hit"):
                session_wins[session] = session_wins.get(session, 0) + 1
    
    if session_total:
        best_session = max(session_total, key=lambda s: session_wins.get(s,0) / session_total.get(s,1))
        return f"{best_session} session produced the highest win rate. Prioritizing setups during this window."
    
    return "Collecting data to identify optimal trading conditions."
