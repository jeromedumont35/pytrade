import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CRSICalculator
import CTransformToPanda
import CIndicatorsBTCAdder
import CTrendBreakDetector
import numpy as np

class CStrat_WDetector:
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

    def detect_w_pattern(
            self,
            df: pd.DataFrame,
            interval1: int,
            drop_pct: float,
            rise_pct: float,
            interval2: int,
            ratio_min: float,
            column_name: str
    ):
        """
        Détecte un pattern en 'W' :
        1. Chute du prix moyen de `drop_pct` sur `interval1` bougies
        2. Remontée de `rise_pct` sur `interval2` bougies
        Garde uniquement le point de détection avec le `low` le plus bas en cas de détections consécutives.

        :param df: DataFrame avec colonnes 'open', 'close', 'high', 'low'
        :param interval1: période de chute
        :param drop_pct: pourcentage de baisse (ex: -0.05)
        :param rise_pct: pourcentage de hausse (ex: 0.04)
        :param interval2: période de remontée
        :param ratio_min: ratio appliqué à 'low' pour la phase de remontée
        :param column_name: nom de la colonne des signaux (0 ou 1)
        :return: df avec la colonne des signaux ajoutée
        """
        if any(col not in df.columns for col in ["open", "close", "high", "low"]):
            raise ValueError("Le DataFrame doit contenir les colonnes 'open', 'close', 'high', 'low'.")

        price_mean = df["moy_l_h_e_c"]

        raw_signals = [0] * len(df)

        for i in range(interval1 + interval2, len(df)):
            start_price = price_mean.iloc[i - interval1 - interval2]
            mid_price = price_mean.iloc[i - interval2]
            drop = (mid_price - start_price) * 100 / start_price

            if drop > drop_pct:
                continue

            end_price = price_mean.iloc[i]
            rise = (end_price - mid_price) * 100 / mid_price

            if rise >= rise_pct:
                raw_signals[i - interval2] = 1

        # Nettoyage avancé des signaux dans une fenêtre de 5 minutes
        filtered_signals = [0] * len(df)

        signal_df = df.copy()
        signal_df["raw"] = raw_signals

        signal_points = signal_df[signal_df["raw"] == 1]
        used_indices = set()

        for current_time, _ in signal_points.iterrows():
            if current_time in used_indices:
                continue

            window_end = current_time + pd.Timedelta(minutes=interval2)
            window_points = signal_points.loc[
            (signal_points.index >= current_time) & (signal_points.index < window_end)]

            if not window_points.empty:
                min_low_idx = window_points["low"].idxmin()
                filtered_signals[df.index.get_loc(min_low_idx)] = 1
                used_indices.update(window_points.index)

        df[column_name] = filtered_signals
        # # Nettoyage des détections consécutives
        # filtered_signals = [0] * len(df)
        # i = 0
        # while i < len(raw_signals):
        #     if raw_signals[i] == 1:
        #         # Début d'un groupe de détections consécutives
        #         start = i
        #         while i + 1 < len(raw_signals) and raw_signals[i + 1] == 1:
        #             i += 1
        #         end = i
        #
        #         # Trouver l'index avec le low le plus bas dans l'intervalle [start, end]
        #         min_low_idx = df["low"].iloc[start:end + 1].idxmin()
        #         filtered_signals[df.index.get_loc(min_low_idx)] = 1
        #     i += 1
        #
        # df[column_name] = filtered_signals
        return df


    def apply_indicators(self, df, is_btc_file):
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

        df = CRSICalculator.CRSICalculator(df, period=14,
                                           close_times=[(3, 59), (7, 59), (11, 59), (15, 59), (19, 59), (23, 59)],
                                           name="rsi_4h_14").get_df()
        df = df.drop(columns=[col for col in df.columns if col.startswith("avg_")])

        if not is_btc_file:
            adder = CIndicatorsBTCAdder.CIndicatorsBTCAdder(btc_dir="../panda")
            df = adder.add_columns(df, ["rsi_4h_14", "close"])

        df = df.rename(columns={"BTC_close": "BTC_close__k_P1"})

        df = self.detect_w_pattern(
            df,
            interval1=30,
            drop_pct=-3,
            rise_pct=0.7,
            interval2=10,
            ratio_min=0.5,
            column_name="w_patte_1_detection_P3"
        )

        df = df.rename(columns={"moy_l_h_e_c": "moy_l_h_e_c__c_P1"})
        df["W_patte1_*_b_P1"] = np.where(df["w_patte_1_detection_P3"] == 1, df["moy_l_h_e_c__c_P1"], np.nan)

        return df

    def run(self):
        self.transformer.process_all(self.apply_indicators)

if __name__ == "__main__":
    strat = CStrat_WDetector()
    strat.run()


