import ccxt
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
import ta
import time
from datetime import datetime
import matplotlib.pyplot as plt

# Cargar las credenciales de la API desde un archivo .env
load_dotenv()

# Configuración de API para KuCoin con apalancamiento 10x
exchange = ccxt.kucoinfutures({
    'enableRateLimit': True,
    'apiKey': os.getenv("API_KEY_KUC"),
    'secret': os.getenv("API_SECRET_KUC"),
    'password': os.getenv("API_PASS_KUC")
})

symbol = 'XBTUSDTM'
timeframe = '1w'
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

# Aplicar indicadores técnicos (si es necesario para análisis adicional)
def apply_indicators(df):
    df['SMA_20'] = ta.trend.sma_indicator(df['close'], 20)
    df['SMA_50'] = ta.trend.sma_indicator(df['close'], 50)
    df['RSI'] = ta.momentum.rsi(df['close'], window=7)  # Ajuste de RSI más sensible
    df['BB_upper'], df['BB_middle'], df['BB_lower'] = ta.volatility.BollingerBands(df['close'], window=14).bollinger_hband(), ta.volatility.BollingerBands(df['close'], window=14).bollinger_mavg(), ta.volatility.BollingerBands(df['close'], window=14).bollinger_lband()
    df['volatility'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=7)  # ATR más sensible para fluctuaciones rápidas
    return df

# Detectar zonas de oferta y demanda basado en precio y volumen
def detect_supply_demand(df):
    tolerance = 0.005  # 0.5% de tolerancia
    window = 50  # Ventana de 50 períodos para mayor precisión

    # Detectar máximos y mínimos recientes
    high_max = df['high'].rolling(window=window).max()
    low_min = df['low'].rolling(window=window).min()

    # Zonas de demanda: cuando el precio toca un mínimo reciente y el volumen es alto
    df['demand_zone'] = np.where(
        (df['low'] <= low_min * (1 + tolerance)) &
        (df['volume'] > df['volume'].rolling(window=window).mean()), 1, 0
    )

    # Zonas de oferta: cuando el precio toca un máximo reciente y el volumen es alto
    df['supply_zone'] = np.where(
        (df['high'] >= high_max * (1 - tolerance)) &
        (df['volume'] > df['volume'].rolling(window=window).mean()), 1, 0
    )

    # Imprimir detalles sobre las zonas detectadas
    print(f"Zonas de Demanda detectadas: {df['demand_zone'].sum()}")
    print(f"Zonas de Oferta detectadas: {df['supply_zone'].sum()}")
    
    return df

# Función para calcular PNL
def calculate_pnl(entry_price, exit_price, position_size, trade_type):
    if trade_type == "buy":
        return (exit_price - entry_price) * position_size
    elif trade_type == "sell":
        return (entry_price - exit_price) * position_size

# Función para graficar zonas de oferta y demanda
def plot_supply_demand(df, title="Zonas de Oferta y Demanda"):
    plt.figure(figsize=(12, 6))

    # Graficar el precio de cierre
    plt.plot(df['timestamp'], df['close'], label='Precio de cierre', color='black', linewidth=1)

    # Resaltar las zonas de demanda
    demand_zone = df[df['demand_zone'] == 1]
    for i, row in demand_zone.iterrows():
        plt.axvspan(row['timestamp'], row['timestamp'], color='green', alpha=0.3, label='Zona de Demanda')

    # Resaltar las zonas de oferta
    supply_zone = df[df['supply_zone'] == 1]
    for i, row in supply_zone.iterrows():
        plt.axvspan(row['timestamp'], row['timestamp'], color='red', alpha=0.3, label='Zona de Oferta')

    # Evitar duplicar leyendas
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys())

    # Etiquetas y título
    plt.xlabel('Tiempo')
    plt.ylabel('Precio')
    plt.title(title)
    plt.legend(loc='upper left')

    # Mostrar el gráfico
    plt.show()

# Estrategia de trading basada en zonas de oferta y demanda
position_active = False
position_type = None
entry_price = 0

def trading_strategy():
    global position_active, position_type, entry_price
    df = fetch_ohlcv(symbol, timeframe, limit)
    df = apply_indicators(df)  # Aplicamos indicadores técnicos (opcional)
    df = detect_supply_demand(df)  # Detección de oferta y demanda

    last_row = df.iloc[-1]

    # Parámetros de gestión de riesgo
    account_balance = 10000  # Ajustar según tu capital
    risk_percent = 2
    stop_loss_distance = 0.02  # Stop Loss del 2%
    take_profit_distance = 0.025  # Take Profit del 2.5%

    if not position_active:
        # Condiciones para abrir una posición de compra
        if last_row['demand_zone'] == 1:
            entry_price = last_row['close']
            position_type = "buy"
            position_active = True
            print(f"Se abre posición de compra a {entry_price}")
            log_trade(f"Compra abierta - Entrada: {entry_price}")
        
        # Condiciones para abrir una posición de venta
        elif last_row['supply_zone'] == 1:
            entry_price = last_row['close']
            position_type = "sell"
            position_active = True
            print(f"Se abre posición de venta a {entry_price}")
            log_trade(f"Venta abierta - Entrada: {entry_price}")
    
    # Gestionar la posición abierta
    if position_active:
        current_price = last_row['close']
        if position_type == "buy":
            # Take profit y Stop loss para posición de compra
            if current_price >= entry_price * (1 + take_profit_distance):
                pnl = calculate_pnl(entry_price, current_price, account_balance, "buy")
                print(f"Take profit alcanzado en {current_price}. PNL: {pnl}")
                log_trade(f"Compra cerrada - Entrada: {entry_price}, Salida: {current_price}, PNL: {pnl}")
                position_active = False
            elif current_price <= entry_price * (1 - stop_loss_distance):
                pnl = calculate_pnl(entry_price, current_price, account_balance, "buy")
                print(f"Stop loss activado en {current_price}. PNL: {pnl}")
                log_trade(f"Compra cerrada - Entrada: {entry_price}, Salida: {current_price}, PNL: {pnl}")
                position_active = False
        elif position_type == "sell":
            # Take profit y Stop loss para posición de venta
            if current_price <= entry_price * (1 - take_profit_distance):
                pnl = calculate_pnl(entry_price, current_price, account_balance, "sell")
                print(f"Take profit alcanzado en {current_price}. PNL: {pnl}")
                log_trade(f"Venta cerrada - Entrada: {entry_price}, Salida: {current_price}, PNL: {pnl}")
                position_active = False
            elif current_price >= entry_price * (1 + stop_loss_distance):
                pnl = calculate_pnl(entry_price, current_price, account_balance, "sell")
                print(f"Stop loss activado en {current_price}. PNL: {pnl}")
                log_trade(f"Venta cerrada - Entrada: {entry_price}, Salida: {current_price}, PNL: {pnl}")
                position_active = False
    
    plot_supply_demand(df)

# Ejecución constante del bot cada 15 minutos
def run_bot():
    while True:
        current_time = datetime.now()
        print(f"Ejecutando estrategia a las {current_time}")
        trading_strategy()
        time.sleep(900)  # Esperar 15 minutos (900 segundos) antes de volver a ejecutar

# Iniciar el bot
run_bot()