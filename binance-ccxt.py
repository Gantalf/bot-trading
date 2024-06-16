import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

# Crear una instancia del intercambio (exchange)
exchange = ccxt.binance({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
})

# Definir el par de trading (BTC/USDT)
symbol = 'BTC/USDT'

# Obtener el balance de la cuenta
complete_balance = exchange.fetch_balance()
filtered_balance = {key: value for key, value in complete_balance['total'].items() if value != 0}
reference_money = 'USDT'
total_money = 0.0

for money, balance in complete_balance["total"].items():
  if balance > 0 :
    if money != reference_money and money != "ARS":
      precio = exchange.fetch_ticker(f"{money}/{reference_money}")['last']
      print(f"precio {money}/{reference_money}:", precio)
      value_reference_money = balance * precio 
      total_money += value_reference_money
    elif money != "ARS":
      total_money += balance 


# Obtener el precio actual de Bitcoin
ticker = exchange.fetch_ticker(symbol)
btc_price = ticker['last']

# Imprimir información 
print("todas mis criptos", filtered_balance)
print("balance total en USDT", total_money)
print("precio de BTC", btc_price)