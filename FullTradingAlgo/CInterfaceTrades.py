import CEvaluateROI
import CBitgetTrader

class CInterfaceTrades:
    def __init__(self, executor):
        self.executor = executor

    def add_trade(self, price: float, side: str, asset: str, timestamp, amount_usdc: float = 0.0, exit_type: str = None):
        self.executor.add_trade(price, side,asset,timestamp, amount_usdc, exit_type)

    def get_available_usdc(self):
        return self.executor.get_available_usdc()