import pandas as pd 
import mplfinance as mpf
import matplotlib.pyplot as plt

class BinanceCandlePlotter:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def plot(self, df: pd.DataFrame, start_date=None, end_date=None, evaluator=None):
        """
        Affiche un graphique à partir d'un DataFrame pandas déjà préparé.

        :param df: DataFrame pandas avec index datetime et colonnes "open", "high", "low", "close", "volume"
        :param start_date: datetime ou str (optionnel)
        :param end_date: datetime ou str (optionnel)
        :param evaluator: instance contenant la liste .trades (optionnel)
        """
        if start_date:
            start_date = pd.to_datetime(start_date)
            df = df[df.index >= start_date]

        if end_date:
            end_date = pd.to_datetime(end_date)
            df = df[df.index <= end_date]

        if df.empty:
            print("Aucune donnée pour la période spécifiée.")
            return

        if evaluator is None:
            # --- Mode candlestick classique ---
            mpf.plot(
                data=df,
                type='candle',
                volume=True,
                style='yahoo',
                title=f'Graphique de bougies - {self.symbol}',
                ylabel='Prix',
                ylabel_lower='Volume',
                figratio=(16, 9),
                figscale=1.2,
                tight_layout=True
            )
        else:
            # --- Mode clôture + trades ---
            plt.figure(figsize=(16, 6))
            plt.plot(df.index, df["close"], label="Clôture", color="blue", linewidth=0.7)

            trades_by_type = {
                "BUY_LONG": {"times": [], "prices": [], "color": "limegreen", "marker": "^", "label": "Achat Long"},
                "SELL_LONG": {"times": [], "prices": [], "color": "darkgreen", "marker": "v", "label": "Vente Long"},
                "BUY_SHORT": {"times": [], "prices": [], "color": "orange", "marker": "^", "label": "Achat Short"},
                "SELL_SHORT": {"times": [], "prices": [], "color": "darkred", "marker": "v", "label": "Vente Short"},
            }

            for trade in evaluator.trades:
                time = pd.to_datetime(trade["timestamp"])
                if time in df.index and trade["side"] in trades_by_type:
                    data = trades_by_type[trade["side"]]
                    data["times"].append(time)
                    data["prices"].append(trade["price"])

            for side, data in trades_by_type.items():
                if data["times"]:
                    plt.scatter(
                        data["times"],
                        data["prices"],
                        marker=data["marker"],
                        color=data["color"],
                        label=data["label"],
                        zorder=5
                    )

            plt.title(f"Prix de clôture avec les trades - {self.symbol}")
            plt.xlabel("Temps")
            plt.ylabel("Prix")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plt.show()
