import pandas as pd
import matplotlib.pyplot as plt


class CEvaluateROI:
    def __init__(self, initial_usdc=1000.0, trading_fee_rate=0.001):
        self.initial_usdc = initial_usdc
        self.available_usdc = initial_usdc
        self.trading_fee_rate = trading_fee_rate

        self.trades = []  # Liste brute de tous les ordres (entrée + sortie)
        self.positions = {}  # Positions ouvertes {asset: position_dict}
        self.closed_trades = []  # Positions fermées avec pnl et timestamps
        self.latest_prices = {}  # Derniers prix par actif

    def get_available_usdc(self):
        return self.available_usdc

    def add_trade(self, price, side, asset, timestamp, amount_usdc=0.0, exit_type=None):
        trade = {
            "price": price,
            "side": side,
            "asset": asset,
            "timestamp": timestamp,
            "amount_usdc": amount_usdc,
            "exit_type": exit_type
        }
        self._process_trade(trade)
        self.trades.append(trade)  # conserve la trace brute
        self.latest_prices[asset] = price

    def _process_trade(self, trade):
        side = trade["side"]
        asset = trade["asset"]
        price = trade["price"]
        timestamp = trade["timestamp"]
        amount_usdc = trade.get("amount_usdc", 0.0)

        # Ouverture de position (une seule par actif)
        if side in ["BUY_LONG", "SELL_SHORT"]:
            if asset in self.positions:
                # Position déjà ouverte sur cet actif, on ne peut pas en ouvrir une autre
                print(f"⚠️ Position déjà ouverte sur {asset}, trade ignoré : {side} à {timestamp}")
                return

            fee = amount_usdc * self.trading_fee_rate
            net_amount = amount_usdc - fee

            if self.available_usdc < amount_usdc:
                print(f"⚠️ Pas assez d'USDC disponible pour ouvrir position sur {asset}")
                return

            self.available_usdc -= amount_usdc  # bloque le montant brut

            self.positions[asset] = {
                "side": side,
                "entry_price": price,
                "usdc": net_amount,
                "timestamp": timestamp,
                "asset": asset
            }

        # Fermeture de position
        elif side in ["SELL_LONG", "BUY_SHORT"]:
            pos = self.positions.get(asset)
            if pos is None:
                print(f"⚠️ Aucune position ouverte sur {asset} pour fermer à {timestamp}")
                return

            entry_price = pos["entry_price"]
            entry_usdc = pos["usdc"]
            entry_side = pos["side"]

            fee = entry_usdc * self.trading_fee_rate

            if entry_side == "BUY_LONG" and side == "SELL_LONG":
                pnl = entry_usdc * (price / entry_price - 1)
            elif entry_side == "SELL_SHORT" and side == "BUY_SHORT":
                pnl = entry_usdc * (entry_price / price - 1)
            else:
                print(f"⚠️ Incohérence sens entrée/sortie sur {asset} à {timestamp}")
                return

            self.available_usdc += entry_usdc + pnl - fee
            self.closed_trades.append({
                "asset": asset,
                "side": entry_side,
                "entry_price": entry_price,
                "exit_price": price,
                "entry_time": pos["timestamp"],
                "exit_time": timestamp,
                "usdc": entry_usdc,
                "pnl": pnl,
                "fee": fee,
                "duration": (timestamp - pos["timestamp"]).total_seconds()
            })

            del self.positions[asset]

    def get_final_balance(self):
        balance = self.available_usdc
        for asset, pos in self.positions.items():
            current_price = self.latest_prices.get(asset)
            if current_price is None:
                continue
            entry_price = pos["entry_price"]
            usdc = pos["usdc"]
            side = pos["side"]
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
        if not self.closed_trades:
            print("⚠️ Aucun trade fermé à afficher")
            return
        df = pd.DataFrame(self.closed_trades).sort_values("exit_time")
        df["cum_pnl"] = df["pnl"].cumsum()
        df["capital"] = self.initial_usdc + df["cum_pnl"]

        plt.figure(figsize=(12, 6))
        plt.plot(df["exit_time"], df["cum_pnl"], label="PNL cumulatif", color="orange")
        plt.plot(df["exit_time"], df["capital"], label="Capital", color="blue")
        plt.xlabel("Date")
        plt.ylabel("USDC")
        plt.title("Évolution du capital et PNL cumulatif")
        plt.legend()
        plt.grid(True)
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

        long_trades = [t for t in self.closed_trades if t["side"] == "BUY_LONG"]
        short_trades = [t for t in self.closed_trades if t["side"] == "SELL_SHORT"]
        print(f"🔹 Positions LONG  : {len(long_trades)}")
        print(f"🔸 Positions SHORT : {len(short_trades)}")

        wins = sum(1 for t in self.closed_trades if t["pnl"] > 0)
        losses = sum(1 for t in self.closed_trades if t["pnl"] <= 0)
        print(f"✅ Trades gagnants : {wins}")
        print(f"❌ Trades perdants : {losses}")
        print("=" * 40)

        # Détail par actif
        print("\n📊 Détail par actif")
        print("=" * 40)
        assets = set(t["asset"] for t in self.closed_trades)
        for asset in sorted(assets):
            asset_trades = [t for t in self.closed_trades if t["asset"] == asset]
            longs = sum(1 for t in asset_trades if t["side"] == "BUY_LONG")
            shorts = sum(1 for t in asset_trades if t["side"] == "SELL_SHORT")
            pnl_asset = sum(t["pnl"] for t in asset_trades)
            roi_asset = (pnl_asset / self.initial_usdc) * 100 if self.initial_usdc else 0
            wins_asset = sum(1 for t in asset_trades if t["pnl"] > 0)
            losses_asset = sum(1 for t in asset_trades if t["pnl"] <= 0)
            print(f"🔹 {asset}")
            print(f"   LONGs   : {longs}")
            print(f"   SHORTs  : {shorts}")
            print(f"   PNL     : {pnl_asset:.2f} USDC")
            print(f"   ROI     : {roi_asset:.2f} %")
            print(f"   Gagnants: {wins_asset} | Perdants: {losses_asset}")

