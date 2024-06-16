import yfinance as yf
import pandas as pd
import numpy as np

# Descargar datos históricos de precios
data = yf.download('YPF', start='2023-01-01', end='2024-06-01')
print(len(data))

# Calcular las medias móviles simples (SMA)
short_window = 12
long_window = 26

data['SMA12'] = data['Close'].rolling(window=short_window, min_periods=1).mean()
data['SMA26'] = data['Close'].rolling(window=long_window, min_periods=1).mean()

# Crear DataFrame de señales
signals = pd.DataFrame(index=data.index)
signals['Close'] = data['Close']
signals['SMA12'] = data['SMA12']
signals['SMA26'] = data['SMA26']

# Generar señales de compra/venta basadas en el cruce de medias móviles
signals['Signal'] = np.where(signals['SMA12'] < signals['SMA26'], 1.0, -1.0)

# Generar posiciones basadas en las señales
signals['Position'] = signals['Signal'].diff()

def backtest(signals, initial_balance=10000):
    balance = initial_balance
    shares = 0
    buy_price = 0  # Precio de compra inicial
    already_bought = False  # Variable para controlar si ya se han comprado acciones

    for i in range(len(signals)):
        if signals['Signal'].iloc[i] == 1.0 and not already_bought:
            # Comprar acciones
            shares = balance / signals['Close'].iloc[i]
            buy_price = signals['Close'].iloc[i]  # Guardar el precio de compra
            balance = 0
            already_bought = True  # Actualizar el estado de la variable
            print(f"Comprar: {shares:.2f} acciones a {signals['Close'].iloc[i]:.2f} USD el {signals.index[i]}")
        elif signals['Signal'].iloc[i] == -1.0 and already_bought:
            # Vender acciones si el precio de venta es mayor o igual al precio de compra
            sell_price = signals['Close'].iloc[i]
            if sell_price >= buy_price:
                balance = shares * sell_price
                shares = 0
                already_bought = False  # Actualizar el estado de la variable
                print(f"Vender: {balance:.2f} USD a {signals['Close'].iloc[i]:.2f} USD el {signals.index[i]}")
    
    # Valor final del portafolio
    final_balance = balance + shares * signals['Close'].iloc[-1]
    return final_balance

# Ejecutar backtest y mostrar resultados
final_balance = backtest(signals)
print(f"Saldo inicial: $10000")
print(f"Saldo final: ${final_balance:.2f}")
