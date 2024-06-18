import ccxt
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np 
from datetime import date, datetime, timezone, tzinfo
import time, schedule


load_dotenv()

exchange = ccxt.binance({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
})

symbol = 'BTC/USDT'
pos_size = 1
short_window = 12
long_window = 26

# Find data
def data() :
  print("starting data..")

  timeframe = '30m'
  num_bars = 1000
  bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=num_bars)

  df_d = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
  df_d['timestamp'] = pd.to_datetime(df_d['timestamp'], unit='ms')

  #print(df_d)

  return df_d

data = data()
data['SMA12'] = data['close'].rolling(window=short_window, min_periods=1).mean()
data['SMA26'] = data['close'].rolling(window=long_window, min_periods=1).mean()

# crear dataframe de signals
signals = pd.DataFrame(index=data.index)
signals['close'] = data['close']
signals['SMA12'] = data['SMA12']
signals['SMA26'] = data['SMA26']

signals['Signal'] = np.where(signals['SMA12'] < signals['SMA26'], 1.0, -1.0)

signals['Position'] = signals['Signal'].diff()

def backtest(signals, initial_balance=10000):
    balance = initial_balance
    shares = 0
    buy_price = 0  # Precio de compra inicial
    already_bought = False  # Variable para controlar si ya se han comprado acciones

    for i in range(len(signals)):
        if signals['Signal'].iloc[i] == 1.0 and not already_bought:
            # Comprar acciones
            shares = balance / signals['close'].iloc[i]
            buy_price = signals['close'].iloc[i]  # Guardar el precio de compra
            balance = 0
            already_bought = True  # Actualizar el estado de la variable
            print(f"Comprar: {shares:.2f} acciones a {signals['close'].iloc[i]:.2f} USD el {signals.index[i]}")
        elif signals['Signal'].iloc[i] == -1.0 and already_bought:
            # Vender acciones si el precio de venta es mayor o igual al precio de compra
            sell_price = signals['close'].iloc[i]
            if sell_price >= buy_price:
                balance = shares * sell_price
                shares = 0
                already_bought = False  # Actualizar el estado de la variable
                print(f"Vender: {balance:.2f} USD a {signals['close'].iloc[i]:.2f} USD el {signals.index[i]}")
    
    # Valor final del portafolio
    final_balance = balance + shares * signals['close'].iloc[-1]
    return final_balance

# Ejecutar backtest y mostrar resultados
final_balance = backtest(signals)
print(f"Saldo inicial: $10000")
print(f"Saldo final: ${final_balance:.2f}")


