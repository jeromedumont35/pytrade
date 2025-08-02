import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timedelta

class CEvaluateROI:
    def __init__(self, initial_usdc=1000.0, trading_fee_rate=0.001):
        self.initial_usdc = initial_usdc
        self.available_usdc = initial_usdc
        self.trading_fee_rate = trading_fee_rate
        self.trades = []
        self.positions = []  # Liste des positions ouvertes
        self.pnl_log = []    # Liste des (timestamp, PNL cumulatif)
        self.latest_prices = {}  # Derniers prix vus pour chaque asset

    def get_available_usdc(self):
        return self.available_usdc

    def add_trade(self, price: float, side: str, asset: str, timestamp, amount_usdc: float = 0.0, exit_type: str = None):
        trade = {
            "price": price,
            "side": side,
            "asset": asset,
            "timestamp": timestamp,
            "amount_usdc": amount_usdc,
            "exit_type": exit_type
        }
        self._process_trade(trade)
        self.trades.append(trade)
        self.latest_prices[asset] = price  # Mémorise le dernier prix

    def _process_trade(self, trade: dict):
        timestamp = trade["timestamp"]
        price = trade["price"]
        side = trade["side"]
        asset = trade["asset"]
        amount_usdc = trade.get("amount_usdc", 0.0)

        if side in ["BUY_LONG", "SELL_SHORT"]:
            # --- Frais à l'ouverture
            fee = amount_usdc * self.trading_fee_rate
            net_amount = amount_usdc - fee
            self.available_usdc -= amount_usdc  # On bloque le montant brut
            self.positions.append({
                "side": side,
                "entry_price": price,
                "usdc": net_amount,
                "timestamp": timestamp,
                "asset": asset,
            })

        elif side in ["SELL_LONG", "BUY_SHORT"]:
            if not self.positions:
                return

            entry = self.positions.pop()
            entry_price = entry["entry_price"]
            entry_usdc = entry["usdc"]
            fee = entry_usdc * self.trading_fee_rate  # Frais à la sortie

            if entry["side"] == "BUY_LONG" and side == "SELL_LONG":
                pnl = entry_usdc * (price / entry_price - 1)
            elif entry["side"] == "SELL_SHORT" and side == "BUY_SHORT":
                pnl = entry_usdc * (entry_price / price - 1)
            else:
                raise ValueError("Mauvais sens entrée/sortie : incohérent.")

            self.available_usdc += entry_usdc + pnl - fee

            total_pnl = self.get_final_balance() - self.initial_usdc
            self.pnl_log.append((timestamp, total_pnl))

    def get_final_balance(self):
        balance = self.available_usdc
        for pos in self.positions:
            asset = pos["asset"]
            entry_price = pos["entry_price"]
            usdc = pos["usdc"]
            side = pos["side"]
            current_price = self.latest_prices.get(asset)

            if current_price is None:
                continue

            if side == "BUY_LONG":
                gain = current_price / entry_price
            elif side == "SELL_SHORT":
                gain = entry_price / current_price
            else:
                continue

            balance += usdc * gain
        return balance

    def get_roi_percentage(self):
        return ((self.get_final_balance() - self.initial_usdc) / self.initial_usdc) * 100

    def plot_combined(self):
        if not self.pnl_log:
            print("Aucune donnée PNL à tracer.")
            return

        pnl_data_sorted = sorted(self.pnl_log, key=lambda x: x[0])
        timestamps, pnl_values = zip(*pnl_data_sorted)

        times_with_initial = [timestamps[0] - timedelta(minutes=1)] + list(timestamps)
        saldo_values = [self.initial_usdc] + [self.initial_usdc + p for p in pnl_values]
        roi_values = [(p / self.initial_usdc) * 100 for p in pnl_values]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        ax1.plot(times_with_initial, saldo_values, marker='o', color='green')
        ax1.set_title("Évolution du solde total (USDC)")
        ax1.set_ylabel("Solde total")
        ax1.grid(True)

        ax2.plot(timestamps, pnl_values, marker='o', linestyle='--', label="PNL (USDC)", color='blue')
        ax2.plot(timestamps, roi_values, marker='s', label="ROI (%)", color='orange')
        ax2.set_title("PNL et ROI")
        ax2.set_xlabel("Temps")
        ax2.set_ylabel("Valeur")
        ax2.grid(True)
        ax2.legend()

        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.show()

    def print_summary(self):
        final_balance = self.get_final_balance()
        total_pnl = final_balance - self.initial_usdc
        roi = self.get_roi_percentage()

        print("📊 Résumé de la performance :")
        print("=" * 40)
        print(f"💰 Capital initial : {self.initial_usdc:.2f} USDC")
        print(f"💼 Solde final     : {final_balance:.2f} USDC (incluant positions ouvertes)")
        print(f"📈 PNL total       : {total_pnl:.2f} USDC")
        print(f"📊 ROI             : {roi:.2f} %")
        print("=" * 40)

        print(f"📌 Nombre total de trades : {len(self.trades)}")
        long_trades = [t for t in self.trades if t["side"] in ("BUY_LONG", "SELL_LONG")]
        short_trades = [t for t in self.trades if t["side"] in ("SELL_SHORT", "BUY_SHORT")]
        print(f"🔹 Positions LONG  : {len(long_trades) // 2}")
        print(f"🔸 Positions SHORT : {len(short_trades) // 2}")

        wins = 0
        losses = 0
        for i in range(1, len(self.pnl_log)):
            if self.pnl_log[i][1] > self.pnl_log[i-1][1]:
                wins += 1
            else:
                losses += 1
        print(f"✅ Trades gagnants : {wins}")
        print(f"❌ Trades perdants : {losses}")
        print("=" * 40)
