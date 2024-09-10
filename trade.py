import time
import ccxt
import threading
import os
from dotenv import load_dotenv
import pandas as pd

exchange = ccxt.kucoinfutures({
    'enableRateLimit': True,
    'apiKey': os.getenv("API_KEY_KUC"),
    'secret': os.getenv("API_SECRET_KUC"),
    'password': os.getenv("API_PASS_KUC")
})

symbol = "XBTUSDM"  # Puedes cambiarlo por el símbolo que estés analizando

# Función para obtener los trades usando la API de exchange
def fetch_order_data(symbol, limit=100):
    # Llamada a la API para obtener los últimos trades
    trades = exchange.fetch_trades(symbol, limit)

    # Crear listas para asks (ventas) y bids (compras)
    asks = []
    bids = []

    # Recorrer los trades y acceder a los campos anidados
    for trade in trades:
        # Verifica que 'info' tenga los campos 'price', 'size' y 'side'
        if 'info' in trade:
            trade_info = trade['info']
            if 'price' in trade_info and 'size' in trade_info and 'side' in trade_info:
                price = float(trade_info['price'])
                size = trade_info['size']
                side = trade_info['side']

                # Clasificar en asks o bids según el lado
                if side == 'sell':
                    asks.append((price, size))
                elif side == 'buy':
                    bids.append((price, size))

    return asks, bids

# Función para obtener el mejor precio de compra (long) y venta (short)
def get_best_prices(asks, bids):
    best_ask_price = min([price for price, quantity in asks])
    best_bid_price = max([price for price, quantity in bids])
    return best_ask_price, best_bid_price

# 1. Profundidad del mercado: Análisis de órdenes cercanas al mejor precio
def analyze_market_depth(asks, bids, proximity_range=0.01):
    best_ask_price, best_bid_price = get_best_prices(asks, bids)

    # Filtrar órdenes cercanas a los mejores precios
    asks_near_best = [(price, quantity) for price, quantity in asks if best_ask_price <= price <= best_ask_price * (1 + proximity_range)]
    bids_near_best = [(price, quantity) for price, quantity in bids if best_bid_price * (1 - proximity_range) <= price <= best_bid_price]

    # Calcular los volúmenes de órdenes cercanas
    asks_near_best_volume = sum([quantity for price, quantity in asks_near_best])
    bids_near_best_volume = sum([quantity for price, quantity in bids_near_best])

    print(f"Mejor precio de venta (ask): {best_ask_price}")
    print(f"Mejor precio de compra (bid): {best_bid_price}")
    print(f"Total Ask Volume near Best Ask: {asks_near_best_volume}")
    print(f"Total Bid Volume near Best Bid: {bids_near_best_volume}")

# 2. Análisis temporal: Almacenar snapshots del libro de órdenes a intervalos regulares
order_book_history = []

def capture_order_book_snapshot(asks, bids):
    best_ask_price, best_bid_price = get_best_prices(asks, bids)
    total_asks_quantity = sum([quantity for price, quantity in asks])
    total_bids_quantity = sum([quantity for price, quantity in bids])
    
    # Guardar el snapshot con la marca de tiempo
    order_book_history.append({
        "timestamp": time.time(),
        "total_asks_quantity": total_asks_quantity,
        "total_bids_quantity": total_bids_quantity,
        "best_ask_price": best_ask_price,
        "best_bid_price": best_bid_price
    })

def start_order_book_tracking(interval=300):
    while True:
        asks, bids = fetch_order_data(symbol)
        capture_order_book_snapshot(asks, bids)
        time.sleep(interval)  # Esperar el intervalo antes de la siguiente captura

# Iniciar el tracking en segundo plano (cada 5 minutos)
tracking_thread = threading.Thread(target=start_order_book_tracking)
tracking_thread.start()

# 3. Velocidad de ejecución: Medir la diferencia en los volúmenes entre snapshots
execution_speed_data = []

def measure_execution_speed():
    while True:
        if len(order_book_history) >= 2:
            current_snapshot = order_book_history[-1]
            previous_snapshot = order_book_history[-2]
            
            # Calcular la diferencia en los volúmenes
            delta_asks = previous_snapshot['total_asks_quantity'] - current_snapshot['total_asks_quantity']
            delta_bids = previous_snapshot['total_bids_quantity'] - current_snapshot['total_bids_quantity']
            
            execution_speed_data.append({
                "timestamp": current_snapshot['timestamp'],
                "delta_asks": delta_asks,
                "delta_bids": delta_bids
            })
            print(f"Delta Asks: {delta_asks}, Delta Bids: {delta_bids}")
        
        time.sleep(1)  # Medir cada segundo (ajustable)

# Iniciar la medición de velocidad de ejecución
execution_speed_thread = threading.Thread(target=measure_execution_speed)
execution_speed_thread.start()

# Ejemplo: Ejecución de un análisis de profundidad de mercado
asks, bids = fetch_order_data(symbol)  # Llamada inicial a la API
analyze_market_depth(asks, bids, proximity_range=0.01)  # 1% de proximidad a los mejores precios

# Nota: La captura de snapshots y el análisis de velocidad se ejecutan en segundo plano
