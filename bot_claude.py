import ccxt
import time
import threading
import numpy as np
import pandas as pd
from typing import Tuple, List

class ImprovedTradingBot:
    def __init__(self, symbol: str, leverage: int = 20, stop_loss_pct: float = 0.035, take_profit_pct: float = 0.04, risk_per_trade: float = 0.01):
        self.exchange = ccxt.kucoinfutures({
            'enableRateLimit': True,
            'apiKey': 'TU_API_KEY',
            'secret': 'TU_SECRET',
            'password': 'TU_PASSWORD'
        })
        self.symbol = symbol
        self.leverage = leverage
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.risk_per_trade = risk_per_trade
        self.order_book_history = []
        self.position = None
        self.price_history = []
        self.timeframe = '15m'
        self.candles = []

    def fetch_ohlcv(self):
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=100)
        self.candles = [[candle[0], candle[4]] for candle in ohlcv]  # Timestamp y precio de cierre
        self.price_history = [candle[1] for candle in self.candles]

    def fetch_order_book(self):
        order_book = self.exchange.fetch_order_book(self.symbol)
        asks = order_book['asks'][:5]  # Top 5 asks
        bids = order_book['bids'][:5]  # Top 5 bids
        return asks, bids

    def analyze_market_depth(self, asks: list, bids: list) -> Tuple[float, float]:
        asks_volume = sum(ask[1] for ask in asks)
        bids_volume = sum(bid[1] for bid in bids)
        return asks_volume, bids_volume

    def capture_market_data(self):
        while True:
            self.fetch_ohlcv()
            asks, bids = self.fetch_order_book()
            asks_volume, bids_volume = self.analyze_market_depth(asks, bids)
            self.order_book_history.append({
                "timestamp": time.time(),
                "asks_volume": asks_volume,
                "bids_volume": bids_volume
            })
            if len(self.order_book_history) > 10:
                self.order_book_history.pop(0)
            time.sleep(900)  # 15 minutos

    def calculate_indicators(self):
        if len(self.price_history) < 20:
            return None, None, None, None

        prices = np.array(self.price_history)
        
        # SMA
        sma = np.mean(prices[-20:])
        
        # RSI
        delta = np.diff(prices)
        gain = (delta > 0) * delta
        loss = (delta < 0) * -delta
        avg_gain = np.mean(gain[-14:])
        avg_loss = np.mean(loss[-14:])
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        std = np.std(prices[-20:])
        upper_bb = sma + (2 * std)
        lower_bb = sma - (2 * std)

        return sma, rsi, lower_bb, upper_bb

    def calculate_deltas(self) -> Tuple[float, float]:
        if len(self.order_book_history) < 2:
            return 0, 0
        current = self.order_book_history[-1]
        previous = self.order_book_history[-2]
        delta_asks = previous['asks_volume'] - current['asks_volume']
        delta_bids = previous['bids_volume'] - current['bids_volume']
        return delta_asks, delta_bids

    def should_enter_trade(self) -> Tuple[bool, str]:
        if len(self.price_history) < 20:
            return False, ''

        delta_asks, delta_bids = self.calculate_deltas()
        sma, rsi, lower_bb, upper_bb = self.calculate_indicators()
        
        if sma is None:
            return False, ''

        current_price = self.price_history[-1]

        # Condiciones para entrar en largo
        long_condition = (
            delta_bids > delta_asks * 1.5 and
            current_price > sma and
            rsi < 70 and  # No sobrecomprado
            current_price < upper_bb
        )

        # Condiciones para entrar en corto
        short_condition = (
            delta_asks > delta_bids * 1.5 and
            current_price < sma and
            rsi > 30 and  # No sobrevendido
            current_price > lower_bb
        )

        if long_condition:
            return True, 'long'
        elif short_condition:
            return True, 'short'
        return False, ''

    def should_close_position(self) -> Tuple[bool, str]:
        if not self.position:
            return False, ''

        delta_asks, delta_bids = self.calculate_deltas()
        sma, rsi, lower_bb, upper_bb = self.calculate_indicators()
        
        if sma is None:
            return False, ''

        current_price = self.price_history[-1]

        # Cerrar long si hay cambio bajista fuerte
        if self.position['side'] == 'long' and (
            delta_asks > delta_bids * 2 or  # Fuerte presión de venta
            current_price < sma or  # Precio cae por debajo de la SMA
            rsi > 70  # Sobrecomprado
        ):
            return True, 'Cambio bajista detectado'

        # Cerrar short si hay cambio alcista fuerte
        if self.position['side'] == 'short' and (
            delta_bids > delta_asks * 2 or  # Fuerte presión de compra
            current_price > sma or  # Precio sube por encima de la SMA
            rsi < 30  # Sobrevendido
        ):
            return True, 'Cambio alcista detectado'

        return False, ''

    def calculate_position_size(self) -> float:
        balance = self.exchange.fetch_balance()['total']['USDT']
        risk_amount = balance * self.risk_per_trade
        price = self.price_history[-1]
        position_size = (risk_amount * self.leverage) / price
        return position_size

    def execute_trade(self, side: str):
        try:
            self.exchange.set_leverage(self.leverage, self.symbol)
            amount = self.calculate_position_size()
            order = self.exchange.create_market_order(self.symbol, side, amount)
            print(f"Orden ejecutada: {order}")
            self.position = {
                'side': side,
                'entry_price': float(order['price']),
                'amount': amount
            }
            self.set_stop_loss_take_profit()
        except Exception as e:
            print(f"Error al ejecutar la orden: {e}")

    def set_stop_loss_take_profit(self):
        if not self.position:
            return
        
        entry_price = self.position['entry_price']
        side = self.position['side']
        amount = self.position['amount']

        if side == 'long':
            stop_loss_price = entry_price * (1 - self.stop_loss_pct)
            take_profit_price = entry_price * (1 + self.take_profit_pct)
        else:  # short
            stop_loss_price = entry_price * (1 + self.stop_loss_pct)
            take_profit_price = entry_price * (1 - self.take_profit_pct)

        try:
            self.exchange.create_order(self.symbol, 'stop', 'sell' if side == 'long' else 'buy', amount, stop_loss_price)
            self.exchange.create_order(self.symbol, 'take_profit', 'sell' if side == 'long' else 'buy', amount, take_profit_price)
            print(f"Stop Loss establecido en {stop_loss_price}, Take Profit en {take_profit_price}")
        except Exception as e:
            print(f"Error al establecer SL/TP: {e}")

    def close_position(self, reason: str):
        if not self.position:
            return

        try:
            side = 'sell' if self.position['side'] == 'long' else 'buy'
            amount = self.position['amount']
            order = self.exchange.create_market_order(self.symbol, side, amount)
            print(f"Posición cerrada por {reason}: {order}")
            self.position = None
        except Exception as e:
            print(f"Error al cerrar la posición: {e}")

    def run(self):
        market_data_thread = threading.Thread(target=self.capture_market_data)
        market_data_thread.start()

        while True:
            if self.position:
                should_close, reason = self.should_close_position()
                if should_close:
                    self.close_position(reason)
            else:
                should_trade, side = self.should_enter_trade()
                if should_trade:
                    self.execute_trade(side)
            time.sleep(900)  # Verificar cada 15 minutos

# Uso del bot
bot = ImprovedTradingBot("XBTUSDM", leverage=20, stop_loss_pct=0.035, take_profit_pct=0.04, risk_per_trade=0.01)
bot.run()