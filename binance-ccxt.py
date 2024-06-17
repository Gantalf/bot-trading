import ccxt
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np 
from datetime import date, datetime, timezone, tzinfo
import time, schedule


load_dotenv()

# determine the trend with 20 day sma / based off trend 
# buy/sell to open around the 15m sma (20d) - .1% under and .3% over

# Crear una instancia del intercambio (exchange)
exchange = ccxt.binance({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
})

symbol = 'BTC/USDT'
pos_size = 1
params = {
  'timeinForce': 'PostOnly',
}


# ask_bid()[0] = ask, [1] = bid
def ask_bid() :

  ob = exchange.fetch_order_book(symbol)
  #print(ob)

  bid = ob['bids'][0][0]
  ask = ob['asks'][0][0]

  return ask, bid 

# Find daily SMA 20
def daily_sma() :
  print("starting daily_sma...")

  timeframe = '1d'
  num_bars = 100
  bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=num_bars)

  df_d = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
  df_d['timestamp'] = pd.to_datetime(df_d['timestamp'], unit='ms')

  # daily sma -20 day
  df_d['sma20_1d'] = df_d.close.rolling(20).mean()

  # Eliminar filas con NaN en la columna sma20_1d
  df_d = df_d.dropna(subset=['sma20_1d'])
  #print(df_d)

  # determine the trend
  # if bid < the 20 day sma then = BEARISH, if bid > 20 day sma = BULLISH 
  bid = ask_bid()[1]
  
  # if sma > bid = SELL, if sma < bid = BUY
  df_d.loc[df_d['sma20_1d']>bid, 'sig'] = 'SELL'
  df_d.loc[df_d['sma20_1d']<bid, 'sig'] = 'BUY'

  return df_d


# Find 15m SMA 20
def f15_sma() :
  print("starting f15_sma...")

  timeframe = '15m'
  num_bars = 100
  bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=num_bars)

  df_f = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
  df_f['timestamp'] = pd.to_datetime(df_f['timestamp'], unit='ms')
 
  # daily sma - 15m
  df_f['sma20_15m'] = df_f.close.rolling(20).mean()
  # Eliminar filas con NaN en la columna sma20_1d
  df_f = df_f.dropna(subset=['sma20_15m'])
  #print(df_f)

  return df_f


df_d = daily_sma()
# df_f = f15_sma()

# combine the two dataframe
print(df_d)
# print(df_f)

#print(ask_bid())


# get bid and ask 
