import pandas as pd
from tqdm import tqdm


class CTradingAlgo:
    def __init__(self, l_interface_trade, risk_per_trade_pct: float = 0.1, strategy_name: str = "strategy_1"):
        self.interface_trade = l_interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.strategy_name = strategy_name
        self.stop_loss_ratio = 0.98
        self.rsi_tp_long = 65
        self.rsi_tp_short = 40

        self.open_positions = []
        self.closed_count = 0
        self.total_trades = 0

    def run(self, list_data: list):
        merged = []
        for df, symbol in list_data:
            df = df.copy()
            df["symbol"] = symbol
            merged.append(df)
        full_df = pd.concat(merged).sort_index()
        grouped = full_df.groupby(full_df.index)
        total_ticks = len(grouped)

        for timestamp, group in tqdm(grouped, total=total_ticks, desc="🔄 Simulation trading"):
            for _, row in group.iterrows():
                symbol = row["symbol"]
                buy_long_signal = False
                sell_short_signal = False

                df = next(df for df, s in list_data if s == symbol)
                if timestamp not in df.index:
                    continue
                i = df.index.get_loc(timestamp)
                if i == 0:
                    continue
                prev = df.iloc[i - 1]

                # === STRATEGY LOGIC ===
                if self.strategy_name == "short_max":
                    sell_short_signal = row["close"] > 105000

                elif self.strategy_name == "rsi_30":
                    x = 50
                    if i >= x:
                        rsi_window = df["rsi_4h_14"].iloc[i - x:i]
                        current_rsi = row["rsi_4h_14"]
                        if current_rsi > 30 and (rsi_window < 30).all():
                            buy_long_signal = True
                        if current_rsi < 70 and (rsi_window > 70).all():
                            sell_short_signal = True

                elif self.strategy_name == "4h_HA":
                    if i >= 240 * 4:
                        current_close = df["close_4h_HA"].iloc[i]
                        past = [df["close_4h_HA"].iloc[i - 240 * j] for j in range(1, 5)]

                        open_pos = next((p for p in self.open_positions if p["symbol"] == symbol), None)
                        can_reverse = True
                        if open_pos:
                            minutes_open = (timestamp - open_pos["opened_on"]).total_seconds() / 60
                            if minutes_open < 60 * 4:  # 240 min = 4h
                                can_reverse = False

                        if can_reverse and open_pos:
                            if open_pos["side"] == "SHORT" and current_close > past[0]:
                                exit_price = row["close"]
                                self._close_position(open_pos, exit_price, symbol, timestamp, "BUY_SHORT", "REVERSAL_HA")
                                continue
                            elif open_pos["side"] == "LONG" and current_close < past[0]:
                                exit_price = row["close"]
                                self._close_position(open_pos, exit_price, symbol, timestamp, "SELL_LONG", "REVERSAL_HA")
                                continue

                        if not open_pos:
                            if current_close > past[0] < past[1] < past[2] < past[3] and row["rsi_4h_14"] < 30:
                                buy_long_signal = True
                            elif current_close < past[0] > past[1] > past[2] > past[3] and row["rsi_4h_14"] > 70:
                                sell_short_signal = True

                else:
                    raise ValueError(f"Stratégie inconnue : {self.strategy_name}")

                # === BUY LONG ===
                if buy_long_signal and self.interface_trade.get_available_usdc() > 10:
                    close = row["close"]
                    sl_price = close * self.stop_loss_ratio
                    montant_trade = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct

                    self._open_position(
                        symbol=symbol,
                        price=close,
                        sl=sl_price,
                        timestamp=timestamp,
                        side="LONG",
                        usdc=montant_trade
                    )
                    continue

                # === SELL SHORT ===
                if sell_short_signal and self.interface_trade.get_available_usdc() > 10:
                    close = row["close"]
                    sl_price = close * (2 - self.stop_loss_ratio)
                    montant_trade = self.interface_trade.get_available_usdc() * self.risk_per_trade_pct

                    self._open_position(
                        symbol=symbol,
                        price=close,
                        sl=sl_price,
                        timestamp=timestamp,
                        side="SHORT",
                        usdc=montant_trade
                    )
                    continue

            # === GESTION POSITIONS OUVERTES ===
            still_open = []
            for pos in self.open_positions:
                if pos["opened_on"] == timestamp:
                    still_open.append(pos)
                    continue

                df = next(df for df, s in list_data if s == pos["symbol"])
                if timestamp not in df.index:
                    still_open.append(pos)
                    continue
                row = df.loc[timestamp]

                sold = False
                exit_price = None
                reason = None

                if pos["side"] == "LONG":
                    if row["low"] <= pos["sl"]:
                        exit_price = pos["sl"]
                        reason = "SL"
                        sold = True
                    elif row["rsi_4h_14"] >= self.rsi_tp_long:
                        exit_price = row["close"]
                        reason = "TP_RSI"
                        sold = True
                elif pos["side"] == "SHORT":
                    if row["high"] >= pos["sl"]:
                        exit_price = pos["sl"]
                        reason = "SL"
                        sold = True
                    elif row["rsi_4h_14"] <= self.rsi_tp_short:
                        exit_price = row["close"]
                        reason = "TP_RSI"
                        sold = True

                if sold:
                    exit_side = "BUY_SHORT" if pos["side"] == "SHORT" else "SELL_LONG"
                    self._close_position(pos, exit_price, pos["symbol"], timestamp, exit_side, reason)
                else:
                    still_open.append(pos)

            self.open_positions = still_open

            # 💬 Affichage de la progression
            #print(f"[{timestamp}] Open: {len(self.open_positions)} / Closed: {self.closed_count} / Capital: {self.interface_trade.get_available_usdc():.2f} USDC", end='\r')

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
