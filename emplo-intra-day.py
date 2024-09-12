import ccxt
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
import ta
import time
from datetime import datetime
import matplotlib.pyplot as plt


# Configuración de API para KuCoin con apalancamiento 10x
exchange = ccxt.kucoinfutures({
    'enableRateLimit': True,
    'apiKey': os.getenv("API_KEY_KUC"),
    'secret': os.getenv("API_SECRET_KUC"),
    'password': os.getenv("API_PASS_KUC")
})

symbol = 'XBTUSDTM'
timeframe = '1h'
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

def fetch_order_book_data(symbol):
    ob = exchange.fetch_order_book(symbol, 100)
    bid = ob['bids'][0][0] if len(ob['bids']) > 0 else None
    ask = ob['asks'][0][0] if len(ob['asks']) > 0 else None
    total_bid_volume = sum([b[1] for b in ob['bids']])  # Sumar el volumen total de las órdenes de compra
    total_ask_volume = sum([a[1] for a in ob['asks']])  # Sumar el volumen total de las órdenes de venta
    return ask, bid, total_bid_volume, total_ask_volume

def detect_supply_demand(df, symbol):
    tolerance = 0.005  # 0.5% de tolerancia
    window = 50  # Cambiamos la ventana a 50 períodos para mayor precisión

    # Obtener datos del order book
    ask, bid, total_bid_volume, total_ask_volume = fetch_order_book_data(symbol)

    high_max = df['high'].rolling(window=window).max()
    low_min = df['low'].rolling(window=window).min()

    # Zonas de demanda: cuando el precio toca un mínimo reciente y hay más volumen de compra (bids)
    df['demand_zone'] = np.where(
        (df['low'] <= low_min * (1 + tolerance)) &
        (df['volume'] > df['volume'].rolling(window=window).mean()) &  # Confirmar con el volumen histórico
        (total_bid_volume > total_ask_volume),  # Confirmar con el order book
        1, 0
    )

    # Zonas de oferta: cuando el precio toca un máximo reciente y hay más volumen de venta (asks)
    df['supply_zone'] = np.where(
        (df['high'] >= high_max * (1 - tolerance)) &
        (df['volume'] > df['volume'].rolling(window=window).mean()) &  # Confirmar con el volumen histórico
        (total_ask_volume > total_bid_volume),  # Confirmar con el order book
        1, 0
    )

    # Imprimir detalles sobre las zonas detectadas, separando las zonas de demanda y oferta
    demand_zones_count = df['demand_zone'].sum()
    supply_zones_count = df['supply_zone'].sum()

    print(f"Zonas de Demanda detectadas: {demand_zones_count}")
    print(f"Zonas de Oferta detectadas: {supply_zones_count}")

    if demand_zones_count == 0:
        print("No se detectaron zonas de demanda.")
    if supply_zones_count == 0:
        print("No se detectaron zonas de oferta.")
    
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
    if not supply_zone.empty:  # Asegurarnos de que existan zonas de oferta
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


def trading_strategy():
    global position_active, position_type, entry_price  # Usar las variables globales
    df = fetch_ohlcv(symbol, timeframe, limit)
    df = apply_indicators(df)  # Aplicamos indicadores técnicos (incluyendo la volatilidad)
    df = detect_supply_demand(df, symbol)  # Detección de oferta y demanda

    # Generar el gráfico de zonas de oferta y demanda
    plot_supply_demand(df)


# def trading_strategy():
#     df = fetch_ohlcv(symbol, timeframe, limit)
    
#     # Aplicar indicadores (incluyendo volatilidad) antes de analizar las señales
#     df = apply_indicators(df)  # Aquí ahora usamos la función apply_indicators
    
#     # Aplicamos las tres medias móviles
#     df['MA7'] = ta.trend.sma_indicator(df['close'], 7)
#     df['MA25'] = ta.trend.sma_indicator(df['close'], 25)
#     df['MA99'] = ta.trend.sma_indicator(df['close'], 99)
#     df = detect_supply_demand(df)  # Detección de oferta y demanda

#     last_row = df.iloc[-1]

#     # Verificar que la columna de volatilidad no esté vacía o NaN
#     if pd.isna(last_row['volatility']):
#         print("Volatilidad no disponible, saltando este ciclo.")
#         return

#     # Imprimir valores clave para analizar la lógica
#     print(f"Último cierre: {last_row['close']}, MA7: {last_row['MA7']}, MA25: {last_row['MA25']}, MA99: {last_row['MA99']}")
#     print(f"Zonas: Demanda: {last_row['demand_zone']}, Oferta: {last_row['supply_zone']}")

