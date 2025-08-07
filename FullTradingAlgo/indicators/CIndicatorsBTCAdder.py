import os
import pickle
import pandas as pd

class CIndicatorsBTCAdder:
    def __init__(self, btc_dir: str):
        self.btc_dir = btc_dir
        self.btc_df = self._load_btc_file()

    def _load_btc_file(self) -> pd.DataFrame:
        # Recherche du fichier BTC*.panda dans le répertoire
        for fname in os.listdir(self.btc_dir):
            if fname.startswith("BTC") and fname.endswith(".panda"):
                path = os.path.join(self.btc_dir, fname)
                with open(path, "rb") as f:
                    df = pickle.load(f)

                if not isinstance(df, pd.DataFrame):
                    raise ValueError(f"Le fichier {fname} n'est pas un DataFrame valide.")
                if not isinstance(df.index, pd.DatetimeIndex):
                    raise ValueError(f"Le DataFrame {fname} doit avoir un index temporel.")
                return df

        raise FileNotFoundError(f"Aucun fichier BTC*.panda trouvé dans {self.btc_dir}")

    def add_columns(self, target_df: pd.DataFrame, columns_to_add: list[str]) -> pd.DataFrame:
        target_df = target_df.copy()

        for col in columns_to_add:
            if col not in self.btc_df.columns:
                raise ValueError(f"Colonne '{col}' non trouvée dans le fichier BTC")

            # Aligner sur les index temporels
            aligned = self.btc_df[col].reindex(target_df.index)
            target_df[f"BTC_{col}"] = aligned

        return target_df
