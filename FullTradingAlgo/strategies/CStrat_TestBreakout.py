import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CRSICalculator
import CTransformToPanda
import CIndicatorsBTCAdder
import CTrendBreakDetector

class CStrat_TestBreakout:
    def __init__(self, interface_trade=None, risk_per_trade_pct: float = 0.1, stop_loss_ratio: float = 0.98):
        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_ratio = stop_loss_ratio
        self.transformer =CTransformToPanda.CTransformToPanda(raw_dir="../raw", panda_dir="../panda")

    def apply(self, df, symbol, row, timestamp, open_positions):
        actions = []
        i = df.index.get_loc(timestamp)
        x = 50
        if i < x:
            return actions

        current_rsi = row["rsi_4h_14"]
        rsi_window = df["rsi_4h_14"].iloc[i - x:i]

        open_pos = next((p for p in open_positions if p["symbol"] == symbol), None)

        if open_pos:
            # aucune logique de clôture automatique
            return actions

        if self.interface_trade.get_available_usdc() > 10:
            close = row["close"]
            montant_trade = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct

            if current_rsi > 30 and (rsi_window < 30).all():
                sl_price = close * self.stop_loss_ratio
                actions.append({
                    "action": "OPEN",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "sl": sl_price,
                    "usdc": montant_trade
                })
            elif current_rsi < 70 and (rsi_window > 70).all():
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
        df = df.drop(columns=[col for col in df.columns if col.startswith("avg_")])

        if not is_btc_file:
            adder = CIndicatorsBTCAdder.CIndicatorsBTCAdder(btc_dir="../panda")
            df = adder.add_columns(df, ["rsi_4h_14", "close"])

        detector = CTrendBreakDetector.CTrendBreakDetector()
        df = detector.detect_breaks(
            df,
            window=30,
            alpha=0.0001,
            signal_col_name="my_break_signal"
        )

        # Compter les occurrences des valeurs 1, -1, 0
        counts = df["my_break_signal"].value_counts(dropna=False)

        # value_counts(dropna=False) compte aussi les NaN
        print(counts)

        return df

    def run(self):
        self.transformer.process_all(self.apply_indicators)

if __name__ == "__main__":
    strat = CStrat_TestBreakout()
    strat.run()