import time
from datetime import datetime, timedelta, timezone
import CBinanceDataFetcher
import CTradingAlgo
import pandas as pd
from strategies.CStrat_RSI5min30 import CStrat_RSI5min30

def display_last_indicators_with_state(symbol_dfs: dict, original_cols: list, algo: CTradingAlgo):
    """
    Affiche un tableau des dernières valeurs d'indicateurs pour chaque symbole,
    avec la colonne 'State' après le symbole.
    Ne montre que les colonnes qui contiennent au moins une valeur non-NaN.
    """
    states = algo.get_symbol_states()
    rows = []
    for sym, df in symbol_dfs.items():
        last_row = df.tail(1)
        new_cols = [c for c in df.columns if c not in original_cols]
        filtered_cols = [col for col in new_cols if not last_row[col].isna().all()]
        row_data = {"Symbol": sym, "State": states.get(sym, "UNKNOWN")}
        for col in filtered_cols:
            row_data[col] = last_row.iloc[0][col]
        rows.append(row_data)
    df_display = pd.DataFrame(rows)
    print("\n📊 Dernière bougie avec indicateurs appliqués et état :")
    print(df_display.to_string(index=False))

def align_df_to_new(df_sym: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    """
    Supprime dans df_sym toutes les colonnes qui n'existent pas dans df_new.
    Retourne un DataFrame allégé qui a les mêmes colonnes que df_new.
    """
    common_cols = [c for c in df_sym.columns if c in df_new.columns]
    return df_sym[common_cols]

def fill_missing_gaps(df_sym, df_new, sym):
    """
    Complète les gaps temporels entre df_sym et df_new en générant des bougies fictives.
    """
    if not df_sym.empty:
        last_time = df_sym.index[-1]
        new_time = df_new.index[-1]
        expected_time = last_time + timedelta(minutes=1)
        if expected_time < new_time:
            print(f"⚠️ Gap détecté pour {sym}: {expected_time} -> {new_time}")
            n_missing = int((new_time - expected_time).total_seconds() / 60)
            for i in range(n_missing):
                missing_time = expected_time + timedelta(minutes=i)
                missing_row = df_sym.iloc[[-1]].copy()
                missing_row.index = [missing_time]
                df_sym = pd.concat([df_sym, missing_row])
    return df_sym

def update_symbol_df(df_sym, df_new, sym):
    """
    Met à jour le DataFrame du symbole avec la nouvelle bougie, gère les gaps, indicateurs et nettoie les doublons.
    """
    df_sym = align_df_to_new(df_sym, df_new)
    df_sym = fill_missing_gaps(df_sym, df_new, sym)
    dups = df_sym.index[df_sym.index.duplicated()]
    if not dups.empty:
        print(f"⚠️ Doublons détectés dans df_sym: {dups}")
    df_sym = pd.concat([df_sym.iloc[1:], df_new])
    # Nettoyage des doublons et tri (optionnel)
    # df_sym = df_sym[~df_sym.index.duplicated(keep='last')]
    # df_sym = df_sym.sort_index()
    return df_sym

def main():
    # === PARAMÈTRES ===
    symbols = ["SHIBUSDC", "SOLUSDC"]
    interval = "1m"
    days = 5

    # === INITIALISATION ===
    fetcher = CBinanceDataFetcher.BinanceDataFetcher()
    interface_trade = None  # ⚡ Remplacer par ton interface trade réelle
    algo = CTradingAlgo.CTradingAlgo(l_interface_trade=interface_trade, strategy_name="RSI5min30")

    # === 1. Téléchargement et simulation historique ===
    print("📥 Téléchargement de l’historique...")
    df_hist = fetcher.get_historical_klines(symbols, interval=interval, days=days)

    # Préparation des DataFrames par symbole
    symbol_dfs = {}
    for sym in symbols:
        df_sym = df_hist[df_hist["symbol"] == sym].drop(columns=["symbol"])
        df_sym = algo.strategy.apply_indicators(df_sym, is_btc_file=(sym == "BTCUSDC"))
        symbol_dfs[sym] = df_sym

    list_data_hist = [(df, sym) for sym, df in symbol_dfs.items()]
    print("⚡ Exécution de la simulation historique...")
    algo.run(list_data_hist, execution=True)

    print("🔄 Passage en mode production (temps réel)...")

    original_cols = {sym: df.columns.tolist() for sym, df in symbol_dfs.items()}

    while True:
        now = datetime.now(timezone.utc)
        if now.second == 0:
            print(f"\n⏰ Nouvelle minute détectée : {now}")
            time.sleep(5)  # Laisser Binance publier la bougie

            df_last = fetcher.get_last_complete_kline(symbols, interval=interval)
            if df_last.empty:
                print("⚠️ Pas de nouvelle bougie dispo (retard API ?).")
                time.sleep(1)
                continue

            list_data_last = []
            for sym in symbols:
                df_sym = symbol_dfs[sym]
                df_new = df_last[df_last["symbol"] == sym].drop(columns=["symbol"])
                df_sym = update_symbol_df(df_sym, df_new, sym)
                orig_cols = original_cols[sym]
                df_sym = algo.strategy.apply_indicators(df_sym, is_btc_file=(sym == "BTCUSDC"))
                symbol_dfs[sym] = df_sym
                df_last_with_ind = df_sym.tail(1)
                list_data_last.append((df_last_with_ind, sym))

            algo.run(list_data_last, execution=True)
            # Utilisation de la dernière version des colonnes originales
            display_last_indicators_with_state(symbol_dfs, orig_cols, algo)
            time.sleep(1)
        time.sleep(0.5)

if __name__ == "__main__":
    main()
