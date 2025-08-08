import numpy as np
import pandas as pd
from scipy import stats

class CTrendBreakDetector:
    def __init__(self):
        pass

    def _compute_prediction_interval(self, x, x_point, se, t_val, Sxx, mean_x, window_size):
        margin = t_val * se * np.sqrt(
            1 + 1 / window_size + ((x_point - mean_x) ** 2) / Sxx
        )
        return margin

    def detect_breaks(
        self,
        df: pd.DataFrame,
        window: int = 20,
        alpha: float = 0.05,
        signal_col_name: str = "break_signal",
    ) -> pd.DataFrame:
        """
        Ajoute une colonne nommée `signal_col_name` au DataFrame avec les signaux :
        - +1 : rupture haussière
        - -1 : rupture baissière
        - 0  : aucun signal
        - np.nan : fenêtre non clean

        Args:
            df (pd.DataFrame): DataFrame avec colonnes 'high' et 'low'.
            window (int): taille de la fenêtre pour la régression.
            alpha (float): seuil de confiance (ex. 0.05 pour 95%).
            signal_col_name (str): nom de la colonne à créer.

        Returns:
            pd.DataFrame: copie du DataFrame avec la colonne ajoutée.
        """
        highs = df["high"].values
        lows = df["low"].values
        avg_price = (highs + lows) / 2
        n = len(df)

        results = [np.nan] * n  # Initialisé à nan par défaut

        for i in range(window, n):
            x_window = np.arange(i - window, i)
            y_window = avg_price[i - window:i]

            # Régression linéaire
            slope, intercept, _, _, _ = stats.linregress(x_window, y_window)
            y_fit = intercept + slope * x_window
            residuals = y_window - y_fit
            se = np.std(residuals, ddof=2)

            t_val = stats.t.ppf(1 - alpha / 2, df=window - 2)
            mean_x = np.mean(x_window)
            Sxx = np.sum((x_window - mean_x) ** 2)

            # Vérifier que tous les points de la fenêtre sont dans leur IC prédictif
            clean_window = True
            for j in range(window):
                xj = x_window[j]
                y_pred_j = intercept + slope * xj
                margin_j = self._compute_prediction_interval(
                    x_window, xj, se, t_val, Sxx, mean_x, window
                )
                lower_j = y_pred_j - margin_j
                upper_j = y_pred_j + margin_j
                if y_window[j] < lower_j or y_window[j] > upper_j:
                    clean_window = False
                    break

            if not clean_window:
                results[i] = np.nan
                continue

            # Tester la dernière bougie
            x_i = i
            y_pred_i = intercept + slope * x_i
            margin_i = self._compute_prediction_interval(
                x_window, x_i, se, t_val, Sxx, mean_x, window
            )
            lower_i = y_pred_i - margin_i
            upper_i = y_pred_i + margin_i

            if highs[i] > upper_i:
                results[i] = 1
            elif lows[i] < lower_i:
                results[i] = -1
            else:
                results[i] = 0

        df_result = df.copy()
        df_result[signal_col_name] = results
        return df_result
