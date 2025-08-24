import pandas as pd
import numpy as np
import sys, os
from enum import Enum, auto

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../indicators")))

import CRSICalculator
import CTransformToPanda
import CIndicatorsBTCAdder


class StratState(Enum):
    WAIT_RSI5M_LOW = auto()
    WAIT_REBOUND_UP = auto()
    WAIT_REBOUND_DOWN = auto()
    WAIT_AFTER_MAX = auto()
    WAIT_BREAK_MAX = auto()
    TRADE_OPEN = auto()


class CStrat_RSI5min30:
    def __init__(self, interface_trade=None, risk_per_trade_pct: float = 0.1,
                 stop_loss_ratio: float = 0.98, max_bars_in_trade: int = 288,
                 break_max_timeout_bars: int = 24):
        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_ratio = stop_loss_ratio
        self.max_bars_in_trade = max_bars_in_trade
        self.break_max_timeout_bars = break_max_timeout_bars  # 24 bougies 5m = 2h
        self.transformer = CTransformToPanda.CTransformToPanda(raw_dir="../raw", panda_dir="../panda")
        self.state = {}  # symbol → dict état

    def _init_symbol_state(self, symbol):
        if symbol not in self.state:
            self.state[symbol] = {
                "state": StratState.WAIT_RSI5M_LOW,
                "rsi5m_min": None,
                "rebound_max_price": None,
                "wait_start_index": None,
                "entry_index": None,
                "break_max_start_index": None
            }

    def _reset_symbol_state(self, symbol, new_state=StratState.WAIT_RSI5M_LOW):
        """Réinitialise complètement l'état du symbole et définit l'état initial."""
        old_state = self.state[symbol]["state"] if symbol in self.state else None
        print(f"[TRACE] {symbol}: RESET state {old_state} -> {new_state}")
        self.state[symbol] = {
            "state": new_state,
            "rsi5m_min": None,
            "rebound_max_price": None,
            "wait_start_index": None,
            "entry_index": None,
            "break_max_start_index": None
        }

    def _set_state(self, symbol, new_state):
        """Change d’état avec trace systématique"""
        old_state = self.state[symbol]["state"]
        if old_state != new_state:
            print(f"[TRACE] {symbol}: STATE {old_state.name} -> {new_state.name}")
        self.state[symbol]["state"] = new_state

    def apply(self, df, symbol, row, timestamp, open_positions, blocked):
        actions = []
        self._init_symbol_state(symbol)
        state = self.state[symbol]

        i = df.index.get_loc(timestamp)
        if i < 240:
            return actions

        close = row["close__b_P1"]
        rsi5m = row.get("rsi_5m_14_P2", None)
        rsi4h = row.get("rsi_4h_14_P2", None)
        rsi4h_prev1 = df["rsi_4h_14_P2"].iloc[i - 10]
        rsi4h_prev2 = df["rsi_4h_14_P2"].iloc[i - 240]
        open_pos = next((p for p in open_positions if p["symbol"] == symbol), None)

        # =================== MACHINE À ÉTATS ===================
        # 1️⃣ WAIT_RSI5M_LOW
        if state["state"] == StratState.WAIT_RSI5M_LOW:
            if rsi5m is not None and rsi5m < 30:
                state["rsi5m_min"] = rsi5m
                if rsi4h_prev1 >= rsi4h_prev2 + 1:
                    self._set_state(symbol, StratState.WAIT_REBOUND_UP)
                elif rsi4h_prev1 < rsi4h_prev2 - 2 and rsi4h < 30:
                    self._set_state(symbol, StratState.WAIT_REBOUND_DOWN)

        # 2️⃣ WAIT_REBOUND_UP
        elif state["state"] == StratState.WAIT_REBOUND_UP:
            if rsi5m is not None:
                state["rsi5m_min"] = min(state["rsi5m_min"], rsi5m)
                if rsi5m > state["rsi5m_min"] + 3 :

                    if blocked :
                        self._set_state(symbol, StratState.WAIT_RSI5M_LOW)
                        return actions

                    sl_price = df.iloc[i - 30:i]["low"].min()
                    usdc = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct
                    actions.append({
                        "action": "OPEN",
                        "symbol": symbol,
                        "side": "LONG",
                        "price": close,
                        "sl": sl_price,
                        "usdc": usdc,
                        "reason": "RSI5M_REBOUND_RSI4H_UP",
                        "entry_index": i
                    })
                    state["entry_index"] = i
                    self._set_state(symbol, StratState.TRADE_OPEN)

        # 3️⃣ WAIT_REBOUND_DOWN
        elif state["state"] == StratState.WAIT_REBOUND_DOWN:
            if rsi5m is not None:
                state["rsi5m_min"] = min(state["rsi5m_min"], rsi5m)
                if rsi5m > state["rsi5m_min"] + 3 :
                    self._set_state(symbol, StratState.WAIT_AFTER_MAX)
                    state["wait_start_index"] = i
                    state["rebound_max_price"] = close

        # 4️⃣ WAIT_AFTER_MAX
        elif state["state"] == StratState.WAIT_AFTER_MAX:
            df_window = df.iloc[state["wait_start_index"]:i + 1]
            max_idx = df_window["close__b_P1"].idxmax()
            max_close = df_window.loc[max_idx, "close__b_P1"]
            df_after_max = df_window.loc[max_idx:]
            min_close = df_after_max["close__b_P1"].min()

            if min_close <= max_close * 0.985:
                self._set_state(symbol, StratState.WAIT_BREAK_MAX)
                state["break_max_start_index"] = i  # ⏳ on démarre le timer pour 2h
                actions.append({
                    "action": "M1",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "position": "LONG",
                    "reason": "CAS_A_SIMPLE_REBOUND",
                    "entry_index": i
                })
            elif i - state["wait_start_index"] >= 60:
                self._set_state(symbol, StratState.WAIT_RSI5M_LOW)
                state["rsi5m_min"] = None
                state["rebound_max_price"] = None
                state["wait_start_index"] = None
                state["entry_index"] = None
                state["break_max_start_index"] = None
            else:
                state["rebound_max_price"] = max(state.get("rebound_max_price", 0), max_close)

        # 5️⃣ WAIT_BREAK_MAX
        elif state["state"] == StratState.WAIT_BREAK_MAX:
            if close > state["rebound_max_price"]:

                if blocked:
                    self._set_state(symbol, StratState.WAIT_RSI5M_LOW)
                    return actions

                sl_price = df.iloc[i - 30:i]["low"].min()
                usdc = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct
                actions.append({
                    "action": "OPEN",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "sl": sl_price,
                    "usdc": usdc,
                    "reason": "BREAK_MAX_CONFIRM",
                    "entry_index": i
                })
                state["entry_index"] = i
                self._set_state(symbol, StratState.TRADE_OPEN)

            elif state.get("break_max_start_index") is not None and \
                 (i - state["break_max_start_index"]) >= self.break_max_timeout_bars:
                print(f"[TRACE] {symbol}: Timeout WAIT_BREAK_MAX -> RESET (2h sans breakout)")
                self._set_state(symbol, StratState.WAIT_RSI5M_LOW)
                state["rsi5m_min"] = None
                state["rebound_max_price"] = None
                state["wait_start_index"] = None
                state["entry_index"] = None
                state["break_max_start_index"] = None

        # 6️⃣ TRADE_OPEN
        elif state["state"] == StratState.TRADE_OPEN and open_pos is not None:
            sl_price = open_pos.get("sl")
            if sl_price and close <= sl_price:
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
                self._reset_symbol_state(symbol, StratState.WAIT_RSI5M_LOW)

            elif rsi5m and rsi5m >= 60:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "SELL_LONG",
                    "reason": "TP_TOTAL",
                    "position": open_pos
                })
                self._reset_symbol_state(symbol, StratState.WAIT_RSI5M_LOW)

            elif "entry_index" in open_pos and (i - open_pos["entry_index"]) >= self.max_bars_in_trade:
                actions.append({
                    "action": "CLOSE",
                    "symbol": symbol,
                    "side": "LONG",
                    "price": close,
                    "exit_price": close,
                    "usdc": open_pos.get("usdc", 0),
                    "exit_side": "SELL_LONG",
                    "reason": "TIME_BASED_EXIT",
                    "position": open_pos
                })
                self._reset_symbol_state(symbol, StratState.WAIT_RSI5M_LOW)

        return actions

    def apply_indicators(self, df, is_btc_file):
        df = df.copy()

        # ⚡ Nettoyage de l’index pour éviter les doublons et trier chronologiquement
        df = df[~df.index.duplicated(keep='last')]
        df = df.sort_index()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

        # 🔹 Nettoyage des anciennes colonnes RSI pour éviter KeyError
        rsi_cols_to_remove = [col for col in df.columns if col.startswith("avg_gain") or
                              col.startswith("avg_loss") or
                              col.startswith("rsi_4h_14") or
                              col.startswith("rsi_5m_14")]
        df = df.drop(columns=rsi_cols_to_remove, errors=True)

        # RSI 4h
        df = CRSICalculator.RSICalculator(
            df, period=14,
            close_times=[(h, m) for h in range(0, 24, 4) for m in [0]],
            name="rsi_4h_14"
        ).get_df()

        # RSI 5m
        close_times_5m = [(h, m) for h in range(24) for m in range(0, 60, 5)]
        df = CRSICalculator.RSICalculator(
            df, period=14, close_times=close_times_5m, name="rsi_5m_14"
        ).get_df()

        # 🔹 Renommage colonnes pour la stratégie
        df = df.rename(columns={
            "rsi_4h_14": "rsi_4h_14_P2",
            "rsi_5m_14": "rsi_5m_14_P2",
            "close": "close__b_P1"
        })

        # 🔹 Affichage des RSI pour la dernière bougie
        rsi_cols = [col for col in df.columns if col.startswith("rsi")]
        print("\n[TRACE] Dernière bougie - valeurs RSI :")
        print(df[rsi_cols].tail(1))

        return df

    def run(self):
        self.transformer.process_all(self.apply_indicators)


if __name__ == "__main__":
    strat = CStrat_RSI5min30()
    strat.run()
