import ccxt
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np 
from datetime import date, datetime, timezone, tzinfo
import time, schedule


load_dotenv()



# Crear una instancia del intercambio (exchange)
exchange = ccxt.kucoinfutures({
    'enableRateLimit': True,
    'apiKey': os.getenv("API_KEY_KUC"),
    'secret': os.getenv("API_SECRET_KUC"),
    'password': os.getenv("API_PASS_KUC")
})

symbol = 'XBTUSDTM'

def ask_best_trades() :
        #
        #      {
        #          "code": "200000",
        #          "data": [
        #              {
        #                  "sequence": 32114961,
        #                  "side": "buy",
        #                  "size": 39,
        #                  "price": "4001.6500000000",
        #                  "takerOrderId": "61c20742f172110001e0ebe4",
        #                  "makerOrderId": "61c2073fcfc88100010fcb5d",
        #                  "tradeId": "61c2074277a0c473e69029b8",
        #                  "ts": 1640105794099993896   # filled time
        #              }
        #          ]
        #      }
  #ob = exchange.fetch_order_book(symbol)
  trades = exchange.fetch_trades(symbol, 20)
  df = pd.DataFrame(trades, columns=['side', 'size', 'price'])
  #prices = df["price"].value_counts().reset_index(name='count').query('count > 25')['index']
  #result = df.price.value_counts().loc[lambda x: x > 50].reset_index()['index']
  #result = df.price.value_counts().loc[lambda x: x > 15]

  grouped_df = df.groupby(['price', 'side']).size().reset_index(name='count')

  # Filtra los precios que se repiten más de 15 veces 
  result = grouped_df[grouped_df['count'] > 5]

  print(trades)
  



def bot() :
  ask_best_trades()


bot()
  