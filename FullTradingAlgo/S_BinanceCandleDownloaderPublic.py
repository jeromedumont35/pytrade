import os
import time
import pickle
import requests
from datetime import datetime, timedelta

class BinanceCandleDownloaderPublic:
    def __init__(self, interval: str = "1m", save_dir: str = "raw"):
        self.interval = interval
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.interval_ms = self._interval_to_milliseconds(interval)

    def _interval_to_milliseconds(self, interval: str):
        unit = interval[-1]
        val = int(interval[:-1])
        if unit == "m":
            return val * 60 * 1000
        elif unit == "h":
            return val * 60 * 60 * 1000
        elif unit == "d":
            return val * 24 * 60 * 60 * 1000
        else:
            raise ValueError("Unsupported interval")

    def _get_filename(self, symbol: str, start_time: datetime, end_time: datetime):
        fmt = "%Y%m%d_%H%M"
        start_str = start_time.strftime(fmt)
        end_str = end_time.strftime(fmt)
        return os.path.join(self.save_dir, f"{symbol}_{start_str}_{end_str}.raw")

    def _get_klines(self, symbol: str, start_time_ms: int, limit: int = 1000):
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": self.interval,
            "limit": limit,
            "startTime": start_time_ms
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erreur API Binance ({symbol}) : {response.status_code} -> {response.text}")
            return []

    def download_and_save(self, symbol: str, start_time: datetime, end_time: datetime):
        symbol = symbol.upper()
        current_time = start_time
        limit = 1000
        all_candles = []

        filename = self._get_filename(symbol, start_time, end_time)
        print(f"\n📥 Téléchargement des bougies {symbol} : {start_time} → {end_time}")
        print(f"📁 Fichier de sauvegarde : {filename}")

        total_minutes = int((end_time - start_time).total_seconds() / 60)
        downloaded_minutes = 0

        while current_time < end_time:
            start_time_ms = int(current_time.timestamp() * 1000)
            candles = self._get_klines(symbol, start_time_ms, limit)

            if not candles:
                print(f"❌ Aucune bougie récupérée pour {symbol}. Arrêt.")
                break

            all_candles.extend(candles)

            last_close = int(candles[-1][6])
            next_time = datetime.fromtimestamp(last_close / 1000.0)
            if next_time <= current_time:
                print("⚠️ Prochaine bougie identique ou antérieure. Stop.")
                break

            # Mise à jour progression
            downloaded_minutes = int((next_time - start_time).total_seconds() / 60)
            percent = min(100, int((downloaded_minutes / total_minutes) * 100))
            print(f"   ➤ {symbol} : {percent:3d}% | Bougies: {len(all_candles)} | Jusqu'à: {next_time}", end="\r")

            current_time = next_time
            time.sleep(0.1)

        print()  # saut de ligne
        if all_candles:
            with open(filename, "wb") as f:
                pickle.dump(all_candles, f)
            print(f"✅ {symbol} : {len(all_candles)} bougies enregistrées.")
        else:
            print(f"⚠️ Aucune donnée à enregistrer pour {symbol}")

# === Exemple d'utilisation ===

if __name__ == "__main__":

    #"BTCUSDC", "ETHUSDC", "BNBUSDC", "XRPUSDC", "ADAUSDC", "DOGEUSDC","SOLUSDC", "DOTUSDC","LTCUSDC",
    # Paramètres
    symbols = [
        "LINKUSDC", "BCHUSDC", "ALGOUSDC", "ATOMUSDC", "VETUSDC", "TRXUSDC", "XLMUSDC",
        "EGLDUSDC", "FILUSDC", "AVAXUSDC", "MATICUSDC", "UNIUSDC", "FTMUSDC", "HBARUSDC", "ICPUSDC",
        "SANDUSDC", "MANAUSDC", "GRTUSDC", "AAVEUSDC", "AXSUSDC", "FTTUSDC", "RUNEUSDC", "NEARUSDC",
        "XEMUSDC", "THETAUSDC", "KSMUSDC", "CRVUSDC", "CHZUSDC", "ZILUSDC", "ENJUSDC", "ZRXUSDC",
        "HOTUSDC", "STXUSDC", "WAVESUSDC", "DASHUSDC", "COMPUSDC", "1INCHUSDC", "YFIUSDC",
        "ANKRUSDC", "QTUMUSDC", "OMGUSDC", "IOSTUSDC", "CELOUSDC", "GALAUSDC", "FLOWUSDC", "ROSEUSDC",
        "ENSUSDC", "BALUSDC", "SKLUSDC", "LRCUSDC", "COTIUSDC", "OCEANUSDC", "KAVAUSDC", "ICXUSDC",
        "MTLUSDC", "STORJUSDC", "XNOUSDC", "TWTUSDC", "NKNUSDC", "SXPUSDC", "SCRTUSDC", "ARUSDC",
        "GLMRUSDC", "CTSIUSDC", "BANDUSDC", "RLCUSDC", "KMDUSDC", "FETUSDC", "ARPAUSDC", "PERPUSDC",
        "DGBUSDC", "CVCUSDC", "AGLDUSDC", "LITUSDC", "RENUSDC", "RSRUSDC", "DENTUSDC",
        "TLMUSDC", "STRAXUSDC", "C98USDC", "VGXUSDC", "BETAUSDC", "ATAUSDC", "SUPERUSDC", "DARUSDC",
        "KDAUSDC", "BAKEUSDC", "FLMUSDC", "BELUSDC", "CTKUSDC", "TOMOUSDC", "SUNUSDC", "NMRUSDC"
    ]

    symbols = ["SHIBUSDC","FARTUSDC"]

    interval = "1m"
    save_dir = "raw"

    # Période à télécharger
    start_time = datetime(2025, 1, 1, 1, 1)
    end_time   = datetime(2025, 7, 24, 1, 1)

    downloader = BinanceCandleDownloaderPublic(interval=interval, save_dir=save_dir)

    for sym in symbols:
        downloader.download_and_save(sym.strip(), start_time, end_time)
