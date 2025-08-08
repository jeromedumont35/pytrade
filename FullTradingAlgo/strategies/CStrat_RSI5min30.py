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

class CStrat_RSI5min30:
    def __init__(self, interface_trade=None, risk_per_trade_pct: float = 0.1, stop_loss_ratio: float = 0.98):
        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_ratio = stop_loss_ratio
        self.transformer = CTransformToPanda.CTransformToPanda(raw_dir="../raw", panda_dir="../panda")
        # Nouveau : suivi des SL récents
        self._waiting_reentry_after_sl = {}

    def apply(self, df, symbol, row, timestamp, open_positions):
        actions = []
        i = df.index.get_loc(timestamp)
        window_size = 30  # minutes pour stop loss

        if i < window_size or i < 2:
            return actions

        open_pos = next((p for p in open_positions if p["symbol"] == symbol), None)
        close = row["close"]
        current_rsi_5m = row.get("rsi_5m_14", None)

        # === CAS SANS POSITION OUVERTE ===
        if open_pos is None:
            # Re-entrée après SL uniquement si flag actif
            if self._waiting_reentry_after_sl.get(symbol, False):
                ts_10min_ago = timestamp - pd.Timedelta(minutes=10)
                if ts_10min_ago in df.index and current_rsi_5m is not None:
                    rsi_10min_ago = df.at[ts_10min_ago, "rsi_5m_14"]
                    if rsi_10min_ago is not None and rsi_10min_ago > 0:
                        delta_rsi_pct = 100 * (current_rsi_5m - rsi_10min_ago) / rsi_10min_ago
                        if delta_rsi_pct >= 3:
                            montant_trade = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct
                            stop_loss_window = df.iloc[i - window_size:i]
                            sl_price = stop_loss_window["moy_l_h_e_c__c_P1"].min()

                            actions.append({
                                "action": "OPEN",
                                "symbol": symbol,
                                "side": "LONG",
                                "price": close,
                                "sl": sl_price,
                                "position": "LONG",
                                "usdc": montant_trade,
                                "reason": "RSI_UP_3pct_IN_10MIN_AFTER_SL"
                            })
                            # On désactive le flag après ré-entrée
                            self._waiting_reentry_after_sl[symbol] = False
                            return actions

            # Ouverture LONG classique si signal RSI
            if not pd.isna(row.get("rsi_5_remonte_*_g_P1", np.nan)):
                montant_trade = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct
                stop_loss_window = df.iloc[i - window_size:i]
                sl_price = stop_loss_window["moy_l_h_e_c__c_P1"].min()

                actions.append({
                    "action": "OPEN",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "sl": sl_price,
                    "position": "LONG",
                    "usdc": montant_trade,
                    "reason": "RSI_SIGNAL"
                })
            return actions

        # === CAS AVEC POSITION LONG OUVERTE ===
        if open_pos["side"] == "LONG":
            sl_price = open_pos.get("sl", None)

            # Fermeture au stop loss
            if sl_price is not None and close <= sl_price:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "SELL_LONG",
                    "reason": "STOP_LOSS",
                    "position": open_pos
                })
                # On active le flag pour ré-entrée potentielle
                self._waiting_reentry_after_sl[symbol] = True
                return actions

            # Fermeture par RSI
            if current_rsi_5m is not None and current_rsi_5m >= 65:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "SELL_LONG",
                    "reason": "REVERSAL_HA",
                    "position": open_pos
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

    def detect_rsi_remonte_progressive(self, df, minutes=10, delta=3):
        col_cross = 'r_5m_cross_*_b_P1'  # Colonne avec les points de départ
        col_result = 'rsi_5_remonte_*_g_P1'  # Colonne résultat avec prix lors de la remontée

        df[col_result] = np.nan

        # Récupérer les index des points initiaux
        cross_points = df.index[df[col_cross].notna()]

        for start_time in cross_points:
            prev_rsi = df.at[start_time, 'rsi_5m_14']

            current_time = start_time + pd.Timedelta(minutes=minutes)

            while current_time in df.index:
                current_rsi = df.at[current_time, 'rsi_5m_14']

                # On compare le RSI actuel avec le RSI précédent
                if current_rsi >= prev_rsi + delta:
                    # La remontée est détectée, on prend le prix à ce moment
                    df.at[current_time, col_result] = df.at[current_time, 'moy_l_h_e_c__c_P1']
                    break  # On arrête la boucle pour ce point initial

                # Sinon, on continue avec ce RSI actuel comme référence pour la prochaine étape
                prev_rsi = current_rsi
                current_time += pd.Timedelta(minutes=minutes)

        return df

    def add_rsi_cross_verif(self, df, minutes=10, pas=2):
        col_init = 'r_5m_cross_*_b_P1'
        col_verif = 'r_5m_cross_verif_*_k_P1'

        df[col_verif] = np.nan

        points_idx = df.index[df[col_init].notna()]

        last_verif_time = None

        for t in points_idx:
            if last_verif_time is not None and (t - last_verif_time).total_seconds() < minutes * 60:
                continue

            rsi_init = df.at[t, 'rsi_5m_14']
            t_future = t + pd.Timedelta(minutes=minutes)

            future_idx = df.index[df.index >= t_future]
            if len(future_idx) == 0:
                continue

            idx_future = future_idx[0]
            rsi_future = df.at[idx_future, 'rsi_5m_14']

            if rsi_future <= rsi_init - pas:
                df.at[idx_future, col_verif] = df.at[idx_future, col_init]
                last_verif_time = t_future

        return df

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

        df = CRSICalculator.RSICalculator(df, period=14,
                                          close_times=[(3, 59), (7, 59), (11, 59), (15, 59), (19, 59), (23, 59)],
                                          name="rsi_4h_14").get_df()

        close_times_5m = [(h, m) for h in range(24) for m in range(0, 60, 5)]
        # Utilisation de ta classe
        rsi_calc = CRSICalculator.RSICalculator(df, period=14, close_times=close_times_5m, name="rsi_5m_14")
        df = rsi_calc.get_df()

        df = df.drop(columns=[col for col in df.columns if col.startswith("avg_")])

        if not is_btc_file:
            adder = CIndicatorsBTCAdder.CIndicatorsBTCAdder(btc_dir="../panda")
            df = adder.add_columns(df, ["rsi_4h_14", "close","rsi_5m_14"])

        #df = df.rename(columns={"BTC_close": "BTC_close__k_P1"})

        df['5min_cross'] = np.where(
            (df['rsi_5m_14'] < 30) & (df['rsi_5m_14'].shift(1) >= 30),1,0)

        df = df.rename(columns={"moy_l_h_e_c": "moy_l_h_e_c__c_P1"})
        # 5. Récupérer les prix correspondants
        #df['r_5m_cross_*_b_P1'] = np.where(df['5min_cross'] == 1, df['moy_l_h_e_c__c_P1'], np.nan)

        # 5. Application de la condition RSI 4H < 35
        df['r_5m_cross_*_b_P1'] = np.where(
            (df['5min_cross'] == 1) & (df['rsi_4h_14'] < 35),
            df['moy_l_h_e_c__c_P1'],
            np.nan
        )

        df = self.detect_rsi_remonte_progressive(df)

        return df

    def run(self):
        self.transformer.process_all(self.apply_indicators)

if __name__ == "__main__":
    strat = CStrat_RSI5min30()
    strat.run()


