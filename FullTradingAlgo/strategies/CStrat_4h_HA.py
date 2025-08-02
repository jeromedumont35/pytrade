import pandas as pd

class CStrat_4h_HA:
    def __init__(self, interface_trade, risk_per_trade_pct: float = 0.1, stop_loss_ratio: float = 0.98):
        self.interface_trade = interface_trade
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_ratio = stop_loss_ratio

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

        if not open_pos and self.interface_trade.get_available_usdc() > 10:
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
