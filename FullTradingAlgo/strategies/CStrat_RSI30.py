import pandas as pd

class CStrat_RSI30:
    def __init__(self, interface_trade, risk_per_trade_pct: float = 0.1, stop_loss_ratio: float = 0.98):
        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_ratio = stop_loss_ratio

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