#     # Parámetros de gestión de riesgo
#     account_balance = 10000  # Ajustar según tu capital
#     risk_percent = 2
#     stop_loss_distance = 0.005  # Distancia de stop-loss más ajustada para movimientos rápidos (0.5%)

#     position_size = calculate_position_size(account_balance, risk_percent, stop_loss_distance, last_row['volatility'])

#     # Configurar apalancamiento 10x
#     #leverage = 10
#     #exchange.futures_set_leverage(leverage, symbol)

#     # Registro de la operación
#     entry_price = last_row['close']
#     print(f"MA7: {last_row['MA7']}, MA25: {last_row['MA25']}, MA99: {last_row['MA99']}")
#     print(f"Zonas: Demanda: {last_row['demand_zone']}, Oferta: {last_row['supply_zone']}")

    
#     if last_row['MA7'] > last_row['MA25'] and df.iloc[-2]['MA7'] <= df.iloc[-2]['MA25'] and last_row['MA7'] > last_row['MA99'] and last_row['MA25'] > last_row['MA99']:
#         print(f"Señal de compra detectada. Tamaño de posición: {position_size}")
#         # Ejecutar orden de compra
#         # exchange.create_order(symbol, 'market', 'buy', position_size)
        
#         # Simular salida después de cierto movimiento
#         exit_price = entry_price * 1.01  # Simulación de ganancia del 1%
#         pnl = calculate_pnl(entry_price, exit_price, position_size, "buy")
#         trade_info = f"Long trade - Entry: {entry_price}, Exit: {exit_price}, PNL: {pnl}"
#         log_trade(trade_info)

#     # Condiciones para venta (solo cruce de medias móviles)
#     elif last_row['MA7'] < last_row['MA25'] and df.iloc[-2]['MA7'] >= df.iloc[-2]['MA25'] and last_row['MA7'] < last_row['MA99'] and last_row['MA25'] < last_row['MA99']:
#         print(f"Señal de venta detectada. Tamaño de posición: {position_size}")
#         # Ejecutar orden de venta
#         # exchange.create_order(symbol, 'market', 'sell', position_size)
        
#         # Simular salida después de cierto movimiento
#         exit_price = entry_price * 0.99  # Simulación de pérdida del 1%
#         pnl = calculate_pnl(entry_price, exit_price, position_size, "sell")
#         trade_info = f"Short trade - Entry: {entry_price}, Exit: {exit_price}, PNL: {pnl}"
#         log_trade(trade_info)

# Estrategia de trading basada solo en zonas de oferta y demanda
# def trading_strategy():
#     df = fetch_ohlcv(symbol, timeframe, limit)
#     df = apply_indicators(df)  # Aplicamos indicadores técnicos (incluyendo la volatilidad)
#     df = detect_supply_demand(df)  # Detección de oferta y demanda

#     last_row = df.iloc[-1]



#     # Parámetros de gestión de riesgo
#     account_balance = 10000  # Ajustar según tu capital
#     risk_percent = 2
#     stop_loss_distance = 0.005  # Distancia de stop-loss más ajustada para movimientos rápidos (0.5%)

#     position_size = calculate_position_size(account_balance, risk_percent, stop_loss_distance, last_row['volatility'])



#     # Registro de la operación
#     entry_price = last_row['close']

#     # Condiciones para compra basada en la zona de demanda
#     if last_row['demand_zone'] == 1:
#         print(f"Señal de compra detectada en la zona de demanda. Tamaño de posición: {position_size}")
#         # Ejecutar orden de compra
#         # exchange.create_order(symbol, 'market', 'buy', position_size)
        
#         # Simular salida después de cierto movimiento (puedes reemplazar esto por condiciones reales)
#         exit_price = entry_price * 1.01  # Simulación de ganancia del 1%
#         pnl = calculate_pnl(entry_price, exit_price, position_size, "buy")
#         trade_info = f"Long trade - Entry: {entry_price}, Exit: {exit_price}, PNL: {pnl}"
#         log_trade(trade_info)
    
#     # Condiciones para venta basada en la zona de oferta
#     elif last_row['supply_zone'] == 1:
#         print(f"Señal de venta detectada en la zona de oferta. Tamaño de posición: {position_size}")
#         # Ejecutar orden de venta
#         # exchange.create_order(symbol, 'market', 'sell', position_size)
        
