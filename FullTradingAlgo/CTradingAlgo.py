import os
import pandas as pd
from tqdm import tqdm

# from strategies.CStrat_4h_HA import CStrat_4h_HA
from strategies.CStrat_RSI5min30 import CStrat_RSI5min30


class CTradingAlgo:
    def __init__(self, l_interface_trade, risk_per_trade_pct: float = 0.1, strategy_name: str = "strategy_1"):
        self.interface_trade = l_interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.strategy_name = strategy_name
        self.stop_loss_ratio = 0.98

        self.open_positions = []
        self.closed_count = 0
        self.total_trades = 0

        # Stockage des DataFrames par symbol
        self.symbol_dfs = {}

        # Dynamically instantiate the strategy class
        if self.strategy_name == "4h_HA":
            self.strategy = CStrat_4h_HA(self.interface_trade, self.risk_per_trade_pct, self.stop_loss_ratio)
        elif self.strategy_name == "rsi_30":
            self.strategy = CStrat_RSI30(self.interface_trade, self.risk_per_trade_pct, self.stop_loss_ratio)
        elif self.strategy_name == "RSI5min30":
            self.strategy = CStrat_RSI5min30(self.interface_trade, self.risk_per_trade_pct)
        else:
            raise ValueError(f"Stratégie inconnue : {self.strategy_name}")

    def run(self, list_data: list, execution):
        merged = []
        for df, symbol in list_data:
            df = df.copy()
            df["symbol"] = symbol
            # Ajout des colonnes vides
            df["entry_price_*_g_P1"] = None
            df["exit_price_*_r_P1"] = None
            self.symbol_dfs[symbol] = df
            merged.append(df)

        full_df = pd.concat(merged).sort_index()
        grouped = full_df.groupby(full_df.index)
        total_ticks = len(grouped)

        # Initialisation de blocked
        blocked = execution  # si exec=False -> blocked=False, si exec=True -> blocked=True

        for i, (timestamp, group) in enumerate(
                tqdm(grouped, total=total_ticks, desc="🔄 Simulation trading")
        ):
            # Si on est sur la dernière minute et que exec=True, on débloque
            if execution and i == total_ticks - 1:
                blocked = False

            for _, row in group.iterrows():
                symbol = row["symbol"]
                df = self.symbol_dfs[symbol]
                if timestamp not in df.index:
                    continue

                actions = self.strategy.apply(df, symbol, row, timestamp, self.open_positions, blocked)

                if blocked:
                    continue

                for action in actions:
                    if action["action"] == "OPEN":
                        self._open_position(
                            symbol=action["symbol"],
                            price=action["price"],
                            sl=action["sl"],
                            timestamp=timestamp,
                            side=action["side"],
                            usdc=action["usdc"]
                        )
                        # On écrit dans la colonne entry_price
                        df.loc[timestamp, "entry_price_*_g_P1"] = action["price"]

                    elif action["action"] == "CLOSE":
                        self._close_position(
                            pos=action["position"],
                            exit_price=action["exit_price"],
                            symbol=action["symbol"],
                            timestamp=timestamp,
                            exit_side=action["exit_side"],
                            reason=action["reason"]
                        )
                        # On écrit dans la colonne exit_price
                        df.loc[timestamp, "exit_price_*_r_P1"] = action["exit_price"]

                    elif action["action"] == "M1":
                        df.loc[timestamp, "entry_price_^_g_P1"] = action["price"]

                    elif action["action"] == "M2":
                        df.loc[timestamp, "entry_price_v_g_P1"] = action["price"]

        # Sauvegarde des df par pièce
        if not execution:
            self._save_results()

    def _open_position(self, symbol, price, sl, timestamp, side, usdc):
        self.open_positions.append({
            "symbol": symbol,
            "entry_price": price,
            "sl": sl,
            "date": timestamp,
            "opened_on": timestamp,
            "side": side,
            "usdc": usdc
        })

        trade_side = "BUY_LONG" if side == "LONG" else "SELL_SHORT"
        self.interface_trade.add_trade(
            price=price,
            side=trade_side,
            asset=symbol,
            timestamp=timestamp,
            amount_usdc=usdc
        )
        self.total_trades += 1

    def _close_position(self, pos, exit_price, symbol, timestamp, exit_side, reason):
        self.interface_trade.add_trade(
            price=exit_price,
            side=exit_side,
            asset=symbol,
            timestamp=timestamp,
            exit_type=reason,
            amount_usdc=pos["usdc"]
        )
        self.closed_count += 1
        self.total_trades += 1
        self.open_positions.remove(pos)

    def _save_results(self):
        os.makedirs("./panda_results", exist_ok=True)
        for symbol, df in self.symbol_dfs.items():
            path = f"./panda_results/{symbol}.panda"
            df.to_pickle(path)
            print(f"✅ Sauvegarde effectuée : {path}")
