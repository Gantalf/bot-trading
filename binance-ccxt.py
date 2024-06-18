'''
  built this bot that does the below 
  # determine the trend with 20 day sma / based off trend 
  # buy/sell to open around the 15m sma (20d) - .1% under and .3% over

  based in phemex
'''


import ccxt
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np 
from datetime import date, datetime, timezone, tzinfo
import time, schedule


load_dotenv()



# Crear una instancia del intercambio (exchange)
exchange = ccxt.binance({
    'enableRateLimit': True,
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
})

symbol = 'BTC/USDT'
pos_size = 20
params = {
  'timeinForce': 'PostOnly', # funciona esto en binance? 
}
# params = {
#   'timeInForce': 'GTC', # Cambiado de 'PostOnly' a 'GTC' para compatibilidad con Binance
# }
target = 25



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

  # buy price 1+2 and sell price 1+2 (then later figure out wich i chose)
  # buy/sell to open around the 15m sma (20d) - .1% under and .3% over
  df_f['bp_1'] = df_f['sma20_15m'] * 1.001  # 15m sma .1% under and .3% over
  df_f['bp_2'] = df_f['sma20_15m'] * .997
  df_f['sp_1'] = df_f['sma20_15m'] * .999
  df_f['sp_2'] = df_f['sma20_15m'] * 1.003

  print(df_f)
  return df_f


# Exit 

def open_position() :
  params = {'type': 'swap', 'code': 'USDT'}
  phe_bal = exchange.fetch_balance(params=params)
  open_position = phe_bal['info']['data']['positions']
  #print(open_position)
  openpos_side = open_position[0]['side']
  openpos_size = open_position[0]['size']

  if openpos_side == ('Buy') :
    openpos_bool = True
    is_long = True
  elif openpos_side == ('Sell') :
    openpos_bool = True
    is_long = False
  else:
    openpos_bool = False
    is_long = None

  return open_position, openpos_bool, openpos_size, is_long

def kill_switch() : 

  # gracefully limit close us
  print('starting the kill swithc')

  openposi = open_position()[1] # true or false
  is_long = open_position([3])
  kill_size = open_position([2])

  print(f'******openposi {}, long {is_long}, size {kill_size}')

  while openposi == True :
    print('starting kill swith loop til limit fil')
    
    exchange.cancel_all_orders(symbol)
    openposi = open_position()[1]
    is_long = open_position()[3]
    kill_size = open_position()[2]
    kill_size = int(kill_size)

    ask = ask_bid()[0]
    bid = ask_bid()[1]

    if is_long == False :
      exchange.create_limit_buy_order(symbol, kill_size, bid, params)
      print(f'just made a BUY to CLOSE order of {kill_size} {symbol} at ${bid}')
      print('sleeping for 30 seconds to see if it fills')
      time.sleep(30)
    elif is_long == True:
      exchange.create_limit_sell_order(symbol, kill_size, ask, params) 
      print(f'just made a SELL to CLOSE order of {kill_size} {symbol} at ${ask}')
      print('sleeping for 30 seconds to see if it fills')
      time.sleep(30)
    else:
      print('+++ Something i didnt except in kill swith function')

    openposi = open_position()[1]


# pnl_close() [0] pnl close and [1] in_pos [2] size [3] is_long
def pnl_close() :

  print('checking to see if its time to exit')

  params = ['type': 'swap', 'code'; 'USDT']
  pos_dict = exchange.fetch_positions(params=params)
  print(pos_dict)
  
  # if hit target then close

  # get in position or NA
  pos_dict = pos_dict[0]
  side = pos_dict['side']
  size = pos_dict['contracts']
  entry_price = float(pos_dict['entryPrice'])
  leverage = float(pos_dict['leverage'])

  current_price = ask_bid()[1]

  print(f'side: {side} | entry_price: {entry_price} | lev: {leverage}')

  # short or long

  if side == 'long':
    diff == current_price - entry_price
    is_long = True
  else: 
    diff = entry_price - current_price
    is_long = False

  try:
    perc = round(((diff/entry_price) * leverage), 10)
  except: 
    perc = 0

  print(f'diff {diff} | perc {perc}')

  perc = 100*perc

  print(f'this is uor PNL percentage: {(perc)}%')

  pnl_close = False
  in_pos = False

  if perc > 0 :

    print('we are in a winning position')
    if perc > target :
      print('hit our target of: {target}')
      pnlclose = True
      kill_switch()
    else :
      print('we have not our target yet')
  elif perc < 0 :
    print('we are in a losing position but holding on')
    in_pos = True
  else :
    print('we are not in position')



  return pnl_close, in_pos, size, is_long


def bot(): 
  
  pnl_close()

  df_d = daily_sma() # determines long/short
  df_f = f15_sma()   # provide prices bp_1, bp_2, sp_1, sp_2
  ask = ask_bid()[0]
  bid = ask_bid()[1]  


  # make open order 
  # long or short?
  sig =  df_d.iloc[-1]['sig']
  
  open_size = pos_size / 2

  # Only run if not in position
  in_pos = pnl_close()[1]
  if in_pos == False:
    if sig == 'BUY':
      print('making a opening order as a buy')
      bp_1 = df_f.iloc[-1]['bp_1']
      bp_2 = df_f.iloc[-1]['bp_2']
      print(f'this is bp_1: {bp_1} this is bp_2: {bp_2}')

      exchange.cancel_all_orders(symbol)
      exchange.create_limit_buy_order(symbol, open_size, bp_1, params)
      exchange.create_limit_buy_order(symbol, open_size, bp_2, params)

      time.sleep(120)
      
    else: 
      print('making a opening order as a sell')
      sp_1 = df_f.iloc[-1]['sp_1']
      sp_2 = df_f.iloc[-1]['sp_2']
      print(f'this is sp_1: {sp_1} this is sp_2: {sp_2}')

      exchange.create_limit_sell_order(symbol, open_size, sp_1, params)
      exchange.create_limit_sell_order(symbol, open_size, sp_2, params)

      time.sleep(120)
  else :
    print('we are in position already so not making new orders')


# Run
schedule.every(28).seconds.do(bot)

while True:
  try:
    schedule.run_pending()
  except:
    print('+++ Maybe an internet problem or somethig')
    time.sleep(30)