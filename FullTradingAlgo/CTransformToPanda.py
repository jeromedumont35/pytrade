import os
import pickle
import pandas as pd
import numpy as np
import talib
import CRSICalculator
import CJapanesePatternDetector

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

    detector = CJapanesePatternDetector.CJapanesePatternDetector(
        pattern_name="CDLHAMMER",
        timeframe="5min",
        pct_threshold=0.3,
        output_col_name="jap_hammer_5m_V2"
    )
    df = detector.detect_and_filter(df)

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
