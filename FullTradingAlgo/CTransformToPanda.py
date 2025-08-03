# CTransformToPanda.py

import os
import pickle
import pandas as pd

class CTransformToPanda:
    def __init__(self, raw_dir="raw", panda_dir="panda"):
        self.raw_dir = raw_dir
        self.panda_dir = panda_dir
        os.makedirs(self.panda_dir, exist_ok=True)

    def _prepare_dataframe(self, candles):
        df = pd.DataFrame(candles, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("time", inplace=True)
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df[["open", "high", "low", "close", "volume"]]

    def process_all(self, apply_indicators_func):
        raw_files = [f for f in os.listdir(self.raw_dir) if f.endswith(".raw")]
        if not raw_files:
            print("❌ Aucun fichier .raw trouvé.")
            return

        for filename in raw_files:
            filepath = os.path.join(self.raw_dir, filename)
            print(f"📂 Traitement de : {filepath}")
            with open(filepath, "rb") as f:
                candles = pickle.load(f)

            if not candles:
                print("⚠️ Fichier vide.")
                continue

            df = self._prepare_dataframe(candles)
            df = apply_indicators_func(df,"BTC" in filename)

            base = os.path.basename(filepath).replace(".raw", ".panda")
            panda_path = os.path.join(self.panda_dir, base)

            with open(panda_path, "wb") as f:
                pickle.dump(df, f)

            print(f"✅ Sauvegardé : {panda_path} ({len(df)} lignes)\n")
