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
pos_size = 2
params = {
    'timeInForce': 'GTC', # Cambiado de 'PostOnly' a 'GTC' para compatibilidad con Binance,
    'leverage': float(10)
}
target = 0.1

# pos_dict = exchange.fetchPosition(symbol)
# print(f'pos_dict', pos_dict)

def ask_bid():
    ob = exchange.fetchOrderBook(symbol)
    bid = ob['bids'][0][0]
    ask = ob['asks'][0][0]
    return ask, bid

def daily_sma():
    print("starting daily_sma...")
    timeframe = '1d'
    num_bars = 100
    bars = exchange.fetchOHLCV(symbol, timeframe=timeframe, limit=num_bars)
    df_d = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_d['timestamp'] = pd.to_datetime(df_d['timestamp'], unit='ms')
    df_d['sma20_1d'] = df_d.close.rolling(20).mean()
    df_d = df_d.dropna(subset=['sma20_1d'])
    bid = ask_bid()[1]
    df_d.loc[df_d['sma20_1d'] > bid, 'sig'] = 'SELL'
    df_d.loc[df_d['sma20_1d'] < bid, 'sig'] = 'BUY'
    return df_d

def f15_sma():
    print("starting f15_sma...")
    timeframe = '15m'
    num_bars = 100
    bars = exchange.fetchOHLCV(symbol, timeframe=timeframe, limit=num_bars)
    df_f = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_f['timestamp'] = pd.to_datetime(df_f['timestamp'], unit='ms')
    df_f['sma20_15m'] = df_f.close.rolling(20).mean()
    df_f = df_f.dropna(subset=['sma20_15m'])
    df_f['bp_1'] = df_f['sma20_15m'] * 1.001
    df_f['bp_2'] = df_f['sma20_15m'] * 0.997
    df_f['sp_1'] = df_f['sma20_15m'] * 0.999
    df_f['sp_2'] = df_f['sma20_15m'] * 1.003
    return df_f

def open_position():
    try:
        positions = exchange.fetchPositions()
        for pos in positions:
            if pos['info']['symbol'] == symbol:
                open_pos = pos
                side = open_pos['side']
                size = open_pos['contracts']
                is_long = side == 'long'
                return open_pos, True, size, is_long
    except Exception as e:
        print(f'Error fetching positions: {e}')
    return None, False, 0, None

def kill_switch():
    print('starting the kill switch')
    open_pos, openpos_bool, kill_size, is_long = open_position()
    while openpos_bool:
        print('starting kill switch loop till limit fill')
        exchange.cancelAllOrders(symbol)
        ask = ask_bid()[0]
        bid = ask_bid()[1]
        if is_long:
            exchange.createOrder(symbol, 'limit', 'sell', kill_size, ask, params)
            print(f'just made a SELL to CLOSE order of {kill_size} {symbol} at ${ask}')
        else:
            exchange.createOrder(symbol, 'limit', 'buy', kill_size, bid, params)
            print(f'just made a BUY to CLOSE order of {kill_size} {symbol} at ${bid}')
        time.sleep(30)
        open_pos, openpos_bool, kill_size, is_long = open_position()

def pnl_close():
    print('checking to see if it is time to exit')
    try:
        pos_dict = exchange.fetchPosition(symbol)
        print(f'pos_dict', pos_dict)
        if not pos_dict:
            print("No open positions found.")
            return False, False, 0, None
        

        side = pos_dict['side']
        size = pos_dict['contracts']
        entry_price = float(pos_dict['entryPrice'])
        leverage = float(pos_dict['leverage'])
        current_price = ask_bid()[1]
        print(f'side: {side} | entry_price: {entry_price} | lev: {leverage}')
        if side == 'long':
            diff = current_price - entry_price
            is_long = True
        else:
            diff = entry_price - current_price
            is_long = False
        try:
            perc = round(((diff / entry_price) * leverage), 10)
        except ZeroDivisionError:
            perc = 0
        perc *= 100
        print(f'this is our PNL percentage: {perc}%')
        pnl_close = False
        in_pos = True
        if perc > 0:
            print('we are in a winning position')
            if perc > target:
                print(f'hit our target of: {target}%')
                pnl_close = True
                kill_switch()
            else:
                print('we have not hit our target yet')
        elif perc < 0:
            print('we are in a losing position but holding on')
        else:
            print('we are not in position')
            in_pos = False
            size = 0
            is_long = None
    except Exception as e:
        print(f'Error checking positions: {e}')
        pnl_close = False
        in_pos = False
        size = 0
        is_long = None
    return pnl_close, in_pos, size, is_long

def bot():
    pnl_close()
    df_d = daily_sma()
    df_f = f15_sma()
    ask = ask_bid()[0]
    bid = ask_bid()[1]
    sig = df_d.iloc[-1]['sig']
    open_size = pos_size / 2
    _, in_pos, _, _ = pnl_close()
    if not in_pos:
        if sig == 'BUY':
            print('making an opening order as a buy')
            bp_1 = df_f.iloc[-1]['bp_1']
            bp_2 = df_f.iloc[-1]['bp_2']
            print(f'this is bp_1: {bp_1} this is bp_2: {bp_2}')
            exchange.cancelAllOrders(symbol)
            exchange.createOrder(symbol, 'limit', 'buy', open_size, bp_1, params)
            exchange.createOrder(symbol, 'limit', 'buy', open_size, bp_2, params)
        else:
            print('making an opening order as a sell')
            sp_1 = df_f.iloc[-1]['sp_1']
            sp_2 = df_f.iloc[-1]['sp_2']
            print(f'this is sp_1: {sp_1} this is sp_2: {sp_2}')
            exchange.cancelAllOrders(symbol)
            # exchange.create_limit_sell_order(symbol, open_size, sp_1, params)
            # exchange.create_limit_sell_order(symbol, open_size, sp_2, params)
            exchange.createOrder(symbol, 'limit', 'sell', open_size, sp_1, params)
            exchange.createOrder(symbol, 'limit', 'sell', open_size, sp_2, params)
        time.sleep(120)
    else:
        print('we are in position already so not making new orders')

schedule.every(28).seconds.do(bot)

while True:
    try:
        schedule.run_pending()
    except Exception as e:
        print(f'+++ Maybe an internet problem or something: {e}')
        time.sleep(30)