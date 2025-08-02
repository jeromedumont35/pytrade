from datetime import datetime, timedelta
import CEvaluateROI
import CInterfaceTrades
import BinanceCandlePlotter
import CTradingAlgo
import CBitgetTrader
import pandas as pd

# import matplotlib.pyplot as plt
#
# load_only = True
#
# # import talib
# # import numpy as np
# #
# # close = np.array([45.34, 46.23, 47.12, 46.87, 47.45, 48.00, 47.80])
# # rsi = talib.RSI(close, timeperiod=4)
# # print(rsi)
#
# downloader = BinanceCandleDownloaderPublic.BinanceCandleDownloaderPublic()
#
# symbol = "BTCUSDC"
# start = datetime(2025, 1, 1, 12, 0)
# end = start + timedelta(minutes=144000) # ~2 jours
#
# if not load_only:
#     downloader.download_and_save(symbol, start, end)
#
# filepath = "binance_data/BTCUSDC_2025-01-01_12-00.bin"
# candles = downloader.load_candles(filepath)
# print(f"{len(candles)} bougies chargées.")
#
plotter = BinanceCandlePlotter.BinanceCandlePlotter(symbol="SHIBUSDC")
# plotter.plot(
#     raw_candles=candles,
#     start_date="2025-01-15 10:00",
#     end_date="2025-01-15 12:00"
# )

# Création de l'évaluateur


evaluator = CEvaluateROI.CEvaluateROI(1000,trading_fee_rate=0)
#algo = CTradingAlgo.CTradingAlgo("KAITOUSDC", evaluator, initial_balance=1000, risk_per_trade_pct=1, strategy_name="new")
#df_KAITO = pd.read_pickle("panda/KAITOUSDC_20250101_0101_20250724_0101.panda")
#df_VIRTUAL = pd.read_pickle("panda/VIRTUALUSDC_20250101_0101_20250724_0101.panda")
#df_PENGU = pd.read_pickle("panda/PENGUUSDC_20250101_0101_20250724_0101.panda")
df_SHIBUSDC = pd.read_pickle("panda/SHIBUSDC_20250101_0101_20250724_0101.panda")

l_interface_trade = CInterfaceTrades.CInterfaceTrades(evaluator)
algo = CTradingAlgo.CTradingAlgo(l_interface_trade, risk_per_trade_pct=1,strategy_name="4h_HA")

algo.run([(df_SHIBUSDC, "SHIBUSDC")])
#algo.run([(df_PENGU, "PENGUUSDC")])



base_time = datetime(2025, 7, 20, 9, 0)

# Achats BTC
# evaluator.add_trade(59000, "achat", 2000, "BTC", base_time + timedelta(minutes=0))
# evaluator.add_trade(59500, "achat", 1000, "BTC", base_time + timedelta(minutes=5))

# Vente TP (take profit)
# evaluator.add_trade(61000, "vente", 1500, "BTC", base_time + timedelta(minutes=10), exit_type="TP")

# Vente SL (stop loss)
# evaluator.add_trade(58000, "vente", 1000, "BTC", base_time + timedelta(minutes=15), exit_type="SL")

# Vente classique (sans SL/TP)
#evaluator.add_trade(60000, "vente", 500, "BTC", base_time + timedelta(minutes=20), exit_type="TP")

evaluator.print_summary()
evaluator.plot_combined()

plotter.plot(df_SHIBUSDC, evaluator=evaluator)