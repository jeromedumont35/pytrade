import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

class BinanceDataFetcher:
    BASE_URL = "https://api.binance.com/api/v3/klines"

    def __init__(self):
        pass

    def _prepare_dataframe(self, candles):
        """
        Transforme les bougies brutes Binance en DataFrame formaté.
        """
        df = pd.DataFrame(candles, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("time", inplace=True)

        # Conversion en float
        df[["open", "high", "low", "close", "volume"]] = df[
            ["open", "high", "low", "close", "volume"]
        ].astype(float)

        # Moyenne (open, high, low, close)
        df["moy_l_h_e_c"] = (df["open"] + df["close"] + df["high"] + df["low"]) / 4

        return df[["open", "high", "low", "close", "volume", "moy_l_h_e_c"]]

    def _fetch_klines(self, symbol, interval, start_time, end_time):
        """
        Télécharge toutes les bougies pour un symbole entre start_time et end_time
        en gérant la limite API Binance (1000 bougies max par requête).
        """
        url = self.BASE_URL
        limit = 1000
        all_candles = []

        start_ts = int(start_time.timestamp() * 1000)
        end_ts = int(end_time.timestamp() * 1000)

        while True:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": start_ts,
                "endTime": end_ts,
                "limit": limit,
            }

            response = requests.get(url, params=params)
            data = response.json()

            if not isinstance(data, list):
                raise Exception(f"Erreur API Binance : {data}")

            if not data:
                break  # plus de bougies dispo

            all_candles.extend(data)

            # Avancer le start_ts à la dernière bougie récupérée + 1ms
            last_close_time = data[-1][6]  # colonne close_time
            start_ts = last_close_time + 1

            # Si on a atteint ou dépassé end_time → stop
            if start_ts >= end_ts:
                break

        df = self._prepare_dataframe(all_candles)
        df["symbol"] = symbol
        return df

    def get_historical_klines(self, symbols, interval="1m", days=1):
        """
        Récupère les bougies historiques pour une liste de symboles,
        jusqu'à la dernière minute complète.
        """
        # On ne prend que jusqu'à la dernière minute complète
        end_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(second=0, microsecond=0)
        start_time = end_time - timedelta(days=days)

        all_dfs = []
        for sym in symbols:
            df = self._fetch_klines(sym, interval, start_time, end_time)
            all_dfs.append(df)

        return pd.concat(all_dfs)

    def get_last_complete_kline(self, symbols, interval="1m"):
        """
        Récupère uniquement la dernière bougie complète pour une liste de symboles.
        """
        # Dernière minute complète
        end_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(second=0, microsecond=0)
        start_time = end_time - timedelta(minutes=5)  # marge de sécurité

        all_dfs = []
        for sym in symbols:
            df = self._fetch_klines(sym, interval, start_time, end_time)
            if not df.empty:
                all_dfs.append(df.iloc[[-1]])  # dernière bougie complète uniquement

        if all_dfs:
            return pd.concat(all_dfs)
        else:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "moy_l_h_e_c", "symbol"])
