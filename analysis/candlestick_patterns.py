import pandas as pd
import numpy as np

class CandlestickPatterns:
    def __init__(self, df):
        self.df = df.copy()
        self._calc_props()

    def _calc_props(self):
        self.df["body"] = abs(self.df["close"] - self.df["open"])
        self.df["upper_shadow"] = self.df["high"] - self.df[["open","close"]].max(axis=1)
        self.df["lower_shadow"] = self.df[["open","close"]].min(axis=1) - self.df["low"]
        self.df["total_range"] = self.df["high"] - self.df["low"]
        self.df["is_bullish"] = self.df["close"] > self.df["open"]
        self.df["is_bearish"] = self.df["close"] < self.df["open"]

    def detect_hammer(self):
        b, l, u, t = self.df["body"], self.df["lower_shadow"], self.df["upper_shadow"], self.df["total_range"]
        return (t > 0) & (b > 0) & (l >= 2*b) & (u <= b*0.3) & (b <= t*0.35)

    def detect_shooting_star(self):
        b, l, u, t = self.df["body"], self.df["lower_shadow"], self.df["upper_shadow"], self.df["total_range"]
        return (t > 0) & (b > 0) & (u >= 2*b) & (l <= b*0.3) & (b <= t*0.35)

    def detect_dragonfly_doji(self):
        b, l, u, t = self.df["body"], self.df["lower_shadow"], self.df["upper_shadow"], self.df["total_range"]
        return (t > 0) & (b <= t*0.05) & (l >= t*0.6) & (u <= t*0.05)

    def detect_gravestone_doji(self):
        b, l, u, t = self.df["body"], self.df["lower_shadow"], self.df["upper_shadow"], self.df["total_range"]
        return (t > 0) & (b <= t*0.05) & (u >= t*0.6) & (l <= t*0.05)

    def detect_long_legged_doji(self):
        b, l, u, t = self.df["body"], self.df["lower_shadow"], self.df["upper_shadow"], self.df["total_range"]
        return (t > 0) & (b <= t*0.05) & (l >= t*0.25) & (u >= t*0.25) & (abs(l-u) <= t*0.15)

    def detect_marubozu_bullish(self):
        b, u, l, t = self.df["body"], self.df["upper_shadow"], self.df["lower_shadow"], self.df["total_range"]
        return (t > 0) & self.df["is_bullish"] & (b >= t*0.8) & (u <= t*0.1) & (l <= t*0.1)

    def detect_marubozu_bearish(self):
        b, u, l, t = self.df["body"], self.df["upper_shadow"], self.df["lower_shadow"], self.df["total_range"]
        return (t > 0) & self.df["is_bearish"] & (b >= t*0.8) & (u <= t*0.1) & (l <= t*0.1)

    def detect_spinning_top(self):
        b, l, u, t = self.df["body"], self.df["lower_shadow"], self.df["upper_shadow"], self.df["total_range"]
        return (t > 0) & (b <= t*0.25) & (l > b) & (u > b)

    def detect_bullish_engulfing(self):
        return (
            self.df["is_bearish"].shift(1) & self.df["is_bullish"] &
            (self.df["open"] <= self.df["close"].shift(1)) &
            (self.df["close"] >= self.df["open"].shift(1)) &
            (self.df["body"] > self.df["body"].shift(1))
        )

    def detect_bearish_engulfing(self):
        return (
            self.df["is_bullish"].shift(1) & self.df["is_bearish"] &
            (self.df["open"] >= self.df["close"].shift(1)) &
            (self.df["close"] <= self.df["open"].shift(1)) &
            (self.df["body"] > self.df["body"].shift(1))
        )

    def detect_piercing_line(self):
        prev_bearish = self.df["is_bearish"].shift(1)
        curr_bullish = self.df["is_bullish"]
        prev_body = self.df["body"].shift(1)
        prev_low = self.df["low"].shift(1)
        prev_open = self.df["open"].shift(1)
        prev_close = self.df["close"].shift(1)
        mid = (prev_open + prev_close) / 2
        return prev_bearish & curr_bullish & (prev_body > 0) & (self.df["open"] < prev_low) & (self.df["close"] > mid) & (self.df["close"] < prev_open)

    def detect_dark_cloud_cover(self):
        prev_bullish = self.df["is_bullish"].shift(1)
        curr_bearish = self.df["is_bearish"]
        prev_body = self.df["body"].shift(1)
        prev_high = self.df["high"].shift(1)
        prev_open = self.df["open"].shift(1)
        prev_close = self.df["close"].shift(1)
        mid = (prev_open + prev_close) / 2
        return prev_bullish & curr_bearish & (prev_body > 0) & (self.df["open"] > prev_high) & (self.df["close"] < mid) & (self.df["close"] > prev_open)

    def detect_tweezer_top(self):
        return self.df["is_bullish"].shift(1) & self.df["is_bearish"] & (abs(self.df["high"] - self.df["high"].shift(1)) <= self.df["total_range"].rolling(14).mean() * 0.1)

    def detect_tweezer_bottom(self):
        return self.df["is_bearish"].shift(1) & self.df["is_bullish"] & (abs(self.df["low"] - self.df["low"].shift(1)) <= self.df["total_range"].rolling(14).mean() * 0.1)

    def detect_morning_star(self):
        first_bearish = self.df["is_bearish"].shift(2)
        third_bullish = self.df["is_bullish"]
        first_body = self.df["body"].shift(2)
        second_body = self.df["body"].shift(1)
        first_mid = (self.df["open"].shift(2) + self.df["close"].shift(2)) / 2
        return first_bearish & (first_body > 0) & (second_body <= first_body * 0.5) & third_bullish & (self.df["close"] > first_mid)

    def detect_evening_star(self):
        first_bullish = self.df["is_bullish"].shift(2)
        third_bearish = self.df["is_bearish"]
        first_body = self.df["body"].shift(2)
        second_body = self.df["body"].shift(1)
        first_mid = (self.df["open"].shift(2) + self.df["close"].shift(2)) / 2
        return first_bullish & (first_body > 0) & (second_body <= first_body * 0.5) & third_bearish & (self.df["close"] < first_mid)

    def detect_three_white_soldiers(self):
        return (
            self.df["is_bullish"].shift(2) & self.df["is_bullish"].shift(1) & self.df["is_bullish"] &
            (self.df["close"].shift(1) > self.df["close"].shift(2)) &
            (self.df["close"] > self.df["close"].shift(1))
        )

    def detect_three_black_crows(self):
        return (
            self.df["is_bearish"].shift(2) & self.df["is_bearish"].shift(1) & self.df["is_bearish"] &
            (self.df["close"].shift(1) < self.df["close"].shift(2)) &
            (self.df["close"] < self.df["close"].shift(1))
        )

    def detect_three_inside_up(self):
        return (
            self.df["is_bearish"].shift(2) & self.df["is_bullish"].shift(1) & self.df["is_bullish"] &
            (self.df["body"].shift(1) <= self.df["body"].shift(2) * 0.5) &
            (self.df["close"] > self.df["open"].shift(2))
        )

    def detect_three_inside_down(self):
        return (
            self.df["is_bullish"].shift(2) & self.df["is_bearish"].shift(1) & self.df["is_bearish"] &
            (self.df["body"].shift(1) <= self.df["body"].shift(2) * 0.5) &
            (self.df["close"] < self.df["open"].shift(2))
        )

    def detect_rising_three_methods(self):
        return (
            self.df["is_bullish"].shift(4) & self.df["is_bullish"] &
            (self.df["close"] > self.df["close"].shift(4))
        )

    def detect_falling_three_methods(self):
        return (
            self.df["is_bearish"].shift(4) & self.df["is_bearish"] &
            (self.df["close"] < self.df["close"].shift(4))
        )

    def get_all_patterns(self):
        patterns = pd.DataFrame(index=self.df.index)
        patterns["hammer"] = self.detect_hammer()
        patterns["shooting_star"] = self.detect_shooting_star()
        patterns["dragonfly_doji"] = self.detect_dragonfly_doji()
        patterns["gravestone_doji"] = self.detect_gravestone_doji()
        patterns["long_legged_doji"] = self.detect_long_legged_doji()
        patterns["marubozu_bullish"] = self.detect_marubozu_bullish()
        patterns["marubozu_bearish"] = self.detect_marubozu_bearish()
        patterns["spinning_top"] = self.detect_spinning_top()
        patterns["bullish_engulfing"] = self.detect_bullish_engulfing()
        patterns["bearish_engulfing"] = self.detect_bearish_engulfing()
        patterns["piercing_line"] = self.detect_piercing_line()
        patterns["dark_cloud_cover"] = self.detect_dark_cloud_cover()
        patterns["tweezer_top"] = self.detect_tweezer_top()
        patterns["tweezer_bottom"] = self.detect_tweezer_bottom()
        patterns["morning_star"] = self.detect_morning_star()
        patterns["evening_star"] = self.detect_evening_star()
        patterns["three_white_soldiers"] = self.detect_three_white_soldiers()
        patterns["three_black_crows"] = self.detect_three_black_crows()
        patterns["three_inside_up"] = self.detect_three_inside_up()
        patterns["three_inside_down"] = self.detect_three_inside_down()
        patterns["rising_three_methods"] = self.detect_rising_three_methods()
        patterns["falling_three_methods"] = self.detect_falling_three_methods()
        return patterns
