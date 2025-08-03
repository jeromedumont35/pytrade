import pandas as pd
import talib

class CJapanesePatternDetector:
    def __init__(self, pattern_name, timeframe="5min", pct_threshold=0.3, output_col_name="jap_pattern"):
        """
        :param pattern_name: Nom de la fonction TA-Lib, ex: 'CDLHAMMER', 'CDLINVERTEDHAMMER'
        :param timeframe: Résolution temporelle pour le resampling (ex: '5min', '15min', etc.)
        :param pct_threshold: Seuil en pourcentage pour filtrer (ex: 0.3 pour 0.3%)
        :param output_col_name: Nom de la colonne finale à injecter dans le df initial
        """
        self.pattern_name = pattern_name.upper()
        self.timeframe = timeframe
        self.pct_threshold = pct_threshold / 100.0
        self.output_col_name = output_col_name

        if not hasattr(talib, self.pattern_name):
            raise ValueError(f"Le pattern '{self.pattern_name}' n'existe pas dans TA-Lib.")

        self.talib_func = getattr(talib, self.pattern_name)

    def detect_and_filter(self, df):
        """
        Applique la détection du pattern et filtre selon le seuil.
        Injecte le résultat dans le df original avec la bonne granularité.
        """
        df_resampled = df.resample(self.timeframe).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()

        # Appliquer le pattern
        pattern_series = self.talib_func(
            df_resampled["open"],
            df_resampled["high"],
            df_resampled["low"],
            df_resampled["close"]
        )

        signal_col = f"{self.pattern_name.lower()}_signal"
        df_resampled[signal_col] = pattern_series.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

        # Filtrage personnalisé basé sur variation close vs low/high
        df_resampled["filtered"] = 0
        for idx, row in df_resampled.iterrows():
            signal = row[signal_col]
            if signal == 1:
                if row["low"] > 0 and (row["close"] - row["low"]) / row["low"] >= self.pct_threshold:
                    df_resampled.at[idx, "filtered"] = 1
            elif signal == -1:
                if row["close"] > 0 and (row["high"] - row["close"]) / row["close"] >= self.pct_threshold:
                    df_resampled.at[idx, "filtered"] = -1

        # Injection dans df initial (bougies plus fines)
        df[self.output_col_name] = 0
        for ts, signal in df_resampled["filtered"].items():
            ts_end = ts + pd.Timedelta(pd.Timedelta(self.timeframe).seconds - 60, unit="s")
            df.loc[ts:ts_end, self.output_col_name] = signal

        return df
