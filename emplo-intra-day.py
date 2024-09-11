import ccxt
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
import ta
import time
from datetime import datetime

# Configuración de API para KuCoin con apalancamiento 10x
exchange = ccxt.kucoinfutures({
    'enableRateLimit': True,
    'apiKey': os.getenv("API_KEY_KUC"),
    'secret': os.getenv("API_SECRET_KUC"),
    'password': os.getenv("API_PASS_KUC")
})

symbol = 'XBTUSDTM'
timeframe = '15m'
limit = 200  # Más datos para un análisis más profundo

# Archivo para los logs
log_file = "trading_logs.txt"

# Función para escribir en el archivo de log
def log_trade(trade_info):
    try:
        with open(log_file, 'a') as f:
            f.write(trade_info + "\n")
        print(f"Registro escrito en el log: {trade_info}")
    except Exception as e:
        print(f"Error al escribir en el log: {e}")

# Función para obtener datos históricos
def fetch_ohlcv(symbol, timeframe, limit):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Aplicar indicadores técnicos optimizados para 15 minutos
def apply_indicators(df):
    df['SMA_20'] = ta.trend.sma_indicator(df['close'], 20)
    df['SMA_50'] = ta.trend.sma_indicator(df['close'], 50)
    df['RSI'] = ta.momentum.rsi(df['close'], window=7)  # Ajuste de RSI más sensible
    df['BB_upper'], df['BB_middle'], df['BB_lower'] = ta.volatility.BollingerBands(df['close'], window=14).bollinger_hband(), ta.volatility.BollingerBands(df['close'], window=14).bollinger_mavg(), ta.volatility.BollingerBands(df['close'], window=14).bollinger_lband()
    df['volatility'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=7)  # ATR más sensible para fluctuaciones rápidas
    return df

# Detección de oferta y demanda adaptada a 15 minutos
def detect_supply_demand(df):
    high_max = df['high'].rolling(window=15).max()  # Ventanas más cortas para reflejar movimientos rápidos
    low_min = df['low'].rolling(window=15).min()
    
    df['demand_zone'] = np.where(df['low'] <= low_min, 1, 0)
    df['supply_zone'] = np.where(df['high'] >= high_max, 1, 0)
    return df

# Gestión de riesgo y tamaño de posición con apalancamiento
def calculate_position_size(account_balance, risk_percent, stop_loss_distance, volatility):
    risk_amount = account_balance * risk_percent / 100
    position_size = risk_amount / (stop_loss_distance * volatility)
    return position_size

# Función para calcular PNL
def calculate_pnl(entry_price, exit_price, position_size, trade_type):
    if trade_type == "buy":
        return (exit_price - entry_price) * position_size
    elif trade_type == "sell":
        return (entry_price - exit_price) * position_size

# Estrategia de trading intradiaria
def trading_strategy():
    print("Ejecutando estrategia de trading...")
    df = fetch_ohlcv(symbol, timeframe, limit)
    print("Datos históricos obtenidos.")
    df = apply_indicators(df)
    print("Indicadores aplicados.")
    df = detect_supply_demand(df)

    last_row = df.iloc[-1]
    
    # Parámetros de gestión de riesgo
    account_balance = 10000  # Ajustar según tu capital
    risk_percent = 2
    stop_loss_distance = 0.005  # Distancia de stop-loss más ajustada para movimientos rápidos (0.5%)
    
    position_size = calculate_position_size(account_balance, risk_percent, stop_loss_distance, last_row['volatility'])
    
    # Configurar apalancamiento 10x
    leverage = 10
    #exchange.futures_set_leverage(leverage, symbol)

    # Registro de la operación
    entry_price = last_row['close']
    
    # Condiciones para compra (SMA cruce alcista + zona de demanda + RSI bajo)
    if last_row['SMA_20'] > last_row['SMA_50'] and last_row['demand_zone'] == 1 and last_row['RSI'] < 30:
        print(f"Señal de compra detectada. Tamaño de posición: {position_size}")
        # Ejecutar orden de compra
        # exchange.create_order(symbol, 'market', 'buy', position_size)
        
        # Simular salida después de cierto movimiento (puedes reemplazar esto por condiciones reales)
        exit_price = entry_price * 1.01  # Simulación de ganancia del 1%
        pnl = calculate_pnl(entry_price, exit_price, position_size, "buy")
        trade_info = f"Long trade - Entry: {entry_price}, Exit: {exit_price}, PNL: {pnl}"
        log_trade(trade_info)
    
    # Condiciones para venta (SMA cruce bajista + zona de oferta + RSI alto)
    elif last_row['SMA_20'] < last_row['SMA_50'] and last_row['supply_zone'] == 1 and last_row['RSI'] > 70:
        print(f"Señal de venta detectada. Tamaño de posición: {position_size}")
        # Ejecutar orden de venta
        # exchange.create_order(symbol, 'market', 'sell', position_size)
        
        # Simular salida después de cierto movimiento (puedes reemplazar esto por condiciones reales)
        exit_price = entry_price * 0.99  # Simulación de pérdida del 1%
        pnl = calculate_pnl(entry_price, exit_price, position_size, "sell")
        trade_info = f"Short trade - Entry: {entry_price}, Exit: {exit_price}, PNL: {pnl}"
        log_trade(trade_info)

# Ejecución constante del bot cada 15 minutos
def run_bot():
    while True:
        current_time = datetime.now()
        # Obtener minutos actuales (sin segundos) para verificar si estamos al inicio de una nueva vela de 15m
        if current_time.minute % 15 == 0:
            print(f"Ejecutando estrategia a las {current_time}")
            trading_strategy()
            # Esperar hasta el próximo intervalo de 15 minutos (para evitar múltiples ejecuciones en el mismo minuto)
            time.sleep(60)  
        else:
            # Esperar un poco antes de verificar nuevamente
            time.sleep(5)

# Iniciar el bot
run_bot()