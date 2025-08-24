from datetime import datetime, timedelta
import CEvaluateROI
import CInterfaceTrades
import BinanceCandlePlotter
import CTradingAlgo
import CBitgetTrader
import pandas as pd

def load_symbol_data(symbols, start_date="20250101_0101", end_date="20250724_0101", folder="panda"):
    """
    Charge automatiquement les DataFrames .panda pour une liste de symboles.

    Args:
        symbols (list): Liste des symboles (ex: ["BTCUSDC", "ETHUSDC"])
        start_date (str): Date de début au format AAAAMMJJ_HHMM
        end_date (str): Date de fin au format AAAAMMJJ_HHMM
        folder (str): Dossier contenant les fichiers .panda

    Returns:
        list: Liste de tuples (DataFrame, symbole)
    """
    list_data = []
    for sym in symbols:
        filename = f"{folder}/{sym}_{start_date}_{end_date}.panda"
        try:
            df = pd.read_pickle(filename)
            list_data.append((df, sym))
        except FileNotFoundError:
            print(f"⚠️ Fichier introuvable : {filename}")
    return list_data

# Création de l'évaluateur
evaluator = CEvaluateROI.CEvaluateROI(1000,trading_fee_rate=0.000)

l_interface_trade = CInterfaceTrades.CInterfaceTrades(evaluator)
algo = CTradingAlgo.CTradingAlgo(l_interface_trade, risk_per_trade_pct=1,strategy_name="RSI5min30")

# Liste des symboles à analyser
symbols = [
    #"KAITOUSDC",
    #"PENGUUSDC",  # tu peux en commenter certains
    "SHIBUSDC",
    "SOLUSDC",
    #"DOGEUSDC"
]

#symbols = [
#    "KAITOUSDC"]

list_data = load_symbol_data(symbols)

# Lancement de l'algo
algo.run(list_data,execution=False)

evaluator.print_summary()
evaluator.plot_combined()

plotter = BinanceCandlePlotter.BinanceCandlePlotter(symbol="KAITOUSDC")

df_virtual = None
for df, sym in list_data:
    if sym == "KAITOUSDC":
        df_virtual = df
        break

plotter.plot(df_virtual, evaluator=evaluator)

