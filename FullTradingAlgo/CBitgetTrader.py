import ccxt
import time
import json
import hmac
import hashlib
import requests

class BitgetTrader:
    def __init__(self, api_key: str, api_secret: str, password: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = password
        self.positions = []  # Liste des positions ouvertes
        self.client = ccxt.bitget({
            'apiKey': api_key,
            'secret': api_secret,
            'password': password,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
            }
        })

        try:
            balance = self.client.fetch_balance()
            print("✅ Connexion à Bitget réussie. Solde disponible (USDT):", balance['total'].get('USDT', 'N/A'))
        except Exception as e:
            raise ConnectionError(f"Échec de la connexion à Bitget : {e}")

    def _usdt_to_amount(self, symbol: str, usdt_amount: float, price=None) -> float:
        if price is None:
            ticker = self.client.fetch_ticker(symbol)
            price = ticker['last']
        amount = usdt_amount / price
        return round(amount, 6)

    def place_order(self, symbol: str, side: str, usdt_amount: float, price=None):
        side_map = {
            "BUY_LONG": "buy",
            "SELL_SHORT": "sell",
        }
        if side not in side_map:
            raise ValueError(f"Type d'ordre non supporté : {side}")

        order_side = side_map[side]
        order_type = "market" if price is None else "limit"
        amount = self._usdt_to_amount(symbol, usdt_amount, price)

        params = {
            "reduceOnly": False,
            "positionMode": "single",
            "positionSide": "open",
        }

        try:
            order = self.client.create_order(
                symbol="SHIB/USDT:USDT",
                type=order_type,
                side=order_side,
                amount=amount,
                price=price if price else None,
                params=params
            )
            print(f"✅ Ordre placé: {order['id']} ({side} sur {symbol})")
            return order
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi de l'ordre {side} sur {symbol} : {e}")
            return None

    def close_position(self, symbol: str, side: str, usdt_amount: float, price=None):
        side_map = {
            "BUY_LONG": "sell",
            "SELL_SHORT": "buy",
        }
        if side not in side_map:
            raise ValueError(f"Type d'ordre non supporté : {side}")

        order_side = side_map[side]
        order_type = "market" if price is None else "limit"
        amount = self._usdt_to_amount(symbol, usdt_amount, price)

        params = {
            "reduceOnly": True,
            "positionMode": "single",
            "positionSide": "close",
        }

        try:
            order = self.client.create_order(
                symbol=symbol,
                type=order_type,
                side=order_side,
                amount=amount,
                price=price if price else None,
                params=params
            )
            print(f"✅ Position fermée: {order['id']} (fermeture {side} sur {symbol})")
            return order
        except Exception as e:
            print(f"❌ Erreur lors de la fermeture {side} sur {symbol} : {e}")
            return None

    def get_available_usdc(self):
        try:
            balance = self.client.fetch_balance()
            usdc_balance = balance['free'].get('USDT')  # USDC n'est pas utilisé en marge sur Bitget, c'est USDT
            if usdc_balance is None:
                print("⚠️ Solde USDT non trouvé dans le compte swap.")
            else:
                print(f"💰 Solde disponible (USDT) sur compte futures : {usdc_balance:.2f}")
            return usdc_balance
        except Exception as e:
            print(f"❌ Erreur lors de la récupération du solde USDT : {e}")
            return None

    def add_trade(self, price: float, side: str, asset: str, timestamp, amount_usdc: float = 0.0, exit_type: str = None):
        trade = {
            "price": price,
            "side": side,
            "asset": asset,
            "timestamp": timestamp,
            "amount_usdc": amount_usdc,
            "exit_type": exit_type
        }
        self._process_trade(trade)
        #self.trades.append(trade)

    def _process_trade(self, trade: dict):
        timestamp = trade["timestamp"]
        price = trade["price"]
        side = trade["side"]
        asset = trade["asset"]
        amount_usdt = trade.get("amount_usdc", 0.0)

        if side in ["BUY_LONG", "SELL_SHORT"]:

            l_order = self.place_order(asset, side, amount_usdt)
            # Entrée en position
            if l_order and l_order.get("status") in ["closed", "filled"]:
                # print("✅ Ordre exécuté immédiatement.")
                self.positions.append({
                "side": side,
                "entry_price": price,
                "usdc": amount_usdt,
                "timestamp": timestamp,
                "asset": asset,
                })

        elif side in ["SELL_LONG", "BUY_SHORT"]:
            # Sortie de position
            if not self.positions:
                return

            entry = self.positions.pop()
            usdc = entry["usdc"]

            l_order = self.close_position(asset, side, usdc)
            # Fermée position
            if l_order and l_order.get("status") in ["closed", "filled"]:
                print("✅ Position fermée immédiatement.")
            else:
                self.positions.append(entry)
