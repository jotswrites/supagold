import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "signals.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        timestamp TEXT,
        direction TEXT,
        entry REAL,
        sl REAL,
        tp1 REAL,
        tp2 REAL,
        confidence REAL,
        outcome TEXT,
        pnl REAL,
        closed_at TEXT
    )''')
    conn.commit()
    conn.close()

def log_signal(symbol, direction, entry, sl, tp1, tp2, confidence=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO signals (symbol, timestamp, direction, entry, sl, tp1, tp2, confidence)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (symbol, datetime.utcnow().isoformat(), direction, entry, sl, tp1, tp2, confidence))
    conn.commit()
    conn.close()

def update_outcome(signal_id, outcome, pnl=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE signals SET outcome=?, pnl=?, closed_at=? WHERE id=?",
              (outcome, pnl, datetime.utcnow().isoformat(), signal_id))
    conn.commit()
    conn.close()

def get_stats(symbol=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT direction, outcome, pnl, entry, sl, tp1, tp2 FROM signals"
    params = ()
    if symbol:
        query += " WHERE symbol = ?"
        params = (symbol,)
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    total = len(rows)
    wins = sum(1 for r in rows if r[1] in ('tp1', 'tp2'))
    losses = sum(1 for r in rows if r[1] == 'sl')
    pending = total - wins - losses
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    total_pnl = sum(r[2] for r in rows if r[2])
    avg_rr = (sum((r[5]-r[3])/(r[3]-r[4]) for r in rows if r[3] and r[4] and r[5]) / total) if total > 0 else 0

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_rr": round(avg_rr, 2)
    }
