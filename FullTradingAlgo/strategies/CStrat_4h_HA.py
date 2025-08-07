import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import CRSICalculator
import CTransformToPanda
import CIndicatorsBTCAdder
import CJapanesePatternDetector

class CStrat_4h_HA:
    def __init__(self, interface_trade=None, risk_per_trade_pct: float = 0.1, stop_loss_ratio: float = 0.98):
        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_ratio = stop_loss_ratio
        self.transformer =CTransformToPanda.CTransformToPanda(raw_dir="../raw", panda_dir="../panda")

    def apply(self, df, symbol, row, timestamp, open_positions):
        actions = []

        i = df.index.get_loc(timestamp)
        if i < 240 * 4:
            return actions

        current_close = df["close_4h_HA"].iloc[i]
        past = [df["close_4h_HA"].iloc[i - 240 * j] for j in range(1, 5)]
        rsi_4h = row["rsi_4h_14"]

        open_pos = next((p for p in open_positions if p["symbol"] == symbol), None)
        can_reverse = True
        if open_pos:
            minutes_open = (timestamp - open_pos["opened_on"]).total_seconds() / 60
            if minutes_open < 240:
                can_reverse = False

        if can_reverse and open_pos:
            if open_pos["side"] == "SHORT" and current_close > past[0]:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "exit_price": row["close"],
                    "exit_side": "BUY_SHORT",
                    "reason": "REVERSAL_HA",
                    "position": open_pos
                })
            elif open_pos["side"] == "LONG" and current_close < past[0]:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "exit_price": row["close"],
                    "exit_side": "SELL_LONG",
                    "reason": "REVERSAL_HA",
                    "position": open_pos
                })

        if not open_pos and self.interface_trade and self.interface_trade.get_available_usdc() > 10:
            close = row["close"]
            montant_trade = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct

            if current_close > past[0] < past[1] < past[2] < past[3] and rsi_4h < 30:
                sl_price = close * self.stop_loss_ratio
                actions.append({
                    "action": "OPEN",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "sl": sl_price,
                    "usdc": montant_trade
                })
            elif current_close < past[0] > past[1] > past[2] > past[3] and rsi_4h > 70:
                sl_price = close * (2 - self.stop_loss_ratio)
                actions.append({
                    "action": "OPEN",
                    "symbol": symbol,
                    "side": "SHORT",
                    "price": close,
                    "sl": sl_price,
                    "usdc": montant_trade
                })

        return actions

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

        df = CRSICalculator.RSICalculator(df, period=14,
                                          close_times=[(3, 59), (7, 59), (11, 59), (15, 59), (19, 59), (23, 59)],
                                          name="rsi_4h_14").get_df()

        close_times_1h = [(h, 59) for h in range(24)]
        df = CRSICalculator.RSICalculator(df, period=14, close_times=close_times_1h, name="rsi_1h_14").get_df()
        df = df.drop(columns=[col for col in df.columns if "avg_" in col])

        window = 240  # 4h = 240 minutes
        open_4h = df['open'].rolling(window=window).apply(lambda x: x.iloc[0], raw=False)
        high_4h = df['high'].rolling(window=window).max()
        low_4h = df['low'].rolling(window=window).min()
        close_4h = df['close'].rolling(window=window).apply(lambda x: x.iloc[-1], raw=False)

        df['close_4h_HA'] = (open_4h + high_4h + low_4h + close_4h) / 4

        detector = CJapanesePatternDetector.CJapanesePatternDetector(
            pattern_name="CDLMORNINGSTAR",
            timeframe="5min",
            pct_threshold=0.3,
            output_col_name="jap_hammer_5m"
        )
        df = detector.detect_and_filter(df)

        if not is_btc_file:
            adder = CIndicatorsBTCAdder.CIndicatorsBTCAdder(btc_dir="../panda")
            df = adder.add_columns(df, ["rsi_4h_14", "close"])

        return df

    def run(self):
        self.transformer.process_all(self.apply_indicators)

if __name__ == "__main__":
    strat = CStrat_4h_HA()
    strat.run()