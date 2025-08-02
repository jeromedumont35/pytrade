import os
import pickle
import pandas as pd
import numpy as np
import talib
import CRSICalculator

RAW_DIR = "raw"
PANDA_DIR = "panda"
os.makedirs(PANDA_DIR, exist_ok=True)

def _prepare_dataframe(candles):
    df = pd.DataFrame(candles, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df.set_index("time", inplace=True)
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df[["open", "high", "low", "close", "volume"]]

def _apply_indicators(df):
    df = df.copy()

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Le DataFrame doit avoir un index temporel (datetime).")

    #df = CRSICalculator.RSICalculator(df,period=14,close_times=[(23, 59)],name="rsi_1d_14").get_df()

    df = CRSICalculator.RSICalculator(df, period=14,
                                   close_times=[(3, 59), (7, 59), (11, 59), (15, 59), (19, 59), (23, 59)],
                                   name="rsi_4h_14").get_df()

    close_times_1h = [(h, 59) for h in range(24)]
    df = CRSICalculator.RSICalculator(df, period=14, close_times=close_times_1h, name="rsi_1h_14").get_df()

    # === Calcul close_4h_HA (Heikin Ashi sur 4h glissant) ===
    window = 240  # 4h en minutes

    open_4h = df['open'].rolling(window=window).apply(lambda x: x.iloc[0], raw=False)
    high_4h = df['high'].rolling(window=window).max()
    low_4h = df['low'].rolling(window=window).min()
    close_4h = df['close'].rolling(window=window).apply(lambda x: x.iloc[-1], raw=False)

    df['close_4h_HA'] = (open_4h + high_4h + low_4h + close_4h) / 4

    # === Détection et filtrage des hammers sur bougies 5 minutes ===

    df_5min = df.resample("5min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()

    hammer = talib.CDLHAMMER(df_5min["open"], df_5min["high"], df_5min["low"], df_5min["close"])
    inv_hammer = talib.CDLINVERTEDHAMMER(df_5min["open"], df_5min["high"], df_5min["low"], df_5min["close"])

    df_5min["hammer_signal"] = 0
    df_5min.loc[hammer != 0, "hammer_signal"] = 1
    df_5min.loc[inv_hammer != 0, "hammer_signal"] = -1

    def filter_hammers_by_pct(df_5min, signal_col="hammer_signal", pct=0.5):
        """
        Filtre les hammers selon un seuil en % entre close et low/high.
        pct : float en %, ex: 0.3 = 0.3%
        """
        df = df_5min.copy()
        df["hammer_filtered"] = 0
        seuil = pct / 100.0

        for idx, row in df.iterrows():
            signal = row[signal_col]
            if signal == 1:  # Hammer haussier
                if row["low"] > 0 and (row["close"] - row["low"]) / row["low"] >= seuil:
                    df.at[idx, "hammer_filtered"] = 1
            elif signal == -1:  # Inverted hammer
                if row["close"] > 0 and (row["high"] - row["close"]) / row["close"] >= seuil:
                    df.at[idx, "hammer_filtered"] = -1

        return df["hammer_filtered"]

    df_5min["hammer_filtered"] = filter_hammers_by_pct(df_5min, "hammer_signal", pct=0.3)

    # Remettre dans df 1min la variable jap_hammers_5m : 1, -1 ou 0
    df["jap_hammers_5m"] = 0
    for ts, signal in df_5min["hammer_filtered"].items():
        # Plage de 5 minutes
        df.loc[ts: ts + pd.Timedelta(minutes=4), "jap_hammers_5m"] = signal

    return df


def process_raw_file(filepath):
    print(f"📂 Traitement de : {filepath}")
    with open(filepath, "rb") as f:
        candles = pickle.load(f)

    if not candles:
        print("⚠️ Fichier vide.")
        return

    df = _prepare_dataframe(candles)
    df = _apply_indicators(df)

    base = os.path.basename(filepath).replace(".raw", ".panda")
    panda_path = os.path.join(PANDA_DIR, base)

    with open(panda_path, "wb") as f:
        pickle.dump(df, f)

    print(f"✅ Sauvegardé : {panda_path} ({len(df)} lignes)\n")

if __name__ == "__main__":
    raw_files = [f for f in os.listdir(RAW_DIR) if f.endswith(".raw")]

    if not raw_files:
        print("❌ Aucun fichier .raw trouvé.")
    else:
        for filename in raw_files:
            process_raw_file(os.path.join(RAW_DIR, filename))
