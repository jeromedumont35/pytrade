import pandas as pd
import numpy as np
from scipy.signal import find_peaks

class CPeaksDetector:
    def __init__(self, df, atr_period=14, factor=0.5, distance=5,
                 max_col="peak_max", min_col="peak_min"):
        """
        Détecteur de pics min/max avec prominence dynamique basée sur l'ATR.
        Les colonnes ajoutées contiennent les valeurs des pics.

        Params
        ------
        df : pd.DataFrame
            DataFrame avec colonnes 'High' et 'Low'
        atr_period : int
            Fenêtre pour le calcul de la volatilité (ATR simplifié = High-Low)
        factor : float
            Multiplicateur appliqué à l'ATR locale pour définir la prominence
        distance : int
            Nombre de bougies minimum entre deux pics
        max_col : str
            Nom de la colonne pour les maxima
        min_col : str
            Nom de la colonne pour les minima
        """
        self.df = df.copy()
        self.atr_period = atr_period
        self.factor = factor
        self.distance = distance
        self.max_col = max_col
        self.min_col = min_col
        self._compute_peaks()

    def _compute_peaks(self):
        df = self.df

        # ATR glissant
        df['atr'] = (df['high'] - df['low']).rolling(self.atr_period).mean()

        highs = df['high'].values
        lows = df['low'].values

        # Détection brute sans filtrage de prominence
        peaks_max, props_max = find_peaks(highs, distance=self.distance, prominence=0)
        peaks_min, props_min = find_peaks(-lows, distance=self.distance, prominence=0)

        # Post-filtrage dynamique selon ATR locale
        filtered_max = [i for i in peaks_max
                        if props_max["prominences"][list(peaks_max).index(i)] >= self.factor * df['atr'].iloc[i]]
        filtered_min = [i for i in peaks_min
                        if props_min["prominences"][list(peaks_min).index(i)] >= self.factor * df['atr'].iloc[i]]

        # Colonnes pour stocker les valeurs des pics
        df[self.max_col] = np.nan
        df[self.min_col] = np.nan

        df.loc[df.index[filtered_max], self.max_col] = df['high'].iloc[filtered_max].values
        df.loc[df.index[filtered_min], self.min_col] = df['low'].iloc[filtered_min].values

        # Supprimer la colonne ATR si tu ne veux pas la garder
        df.drop(columns=['atr'], inplace=True)

        self.df = df

    def get_df(self):
        """Retourne le DataFrame enrichi avec colonnes des valeurs des pics"""
        return self.df
