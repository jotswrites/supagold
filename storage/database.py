import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "signals.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Signals table (for completed/pending signals)
    c.execute('''CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        timestamp TEXT,
        direction TEXT,
        entry REAL,
        sl REAL,
        tp1 REAL,
        tp2 REAL,
        confidence INTEGER,
        trade_type TEXT,
        outcome TEXT,
        pnl REAL,
        closed_at TEXT
    )''')
    
    # Active positions table (tracks current open trade per symbol)
    c.execute('''CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE,
        direction TEXT,
        entry REAL,
        sl REAL,
        tp1 REAL,
        tp2 REAL,
        confidence INTEGER,
        trade_type TEXT,
        opened_at TEXT,
        updated_at TEXT,
        status TEXT DEFAULT 'active'
    )''')
    
    conn.commit()
    conn.close()

def log_signal(symbol, direction, entry, sl, tp1, tp2, confidence, trade_type="SCALP"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO signals (symbol, timestamp, direction, entry, sl, tp1, tp2, confidence, trade_type)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (symbol, datetime.utcnow().isoformat(), direction, entry, sl, tp1, tp2, confidence, trade_type))
    signal_id = c.lastrowid
    conn.commit()
    conn.close()
    return signal_id

def update_outcome(signal_id, outcome, pnl=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE signals SET outcome=?, pnl=?, closed_at=? WHERE id=?",
              (outcome, pnl, datetime.utcnow().isoformat(), signal_id))
    conn.commit()
    conn.close()

def open_position(symbol, direction, entry, sl, tp1, tp2, confidence, trade_type):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    # Remove any existing position for this symbol
    c.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
    c.execute('''INSERT INTO positions (symbol, direction, entry, sl, tp1, tp2, confidence, trade_type, opened_at, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (symbol, direction, entry, sl, tp1, tp2, confidence, trade_type, now, now))
    conn.commit()
    conn.close()

def get_position(symbol):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM positions WHERE symbol=? AND status='active'", (symbol,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "symbol": row[1], "direction": row[2], "entry": row[3],
            "sl": row[4], "tp1": row[5], "tp2": row[6], "confidence": row[7],
            "trade_type": row[8], "opened_at": row[9], "updated_at": row[10], "status": row[11]
        }
    return None

def close_position(symbol, outcome, pnl=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE positions SET status='closed', updated_at=? WHERE symbol=? AND status='active'",
              (datetime.utcnow().isoformat(), symbol))
    conn.commit()
    conn.close()

def update_position_sl(symbol, new_sl):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE positions SET sl=?, updated_at=? WHERE symbol=? AND status='active'",
              (new_sl, datetime.utcnow().isoformat(), symbol))
    conn.commit()
    conn.close()

def get_stats(symbol=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT direction, outcome, pnl FROM signals"
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
    
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2)
    }
