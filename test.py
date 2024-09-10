import ccxt
import time
import threading
import numpy as np
import pandas as pd
from typing import Tuple, List
import logging
from datetime import datetime

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
        self.last_analysis_time = 0
        
        logging.basicConfig(filename=f'trading_bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
                            level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger()

    def fetch_ohlcv(self):
        current_time = int(time.time() * 1000)
        if current_time - self.last_analysis_time < 15 * 60 * 1000:
            return

        ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=100)
        self.candles = [[candle[0], candle[4]] for candle in ohlcv]
        self.price_history = [candle[1] for candle in self.candles]
        self.last_analysis_time = current_time
        self.logger.info(f"OHLCV fetched. Current price: {self.price_history[-1]}")

    def fetch_order_book(self):
        order_book = self.exchange.fetch_order_book(self.symbol)
        asks = order_book['asks'][:5]
        bids = order_book['bids'][:5]
        self.logger.info(f"Order book fetched. Top ask: {asks[0]}, Top bid: {bids[0]}")
        return asks, bids

    def analyze_market_depth(self, asks: list, bids: list) -> Tuple[float, float]:
        asks_volume = sum(ask[1] for ask in asks)
        bids_volume = sum(bid[1] for bid in bids)
        self.logger.info(f"Market depth analyzed. Asks volume: {asks_volume}, Bids volume: {bids_volume}")
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
            time.sleep(60)

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

        # Bollinger Bands (ajustado a 2.5 desvíos estándar)
        std = np.std(prices[-20:])
        upper_bb = sma + (2.5 * std)
        lower_bb = sma - (2.5 * std)

        self.logger.info(f"Indicators calculated. SMA: {sma}, RSI: {rsi}, Lower BB: {lower_bb}, Upper BB: {upper_bb}")
        return sma, rsi, lower_bb, upper_bb

    def calculate_deltas(self) -> Tuple[float, float]:
        if len(self.order_book_history) < 2:
            return 0, 0
        current = self.order_book_history[-1]
        previous = self.order_book_history[-2]
        delta_asks = previous['asks_volume'] - current['asks_volume']
        delta_bids = previous['bids_volume'] - current['bids_volume']
        self.logger.info(f"Deltas calculated. Delta asks: {delta_asks}, Delta bids: {delta_bids}")
        return delta_asks, delta_bids

    def should_enter_trade(self) -> Tuple[bool, str]:
        if len(self.price_history) < 20:
            return False, ''

        delta_asks, delta_bids = self.calculate_deltas()
        sma, rsi, lower_bb, upper_bb = self.calculate_indicators()

        if sma is None:
            return False, ''

        current_price = self.price_history[-1]

        # Confirmar con volumen superior al promedio antes de entrar
        asks_volume_avg = np.mean([item['asks_volume'] for item in self.order_book_history])
        bids_volume_avg = np.mean([item['bids_volume'] for item in self.order_book_history])

        # Condiciones para entrar en largo
        long_condition = (
            delta_bids > delta_asks * 1.5 and
            current_price > sma and
            rsi < 70 and
            current_price < upper_bb and
            bids_volume_avg > asks_volume_avg
        )

        # Condiciones para entrar en corto
        short_condition = (
            delta_asks > delta_bids * 1.5 and
            current_price < sma and
            rsi > 30 and
            current_price > lower_bb and
            asks_volume_avg > bids_volume_avg
        )

        if long_condition:
            self.logger.info("Long trade signal detected")
            return True, 'long'
        elif short_condition:
            self.logger.info("Short trade signal detected")
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

        # Cerrar long si hay cambio bajista fuerte (ajustar el umbral del delta y RSI)
        if self.position['side'] == 'long' and (
            delta_asks > delta_bids * 2.5 or  # Mayor confirmación de venta
            current_price < sma or
            rsi > 75  # RSI ajustado a 75
        ):
            self.logger.info("Close long position signal detected")
            return True, 'Cambio bajista detectado'

        # Cerrar short si hay cambio alcista fuerte
        if self.position['side'] == 'short' and (
            delta_bids > delta_asks * 2.5 or  # Mayor confirmación de compra
            current_price > sma or
            rsi < 25  # RSI ajustado a 25
        ):
            self.logger.info("Close short position signal detected")
            return True, 'Cambio alcista detectado'

        return False, ''

    def calculate_position_size(self) -> float:
        balance = 200  # Balance simulado
        risk_amount = balance * self.risk_per_trade
        price = self.price_history[-1]
        position_size = (risk_amount * self.leverage) / price
        self.logger.info(f"Position size calculated: {position_size}")
        return position_size

    def execute_trade(self, side: str):
        amount = self.calculate_position_size()
        self.logger.info(f"Trade signal: {side.upper()} {amount} {self.symbol} at {self.price_history[-1]}")
        self.position = {
            'side': side,
            'entry_price': self.price_history[-1],
            'amount': amount
        }
        self.set_trailing_stop_loss()

    def set_trailing_stop_loss(self):
        if not self.position:
            return
        
        entry_price = self.position['entry_price']
        side = self.position['side']
        amount = self.position['amount']

        if side == 'long':
            stop_loss_price = entry_price * (1 - self.stop_loss_pct)
        else:  # short
            stop_loss_price = entry_price * (1 + self.stop_loss_pct)

        self.logger.info(f"Trailing Stop Loss set at {stop_loss_price}")

    def close_position(self, reason: str):
        if not self.position:
            return

        side = 'sell' if self.position['side'] == 'long' else 'buy'
        amount = self.position['amount']
        current_price = self.price_history[-1]

        pnl = (current_price - self.position['entry_price']) * amount if side == 'sell' else (self.position['entry_price'] - current_price) * amount
        self.logger.info(f"Position closed: {side.upper()} {amount} {self.symbol} at {current_price}. Reason: {reason}. PnL: {pnl}")
        self.position = None

    def run(self):
        market_data_thread = threading.Thread(target=self.capture_market_data)
        market_data_thread.start()

        while True:
            self.fetch_ohlcv()  # Actualizar datos OHLCV
            
            if self.position:
                should_close, reason = self.should_close_position()
                if should_close:
                    self.close_position(reason)
            else:
                should_trade, side = self.should_enter_trade()
                if should_trade:
                    self.execute_trade(side)
            
            time.sleep(60)  # Verificar cada minuto

# Uso del bot
bot = ImprovedTradingBot("XBTUSDM", leverage=20, stop_loss_pct=0.035, take_profit_pct=0.04, risk_per_trade=0.01)
bot.run()