#         # Simular salida después de cierto movimiento (puedes reemplazar esto por condiciones reales)
#         exit_price = entry_price * 0.99  # Simulación de pérdida del 1%
#         pnl = calculate_pnl(entry_price, exit_price, position_size, "sell")
#         trade_info = f"Short trade - Entry: {entry_price}, Exit: {exit_price}, PNL: {pnl}"
#         log_trade(trade_info)

position_active = False
position_type = None  # 'buy' o 'sell'
entry_price = None  # Guardar el precio de entrada
# Estrategia de trading basada en zonas de oferta y demanda con control en tiempo real
# def trading_strategy():
#     global position_active, position_type, entry_price  # Usar las variables globales
#     df = fetch_ohlcv(symbol, timeframe, limit)
#     df = apply_indicators(df)  # Aplicamos indicadores técnicos (incluyendo la volatilidad)
#     df = detect_supply_demand(df, symbol)  # Detección de oferta y demanda

#     last_row = df.iloc[-1]

#     # Parámetros de gestión de riesgo
#     account_balance = 10000  # Ajustar según tu capital
#     risk_percent = 2
#     stop_loss_distance = 0.005  # Distancia de stop-loss más ajustada para movimientos rápidos (0.5%)
#     position_size = calculate_position_size(account_balance, risk_percent, stop_loss_distance, last_row['volatility'])

#     # Precio actual
#     current_price = last_row['close']

#     # Verificar si hay una posición abierta
#     if position_active:
#         # Calculamos el porcentaje de cambio desde el precio de entrada
#         price_change = ((current_price - entry_price) / entry_price) * 100

#         if position_type == "buy":
#             # Cerrar la posición si sube un 2.5% (ganancia) o baja un 2% (stop-loss)
#             if price_change >= 2.5:
#                 print(f"Ganancia alcanzada: {price_change}%")
#                 close_trade(current_price, "buy")
#             elif price_change <= -2:
#                 print(f"Stop-loss alcanzado: {price_change}%")
#                 close_trade(current_price, "buy")

#         elif position_type == "sell":
#             # Cerrar la posición si baja un 2.5% (ganancia) o sube un 2% (stop-loss)
#             if price_change <= -2.5:
#                 print(f"Ganancia alcanzada: {price_change}%")
#                 close_trade(current_price, "sell")
#             elif price_change >= 2:
#                 print(f"Stop-loss alcanzado: {price_change}%")
#                 close_trade(current_price, "sell")

#     else:
#         # Solo abrir una nueva posición si no hay ninguna activa
#         if last_row['demand_zone'] == 1:
#             print(f"Señal de compra detectada en la zona de demanda. Tamaño de posición: {position_size}")
#             position_active = True
#             position_type = "buy"
#             entry_price = current_price
#             # Ejecutar orden de compra
#             # exchange.create_order(symbol, 'market', 'buy', position_size)
#             log_trade(f"Long trade abierto - Entry: {entry_price}")

#         elif last_row['supply_zone'] == 1:
#             print(f"Señal de venta detectada en la zona de oferta. Tamaño de posición: {position_size}")
#             position_active = True
#             position_type = "sell"
#             entry_price = current_price
#             # Ejecutar orden de venta
#             # exchange.create_order(symbol, 'market', 'sell', position_size)
#             log_trade(f"Short trade abierto - Entry: {entry_price}")

#     # Generar el gráfico de zonas de oferta y demanda
#     plot_supply_demand(df)

# Función para cerrar la operación y calcular el PNL
def close_trade(current_price, trade_type):
    global position_active, entry_price, position_type
    position_active = False
    position_type = None

    # Calcular el PNL basado en el tipo de operación
    pnl = calculate_pnl(entry_price, current_price, position_size, trade_type)
    trade_info = f"Trade cerrado - Tipo: {trade_type}, Entry: {entry_price}, Exit: {current_price}, PNL: {pnl}"
    log_trade(trade_info)

    # Reiniciar el precio de entrada
    entry_price = None



# Ejecución constante del bot cada 15 minutos
def run_bot():
    while True:
        current_time = datetime.now()
        # Obtener minutos actuales (sin segundos) para verificar si estamos al inicio de una nueva vela de 15m
        #if current_time.minute % 15 == 0:
        print(f"Ejecutando estrategia a las {current_time}")
        trading_strategy()
            # Esperar hasta el próximo intervalo de 15 minutos (para evitar múltiples ejecuciones en el mismo minuto)
        time.sleep(30)  
        #else:
            # Esperar un poco antes de verificar nuevamente
            #time.sleep(5)

# Iniciar el bot
run_bot()