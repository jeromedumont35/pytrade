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

        if self.pattern_name != "CDLMORNINGSTAR":
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

        signal_col = f"{self.pattern_name.lower()}_signal"

        if self.pattern_name == "CDLMORNINGSTAR":
            # Appel de la version personnalisée du Morning Star
            df_resampled[signal_col] = self._detect_custom_morning_star(df_resampled)
        else:
            # Appel TA-Lib pour les autres patterns
            pattern_series = self.talib_func(
                df_resampled["open"],
                df_resampled["high"],
                df_resampled["low"],
                df_resampled["close"]
            )
            df_resampled[signal_col] = pattern_series.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

        # Filtrage basé sur un seuil de variation
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
            ts_end = ts + pd.Timedelta(seconds=pd.Timedelta(self.timeframe).total_seconds() - 60)
            df.loc[ts:ts_end, self.output_col_name] = signal

        return df

    def _detect_custom_morning_star(self, df):
        """
        Morning Star personnalisé :
        - Bougie 1 : baissière
        - Bougie 2 : petite (doji ou toupie)
        - Bougie 3 : haussière, clôture au-dessus du milieu du corps de B1
        - Pas d'exigence de gap
        - La bougie 3 peut englober la bougie 1
        """
        result = pd.Series(0, index=df.index)

        for i in range(2, len(df)):
            o1, c1 = df.iloc[i-2]["open"], df.iloc[i-2]["close"]
            o2, c2 = df.iloc[i-1]["open"], df.iloc[i-1]["close"]
            o3, c3 = df.iloc[i]["open"], df.iloc[i]["close"]

            # Bougie 1 : baissière
            if c1 >= o1:
                continue

            # Bougie 2 : petit corps (indécision)
            body2 = abs(c2 - o2)
            range2 = df.iloc[i-1]["high"] - df.iloc[i-1]["low"]
            if range2 == 0 or body2 / range2 > 0.3:
                continue

            # Bougie 3 : haussière
            if c3 <= o3:
                continue

            # Clôture de la 3e au-dessus du milieu du corps de la 1ʳᵉ
            midpoint_b1 = o1 - abs(o1 - c1) / 2
            if c3 < midpoint_b1:
                continue

            # Pattern détecté
            result.iloc[i] = 1

        return result
