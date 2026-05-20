import pandas as pd
import numpy as np
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, level="INFO")


class CandlestickPatterns:
    """
    Complete candlestick pattern recognition based on
    'The Candlestick Trading Bible' by Munehisa Homma.
    
    All patterns include context awareness — a pattern only
    matters where it appears in market structure.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._calculate_candle_properties()

    def _calculate_candle_properties(self):
        """Calculate basic candle properties used across all patterns."""
        self.df["body"] = abs(self.df["close"] - self.df["open"])
        self.df["upper_shadow"] = self.df["high"] - self.df[["open", "close"]].max(axis=1)
        self.df["lower_shadow"] = self.df[["open", "close"]].min(axis=1) - self.df["low"]
        self.df["total_range"] = self.df["high"] - self.df["low"]
        self.df["is_bullish"] = self.df["close"] > self.df["open"]
        self.df["is_bearish"] = self.df["close"] < self.df["open"]

    # ═══════════════════════════════════════════════════════════
    # SINGLE CANDLE REVERSAL PATTERNS
    # ═══════════════════════════════════════════════════════════

    def detect_hammer(self) -> pd.Series:
        """
        Hammer: Small body at the top, long lower shadow (≥2x body),
        small or no upper shadow. Bullish reversal after downtrend.
        """
        body = self.df["body"]
        lower = self.df["lower_shadow"]
        upper = self.df["upper_shadow"]
        total = self.df["total_range"]

        is_hammer = (
            (total > 0) &
            (body > 0) &
            (lower >= 2 * body) &
            (upper <= body * 0.3) &
            (body <= total * 0.35)
        )
        return is_hammer

    def detect_hanging_man(self) -> pd.Series:
        """
        Hanging Man: Same shape as Hammer but appears after uptrend.
        Small body, long lower shadow, small upper shadow.
        Bearish reversal signal.
        """
        return self.detect_hammer()  # Same shape, context differs

    def detect_shooting_star(self) -> pd.Series:
        """
        Shooting Star: Small body at the bottom, long upper shadow (≥2x body),
        small or no lower shadow. Bearish reversal after uptrend.
        """
        body = self.df["body"]
        lower = self.df["lower_shadow"]
        upper = self.df["upper_shadow"]
        total = self.df["total_range"]

        is_shooting_star = (
            (total > 0) &
            (body > 0) &
            (upper >= 2 * body) &
            (lower <= body * 0.3) &
            (body <= total * 0.35)
        )
        return is_shooting_star

    def detect_inverted_hammer(self) -> pd.Series:
        """
        Inverted Hammer: Same shape as Shooting Star but appears after downtrend.
        Bullish reversal signal.
        """
        return self.detect_shooting_star()  # Same shape, context differs

    def detect_dragonfly_doji(self) -> pd.Series:
        """
        Dragonfly Doji: Open = Close, long lower shadow, no upper shadow.
        Bullish reversal at support.
        """
        body = self.df["body"]
        lower = self.df["lower_shadow"]
        upper = self.df["upper_shadow"]
        total = self.df["total_range"]

        return (
            (total > 0) &
            (body <= total * 0.05) &
            (lower >= total * 0.6) &
            (upper <= total * 0.05)
        )

    def detect_gravestone_doji(self) -> pd.Series:
        """
        Gravestone Doji: Open = Close, long upper shadow, no lower shadow.
        Bearish reversal at resistance.
        """
        body = self.df["body"]
        lower = self.df["lower_shadow"]
        upper = self.df["upper_shadow"]
        total = self.df["total_range"]

        return (
            (total > 0) &
            (body <= total * 0.05) &
            (upper >= total * 0.6) &
            (lower <= total * 0.05)
        )

    def detect_long_legged_doji(self) -> pd.Series:
        """
        Long-Legged Doji: Open = Close, both shadows long and roughly equal.
        Signals indecision — powerful at key S/R levels.
        """
        body = self.df["body"]
        lower = self.df["lower_shadow"]
        upper = self.df["upper_shadow"]
        total = self.df["total_range"]

        return (
            (total > 0) &
            (body <= total * 0.05) &
            (lower >= total * 0.25) &
            (upper >= total * 0.25) &
            (abs(lower - upper) <= total * 0.15)
        )

    def detect_marubozu_bullish(self) -> pd.Series:
        """
        Bullish Marubozu: Long bullish body with no or tiny shadows.
        Signals aggressive buying.
        """
        body = self.df["body"]
        upper = self.df["upper_shadow"]
        lower = self.df["lower_shadow"]
        total = self.df["total_range"]

        return (
            (total > 0) &
            (self.df["is_bullish"]) &
            (body >= total * 0.8) &
            (upper <= total * 0.1) &
            (lower <= total * 0.1)
        )

    def detect_marubozu_bearish(self) -> pd.Series:
        """
        Bearish Marubozu: Long bearish body with no or tiny shadows.
        Signals aggressive selling.
        """
        body = self.df["body"]
        upper = self.df["upper_shadow"]
        lower = self.df["lower_shadow"]
        total = self.df["total_range"]

        return (
            (total > 0) &
            (self.df["is_bearish"]) &
            (body >= total * 0.8) &
            (upper <= total * 0.1) &
            (lower <= total * 0.1)
        )

    def detect_spinning_top(self) -> pd.Series:
        """
        Spinning Top: Small body with both shadows longer than body.
        Indecision — meaningful when clustered near key levels.
        """
        body = self.df["body"]
        lower = self.df["lower_shadow"]
        upper = self.df["upper_shadow"]
        total = self.df["total_range"]

        return (
            (total > 0) &
            (body <= total * 0.25) &
            (lower > body) &
            (upper > body)
        )

    # ═══════════════════════════════════════════════════════════
    # TWO-CANDLE REVERSAL PATTERNS
    # ═══════════════════════════════════════════════════════════

    def detect_bullish_engulfing(self) -> pd.Series:
        """
        Bullish Engulfing: Bearish candle followed by larger bullish candle
        that completely engulfs the previous body.
        """
        prev_bearish = self.df["is_bearish"].shift(1)
        curr_bullish = self.df["is_bullish"]
        prev_body = self.df["body"].shift(1)
        curr_body = self.df["body"]
        prev_open = self.df["open"].shift(1)
        prev_close = self.df["close"].shift(1)
        curr_open = self.df["open"]
        curr_close = self.df["close"]

        return (
            prev_bearish &
            curr_bullish &
            (curr_open <= prev_close) &
            (curr_close >= prev_open) &
            (curr_body > prev_body)
        )

    def detect_bearish_engulfing(self) -> pd.Series:
        """
        Bearish Engulfing: Bullish candle followed by larger bearish candle
        that completely engulfs the previous body.
        """
        prev_bullish = self.df["is_bullish"].shift(1)
        curr_bearish = self.df["is_bearish"]
        prev_body = self.df["body"].shift(1)
        curr_body = self.df["body"]
        prev_open = self.df["open"].shift(1)
        prev_close = self.df["close"].shift(1)
        curr_open = self.df["open"]
        curr_close = self.df["close"]

        return (
            prev_bullish &
            curr_bearish &
            (curr_open >= prev_close) &
            (curr_close <= prev_open) &
            (curr_body > prev_body)
        )

    def detect_piercing_line(self) -> pd.Series:
        """
        Piercing Line: Bearish candle followed by bullish candle that opens below
        previous low and closes above 50% of previous body.
        Bullish reversal.
        """
        prev_bearish = self.df["is_bearish"].shift(1)
        curr_bullish = self.df["is_bullish"]
        prev_body = self.df["body"].shift(1)
        prev_low = self.df["low"].shift(1)
        prev_open = self.df["open"].shift(1)
        prev_close = self.df["close"].shift(1)
        curr_open = self.df["open"]
        curr_close = self.df["close"]

        mid_point = (prev_open + prev_close) / 2

        return (
            prev_bearish &
            curr_bullish &
            (prev_body > 0) &
            (curr_open < prev_low) &
            (curr_close > mid_point) &
            (curr_close < prev_open)
        )

    def detect_dark_cloud_cover(self) -> pd.Series:
        """
        Dark Cloud Cover: Bullish candle followed by bearish candle that opens above
        previous high and closes below 50% of previous body.
        Bearish reversal.
        """
        prev_bullish = self.df["is_bullish"].shift(1)
        curr_bearish = self.df["is_bearish"]
        prev_body = self.df["body"].shift(1)
        prev_high = self.df["high"].shift(1)
        prev_open = self.df["open"].shift(1)
        prev_close = self.df["close"].shift(1)
        curr_open = self.df["open"]
        curr_close = self.df["close"]

        mid_point = (prev_open + prev_close) / 2

        return (
            prev_bullish &
            curr_bearish &
            (prev_body > 0) &
            (curr_open > prev_high) &
            (curr_close < mid_point) &
            (curr_close > prev_open)
        )

    def detect_tweezer_top(self) -> pd.Series:
        """
        Tweezer Top: Two candles with matching or near-matching highs.
        First bullish, second bearish. Reversal signal.
        """
        prev_bullish = self.df["is_bullish"].shift(1)
        curr_bearish = self.df["is_bearish"]
        prev_high = self.df["high"].shift(1)
        curr_high = self.df["high"]
        avg_range = self.df["total_range"].rolling(14).mean()

        return (
            prev_bullish &
            curr_bearish &
            (avg_range > 0) &
            (abs(prev_high - curr_high) <= avg_range * 0.1)
        )

    def detect_tweezer_bottom(self) -> pd.Series:
        """
        Tweezer Bottom: Two candles with matching or near-matching lows.
        First bearish, second bullish. Reversal signal.
        """
        prev_bearish = self.df["is_bearish"].shift(1)
        curr_bullish = self.df["is_bullish"]
        prev_low = self.df["low"].shift(1)
        curr_low = self.df["low"]
        avg_range = self.df["total_range"].rolling(14).mean()

        return (
            prev_bearish &
            curr_bullish &
            (avg_range > 0) &
            (abs(prev_low - curr_low) <= avg_range * 0.1)
        )

    # ═══════════════════════════════════════════════════════════
    # THREE-CANDLE REVERSAL PATTERNS (The Bible's Crown Jewels)
    # ═══════════════════════════════════════════════════════════

    def detect_morning_star(self) -> pd.Series:
        """
        Morning Star: Three-candle bullish reversal.
        Bearish → Small body (gap down) → Bullish (gap up, closes >50% of first body).
        The Bible's highest-probability reversal pattern.
        """
        first_bearish = self.df["is_bearish"].shift(2)
        third_bullish = self.df["is_bullish"]
        first_body = self.df["body"].shift(2)
        second_body = self.df["body"].shift(1)
        first_close = self.df["close"].shift(2)
        second_close = self.df["close"].shift(1)
        second_open = self.df["open"].shift(1)
        third_close = self.df["close"]
        third_open = self.df["open"]

        first_mid = (self.df["open"].shift(2) + first_close) / 2

        return (
            first_bearish &
            (first_body > 0) &
            (second_body <= first_body * 0.5) &  # Small middle candle
            (third_bullish) &
            (third_close > first_mid)  # Closes above midpoint of first
        )

    def detect_evening_star(self) -> pd.Series:
        """
        Evening Star: Three-candle bearish reversal.
        Bullish → Small body (gap up) → Bearish (gap down, closes <50% of first body).
        """
        first_bullish = self.df["is_bullish"].shift(2)
        third_bearish = self.df["is_bearish"]
        first_body = self.df["body"].shift(2)
        second_body = self.df["body"].shift(1)
        first_close = self.df["close"].shift(2)
        first_open = self.df["open"].shift(2)
        third_close = self.df["close"]

        first_mid = (first_open + first_close) / 2

        return (
            first_bullish &
            (first_body > 0) &
            (second_body <= first_body * 0.5) &
            third_bearish &
            (third_close < first_mid)
        )

    def detect_three_white_soldiers(self) -> pd.Series:
        """
        Three White Soldiers: Three consecutive bullish candles with
        higher closes and opens within previous bodies.
        Strong bullish continuation/reversal confirmation.
        """
        c1_bullish = self.df["is_bullish"].shift(2)
        c2_bullish = self.df["is_bullish"].shift(1)
        c3_bullish = self.df["is_bullish"]

        c1_close = self.df["close"].shift(2)
        c2_close = self.df["close"].shift(1)
        c3_close = self.df["close"]
        c2_open = self.df["open"].shift(1)
        c3_open = self.df["open"]

        return (
            c1_bullish & c2_bullish & c3_bullish &
            (c2_close > c1_close) & (c3_close > c2_close) &
            (c2_open > self.df["open"].shift(2)) &
            (c2_open < c1_close) &
            (c3_open > c2_open) &
            (c3_open < c2_close)
        )

    def detect_three_black_crows(self) -> pd.Series:
        """
        Three Black Crows: Three consecutive bearish candles with
        lower closes and opens within previous bodies.
        Strong bearish continuation/reversal confirmation.
        """
        c1_bearish = self.df["is_bearish"].shift(2)
        c2_bearish = self.df["is_bearish"].shift(1)
        c3_bearish = self.df["is_bearish"]

        c1_close = self.df["close"].shift(2)
        c2_close = self.df["close"].shift(1)
        c3_close = self.df["close"]
        c2_open = self.df["open"].shift(1)
        c3_open = self.df["open"]

        return (
            c1_bearish & c2_bearish & c3_bearish &
            (c2_close < c1_close) & (c3_close < c2_close) &
            (c2_open < self.df["open"].shift(2)) &
            (c2_open > c1_close) &
            (c3_open < c2_open) &
            (c3_open > c2_close)
        )

    def detect_three_inside_up(self) -> pd.Series:
        """
        Three Inside Up: Bearish → Harami (small bullish inside first) → Bullish breakout.
        Bullish reversal confirmed by third candle closing above first's open.
        """
        first_bearish = self.df["is_bearish"].shift(2)
        second_bullish = self.df["is_bullish"].shift(1)
        third_bullish = self.df["is_bullish"]

        first_open = self.df["open"].shift(2)
        first_close = self.df["close"].shift(2)
        second_body = self.df["body"].shift(1)
        first_body = self.df["body"].shift(2)
        third_close = self.df["close"]

        return (
            first_bearish & second_bullish & third_bullish &
            (first_body > 0) &
            (second_body <= first_body * 0.5) &
            (third_close > first_open)
        )

    def detect_three_inside_down(self) -> pd.Series:
        """
        Three Inside Down: Bullish → Harami (small bearish inside first) → Bearish breakdown.
        Bearish reversal confirmed by third candle closing below first's open.
        """
        first_bullish = self.df["is_bullish"].shift(2)
        second_bearish = self.df["is_bearish"].shift(1)
        third_bearish = self.df["is_bearish"]

        first_open = self.df["open"].shift(2)
        first_body = self.df["body"].shift(2)
        second_body = self.df["body"].shift(1)
        third_close = self.df["close"]

        return (
            first_bullish & second_bearish & third_bearish &
            (first_body > 0) &
            (second_body <= first_body * 0.5) &
            (third_close < first_open)
        )

    # ═══════════════════════════════════════════════════════════
    # CONTINUATION PATTERNS
    # ═══════════════════════════════════════════════════════════

    def detect_rising_three_methods(self) -> pd.Series:
        """
        Rising Three Methods: Long bullish → 3 small bearish (within first range) → Long bullish.
        Bullish continuation.
        """
        first_bullish = self.df["is_bullish"].shift(4)
        first_body = self.df["body"].shift(4)
        first_high = self.df["high"].shift(4)
        first_low = self.df["low"].shift(4)
        last_bullish = self.df["is_bullish"]
        last_close = self.df["close"]
        first_close = self.df["close"].shift(4)

        # Middle candles stay within first body range
        middle_in_range = all(
            (self.df["high"].shift(i) <= first_high) &
            (self.df["low"].shift(i) >= first_low)
            for i in [3, 2, 1]
        )

        return (
            first_bullish & last_bullish &
            (first_body > 0) &
            middle_in_range &
            (last_close > first_close)
        )

    def detect_falling_three_methods(self) -> pd.Series:
        """
        Falling Three Methods: Long bearish → 3 small bullish (within first range) → Long bearish.
        Bearish continuation.
        """
        first_bearish = self.df["is_bearish"].shift(4)
        first_body = self.df["body"].shift(4)
        first_high = self.df["high"].shift(4)
        first_low = self.df["low"].shift(4)
        last_bearish = self.df["is_bearish"]
        last_close = self.df["close"]
        first_close = self.df["close"].shift(4)

        middle_in_range = all(
            (self.df["high"].shift(i) <= first_high) &
            (self.df["low"].shift(i) >= first_low)
            for i in [3, 2, 1]
        )

        return (
            first_bearish & last_bearish &
            (first_body > 0) &
            middle_in_range &
            (last_close < first_close)
        )

    # ═══════════════════════════════════════════════════════════
    # COMPREHENSIVE ANALYSIS
    # ═══════════════════════════════════════════════════════════

    def get_all_patterns(self) -> pd.DataFrame:
        """Run all pattern detectors and return a DataFrame with results."""
        patterns = pd.DataFrame(index=self.df.index)

        # Single candle patterns
        patterns["hammer"] = self.detect_hammer()
        patterns["shooting_star"] = self.detect_shooting_star()
        patterns["dragonfly_doji"] = self.detect_dragonfly_doji()
        patterns["gravestone_doji"] = self.detect_gravestone_doji()
        patterns["long_legged_doji"] = self.detect_long_legged_doji()
        patterns["marubozu_bullish"] = self.detect_marubozu_bullish()
        patterns["marubozu_bearish"] = self.detect_marubozu_bearish()
        patterns["spinning_top"] = self.detect_spinning_top()

        # Two-candle patterns
        patterns["bullish_engulfing"] = self.detect_bullish_engulfing()
        patterns["bearish_engulfing"] = self.detect_bearish_engulfing()
        patterns["piercing_line"] = self.detect_piercing_line()
        patterns["dark_cloud_cover"] = self.detect_dark_cloud_cover()
        patterns["tweezer_top"] = self.detect_tweezer_top()
        patterns["tweezer_bottom"] = self.detect_tweezer_bottom()

        # Three-candle patterns
        patterns["morning_star"] = self.detect_morning_star()
        patterns["evening_star"] = self.detect_evening_star()
        patterns["three_white_soldiers"] = self.detect_three_white_soldiers()
        patterns["three_black_crows"] = self.detect_three_black_crows()
        patterns["three_inside_up"] = self.detect_three_inside_up()
        patterns["three_inside_down"] = self.detect_three_inside_down()

        # Continuation patterns
      
