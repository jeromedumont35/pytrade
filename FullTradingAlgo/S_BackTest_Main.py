from datetime import datetime, timedelta
import CEvaluateROI
import CInterfaceTrades
import BinanceCandlePlotter
import CTradingAlgo
import CBitgetTrader
import pandas as pd

# Création de l'évaluateur
evaluator = CEvaluateROI.CEvaluateROI(1000,trading_fee_rate=0.000)

# Chargement des paires à analyser.
df_KAITO = pd.read_pickle("panda/KAITOUSDC_20250101_0101_20250724_0101.panda")
df_VIRTUAL = pd.read_pickle("panda/VIRTUALUSDC_20250101_0101_20250724_0101.panda")
#df_PENGU = pd.read_pickle("panda/PENGUUSDC_20250101_0101_20250724_0101.panda")
df_SHIBUSDC = pd.read_pickle("panda/SHIBUSDC_20250101_0101_20250724_0101.panda")
df_LTCUSDC = pd.read_pickle("panda/LTCUSDC_20250101_0101_20250724_0101.panda")

l_interface_trade = CInterfaceTrades.CInterfaceTrades(evaluator)
algo = CTradingAlgo.CTradingAlgo(l_interface_trade, risk_per_trade_pct=1,strategy_name="RSI5min30")

algo.run([(df_VIRTUAL, "VIRTUALUSDC"),(df_KAITO,"KAITUSDC"),(df_SHIBUSDC,"SHIBUSDC"),(df_LTCUSDC,"LTCUSDC")])

evaluator.print_summary()
evaluator.plot_combined()

plotter = BinanceCandlePlotter.BinanceCandlePlotter(symbol="VIRTUALUSDC")
plotter.plot(df_VIRTUAL, evaluator=evaluator)