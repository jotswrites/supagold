import pandas as pd
from storage.database import (
    open_ghost_position, close_ghost_position, get_ghost_position
)

def check_tp_sl_intra_candle(one_min_data, entry_price, tp, sl, direction):
    if direction == "LONG":
        for _, row in one_min_data.iterrows():
            if row["low"] <= sl:
                return "sl", sl
            if row["high"] >= tp:
                return "tp", tp
    else:
        for _, row in one_min_data.iterrows():
            if row["high"] >= sl:
                return "sl", sl
            if row["low"] <= tp:
                return "tp", tp
    return None, None

def simulate_ghost_trade(symbol, one_min_candles, direction, entry_price, sl, tp1, tp2, confidence, trade_type):
    slippage = 3.0 if symbol == "XAU/USD" else 1.0
    fill_price = entry_price + slippage if direction == "LONG" else entry_price - slippage

    existing = get_ghost_position(symbol)
    if existing and existing["status"] == "open":
        # Already tracking — check if this cycle closes it
        pass

    open_ghost_position(symbol, direction, fill_price, sl, tp1, tp2, confidence, trade_type)

    sorted_candles = one_min_candles.sort_values("datetime")

    for target in [tp1, tp2]:
        hit, price = check_tp_sl_intra_candle(sorted_candles, fill_price, target, sl, direction)
        if hit == "tp":
            pnl = abs(target - fill_price)
            close_ghost_position(symbol, f"tp{1 if target == tp1 else 2}_hit", pnl)
            return f"tp{1 if target == tp1 else 2}_hit", pnl

    hit, price = check_tp_sl_intra_candle(sorted_candles, fill_price, sl, sl, direction)
    if hit == "sl":
        pnl = abs(fill_price - sl)
        close_ghost_position(symbol, "sl_hit", -pnl)
        return "sl_hit", -pnl

    return "still_open", 0
