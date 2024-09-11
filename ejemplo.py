import ccxt
import pandas as pd
import numpy as np
import ta
from datetime import datetime

# Configuración de API para KuCoin
exchange = ccxt.kucoin({
    'apiKey': 'TU_API_KEY',
    'secret': 'TU_SECRET_KEY',
    'password': 'TU_PASSWORD',
})

symbol = 'BTC/USDT'
timeframe = '1h'
limit = 200  # Más datos para un análisis más profundo

# Función para obtener datos históricos
def fetch_ohlcv(symbol, timeframe, limit):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Aplicar indicadores técnicos avanzados
def apply_indicators(df):
    df['SMA_50'] = ta.trend.sma_indicator(df['close'], 50)
    df['SMA_200'] = ta.trend.sma_indicator(df['close'], 200)
    df['RSI'] = ta.momentum.rsi(df['close'], window=14)
    df['BB_upper'], df['BB_middle'], df['BB_lower'] = ta.volatility.BollingerBands(df['close'], window=20).bollinger_hband(), ta.volatility.BollingerBands(df['close'], window=20).bollinger_mavg(), ta.volatility.BollingerBands(df['close'], window=20).bollinger_lband()
    df['volatility'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
    return df

# Detección avanzada de oferta y demanda
def detect_supply_demand(df):
    high_max = df['high'].rolling(window=50).max()
    low_min = df['low'].rolling(window=50).min()
    
    df['demand_zone'] = np.where(df['low'] <= low_min, 1, 0)
    df['supply_zone'] = np.where(df['high'] >= high_max, 1, 0)
    return df

# Gestión de riesgo y tamaño de posición
def calculate_position_size(account_balance, risk_percent, stop_loss_distance, volatility):
    risk_amount = account_balance * risk_percent / 100
    position_size = risk_amount / (stop_loss_distance * volatility)
    return position_size

# Estrategia de trading
def trading_strategy():
    df = fetch_ohlcv(symbol, timeframe, limit)
    df = apply_indicators(df)
    df = detect_supply_demand(df)

    last_row = df.iloc[-1]
    
    # Parámetros de gestión de riesgo
    account_balance = 10000  # Ejemplo, ajustar según tu capital
    risk_percent = 2
    stop_loss_distance = 0.01  # Distancia típica de stop-loss (1%)
    
    position_size = calculate_position_size(account_balance, risk_percent, stop_loss_distance, last_row['volatility'])
    
    # Condiciones para compra (SMA cruce alcista + zona de demanda)
    if last_row['SMA_50'] > last_row['SMA_200'] and last_row['demand_zone'] == 1 and last_row['RSI'] < 30:
        print(f"Señal de compra detectada. Tamaño de posición: {position_size}")
        # Ejecutar orden de compra
        # exchange.create_order(symbol, 'market', 'buy', position_size)
    
    # Condiciones para venta (SMA cruce bajista + zona de oferta)
    elif last_row['SMA_50'] < last_row['SMA_200'] and last_row['supply_zone'] == 1 and last_row['RSI'] > 70:
        print(f"Señal de venta detectada. Tamaño de posición: {position_size}")
        # Ejecutar orden de venta
        # exchange.create_order(symbol, 'market', 'sell', position_size)
    
    # Trailing Stop (para proteger ganancias)
    trailing_stop_distance = last_row['volatility'] * 2  # Ajuste basado en la volatilidad
    print(f"Trailing stop establecido a {trailing_stop_distance}")

# Ejecutar estrategia
trading_strategy()
