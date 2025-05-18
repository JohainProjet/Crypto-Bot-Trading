#!/usr/bin/env python

import logging
import time
import json
import pprint
import os
from binance.lib.utils import config_logging
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from collections import deque, defaultdict
from datetime import datetime
from bot.utils.helpers import load_tickers_if_empty

config_logging(logging, logging.DEBUG)

#{"stream": "1inchusdt@ticker_1h", "data": {"e": "1hTicker", "E": 1746780223858, "s": "1INCHUSDT", "p": "0.00140000", 
# "P": "0.613", "w": "0.23206065", "o": "0.22840000", "h": "0.23700000", "l": "0.22770000", "c": "0.22980000", 
# "v": "5187683.80000000", "q": "1203857.29151000", "O": 1746776580000, "C": 1746780222962, "F": 97918396, "L": 97925387, "n": 6992}}

start_time = 1746776619858
end_time = 1746827340568 #1746780219858

#On découpe en intervalles de 999_000 millisecondes
interval = 1_000_000
ranges = []
current = start_time
while current < end_time:
    next_time = min(current + interval, end_time)
    ranges.append((current, next_time))
    current = next_time
print(ranges)
print(len(ranges))
count_nb_of_messages = 0
class DataManager:
    def __init__(self):
        self.path = r'bot/data/historical_datas_from_api'
        self.klines : dict = {}
        self.rolling_window = {}
        self.kline_write_counter = {}
        self.window_ready = []

        #for rolling
        self.current_volume = {}
        self.current_nb_of_trades = {}
        self.current_quantities = {}
        self.closes = defaultdict(list)
        self.volume_to_subtract = {}
        self.current_nb_of_trades_to_substract = {}
        self.current_quantities_to_substract = {}
         #test
        self.nb_of_trades = 0
        self.count = 0
        self.start_date = None

        #miniTicker
        self.mini_ticker = {}

    def create_kline_1s(self, ticker, message):
        """         
        1 = t
        2 = o
        3 = h
        4 = l
        5 = c
        6 = v
        7 = T
        8 = q
        9 = n
        10 = V
        11 = Q 
        """
        t = message[0]
        o = message[1]
        h = message[2]
        l = message[3]
        c = message[4]
        v = message[5]
        E = message[6]
        q = message[7]
        n = message[8]
        V = message[9]
        Q = message[10]
        B = message[11]

        T = int(t + 59_999)
        k = {
            't': t,
            'T': T,
            'E': E,
            's': ticker,
            'i': '1m', 
            'f': None,
            'L': None,
            'o': o,
            'c': c,
            'h': h,
            'l': l,
            'v': v,
            'n': n,
            'x':'false',
            'q': q,
            'V': V,
            'Q': Q,
            'B': B
        }
        return k

    def update_klines(self, k_1s):
        symbol = k_1s['s']
        minute_timestamp = k_1s['t'] // 60000 * 60000  # début de la minute
        #Rajouter un compteur > 60 pour être sûr qu'on a bien une vraie kline, pareil pour rolling windows faudra > 3600

        symbol_data = self.klines.get(symbol)
        if symbol_data:
            last_minute = symbol_data['data']['k']['t']
            agg_data = symbol_data['data']

        if symbol not in self.klines or minute_timestamp != last_minute:
            k = {
                't': minute_timestamp,
                'T': k_1s['T'],
                's': symbol,
                'i': '1m',
                'f': None,
                'L': None,
                'o': k_1s['o'],
                'c': k_1s['c'],
                'h': k_1s['h'],
                'l': k_1s['l'],
                'v': float(k_1s['v']),
                'n': int(k_1s['n']),
                'x': 'false',
                'q': float(k_1s['q']),
                'V': float(k_1s['V']),
                'Q': float(k_1s['Q']),
                'B': k_1s['B']
                }
            data = {'e' : 'kline',
                    'E' : k_1s['E'],
                    's' : symbol,
                    'k' : k}
            
            full_kline = {'stream' : symbol.lower()+'@kline_1m',
                                'data' : data}
            self.klines[symbol] = full_kline
        else:
            agg_data['E'] = k_1s['E']
            agg = agg_data['k']
            agg['h'] = max(agg['h'], k_1s['h'], key=float)
            agg['l'] = min(agg['l'], k_1s['l'], key=float)
            agg['c'] = k_1s['c']
            agg['v'] += round(float(k_1s['v']), 8)
            agg['q'] += float(k_1s['q'])
            agg['n'] += int(k_1s['n'])
            agg['V'] += round(float(k_1s['V']), 8)
            agg['Q'] += float(k_1s['Q'])

            agg['B'] = k_1s['B']
        self.kline_write_counter[symbol] = self.kline_write_counter.get(symbol, 0) + 1
        if self.kline_write_counter[symbol] == 2:
            self.kline_write_counter[symbol] = 0
            if symbol in self.window_ready:
                with open(os.path.join(self.path, 'kline1m', symbol + '.txt'), 'a') as f:
                    f.write(json.dumps(self.klines[symbol])+ '\n')
    
    def update_rolling_window(self, k_1s):
        symbol = k_1s['s']
        if symbol not in self.rolling_window:
            self.rolling_window[symbol] = deque()
        o = float(k_1s['o'])
        p = round((float(k_1s['c']) - o), 8)
        v = round(float(k_1s['v']), 8)
        q = round(float(k_1s['q']), 8)
        n = k_1s['n']
        E = k_1s['E']


        if len(self.rolling_window.get(symbol, [])) < 3600:
            pass#print(len(self.rolling_window.get(symbol, [])))

        try:
            w = round(q/v, 8)
        except ZeroDivisionError:
            w = None
        data = {'e': '1hTicker',
                'E': E,
                's': symbol,
                'p': p,
                'P': round(100*p/o, 8),
                'w': w,
                'o': k_1s['o'],
                'h': k_1s['h'],
                'l': k_1s['l'],
                'c': k_1s['c'],
                'v': v,
                'q': q,
                'O': None,
                'C': None,
                'F': None,
                'L': None,
                'n': n}
        
        full_kline = {'stream' : symbol.lower()+'@ticker_1h',
                            'data' : data}
        self.rolling_window[symbol].append(full_kline)

        self.closes[symbol].append(float(k_1s['c']))
        self.current_volume[symbol] = self.current_volume.get(symbol, 0) + v
        self.current_nb_of_trades[symbol] = self.current_nb_of_trades.get(symbol, 0) + n
        self.current_quantities[symbol] = self.current_quantities.get(symbol, 0) + q
        #print(self.current_nb_of_trades[symbol])
        window = self.rolling_window[symbol]
        #248 027 1746784279999
        #263 359 1746784279999
        #336 866 1746784279999
        #227 947 1746784279999
        #window[-1]['data']['E']

        """
        43557
        1000

        112626
        2000

        227947
        3000
        """

        if len(window) >= 3660:
            self.window_ready.append(symbol)
            #print(self.current_volume[symbol], self.current_nb_of_trades[symbol], self.current_quantities[symbol])
            if E % 60_000 <= 1000:
                volume_to_subtract, current_nb_of_trades_to_substract, current_quantities_to_substract = 0, 0, 0
                volume_to_subtract += float(window[0]['data']['v'])
                current_nb_of_trades_to_substract += window[0]['data']['n']
                current_quantities_to_substract += float(window[0]['data']['q'])
                window.popleft()
                while window[0]['data']['E'] % 60000 > 1000:
                    volume_to_subtract += float(window[0]['data']['v'])
                    current_nb_of_trades_to_substract += window[0]['data']['n']
                    current_quantities_to_substract += float(window[0]['data']['q'])
                    window.popleft()
                    self.closes[symbol].pop(0)
                self.current_volume[symbol] -= volume_to_subtract
                self.current_nb_of_trades[symbol] -= current_nb_of_trades_to_substract
                self.current_quantities[symbol] -= current_quantities_to_substract

            o = float(window[0]['data']['o'])
            p = (self.closes[symbol][-1] - o)
            q = round(self.current_quantities[symbol], 8)
            v = round(self.current_volume[symbol], 8)
            
            data = {'e': '1hTicker',
                    'E': E,
                    's': symbol,
                    'p': round((self.closes[symbol][-1] - o), 8),
                    'P': round(100*p/o, 8),
                    'w': round(q/v, 8),
                    'o': round(float(window[0]['data']['o']), 8),
                    'h': round(max(self.closes[symbol]), 8),
                    'l': round(min(self.closes[symbol]), 8),
                    'c': round(self.closes[symbol][-1], 8),
                    'v': v,
                    'q': q,
                    'O': None,
                    'C': None,
                    'F': None,
                    'L': None,
                    'n': self.current_nb_of_trades[symbol]}
            full_kline = {'stream' : symbol.lower()+'@ticker_1h',
                                'data' : data}
            
            with open(os.path.join(self.path, 'historical_window_1h', symbol + '.txt'), 'a') as f:
                f.write(json.dumps(full_kline)+ '\n')

    def update_mini_ticker(self, k_1s):
        symbol = k_1s['s']
        #{"stream": "dogeusdc@miniTicker", 
        # "data": {"e": "24hrMiniTicker", "E": 1746780215588, "s": "DOGEUSDC", "c": "0.20306000", 
        # "o": "0.18301000", "h": "0.21450000", "l": "0.18210000", "v": "193500666.00000000", "q": "37865891.83400000"}}

        data = {
            'e': '24hrMiniTicker',
            'E': k_1s['E'],
            's': symbol,
            'c': k_1s['c'],
            'o': False,
            'h': False,
            'l': False,
            'v': False,
            'q': False,
            }
        full_kline = {'stream' : symbol.lower()+'@miniTicker',
                        'data' : data}
        self.mini_ticker[symbol] = full_kline
        if symbol in self.window_ready:
            with open(os.path.join(self.path, 'mini_ticker', symbol + '.txt'), 'a') as f:
                f.write(json.dumps(self.mini_ticker[symbol])+ '\n')

    def main(self, message):
        ticker = message['id']
        list_klines = message['result']

        for kline in list_klines:
            kline = self.create_kline_1s(ticker, kline)
            self.update_rolling_window(kline)
            self.update_klines(kline)
            #self.test(kline)

            self.update_mini_ticker(kline)


    """ def test(self, k_1s):
        if self.start_date is None:
            self.start_date = datetime.fromtimestamp(k_1s['E'] / 1000)
        self.nb_of_trades += k_1s['n']
        if self.count < 3600:
            self.count+=1
        if self.count==3600:
            print(self.start_date)
            end_date = datetime.fromtimestamp(k_1s['E'] / 1000)
            print(end_date)
            print(self.nb_of_trades)
            raise False """

def on_close(_):
    logging.info("Do custom stuff when connection is closed")

dataManager = DataManager()
def message_handler(_, source):
    global count_nb_of_messages
    message = json.loads(source)
    print(message['rateLimits'])
    dataManager.main(message)
    #print(message.keys())
    #print(message)


my_client = SpotWebsocketAPIClient(on_message=message_handler, on_close=on_close)

symbols = ["DOGEUSDT"]

for start_time, end_time in ranges:
    for symbol in symbols:
        my_client.klines(symbol=symbol, interval="1s", startTime=start_time, endTime=end_time, id=symbol, limit=1000)
        for _ in range(1000):
            pass
        time.sleep(0.2)
#my_client.klines(symbol="1INCHUSDT", interval="1s", startTime=1746780240000, endTime=1746780299999)

time.sleep(1000)

logging.info("closing ws connection")
my_client.stop()




""" 
import json
import matplotlib.pyplot as plt
import datetime

list_rolling_test = []
list_rolling_real = []


count_test_lines = 0
with open(r'bot/data/historical_datas/mini_ticker/DOGEUSDT.txt', 'r') as f:
    for line in f:
        message = json.loads(line)
        x = datetime.datetime.fromtimestamp(message['data']['E'] / 1000)
        y = float(message['data']['c'])
        list_rolling_test.append((x, y))
        count_test_lines+=1

with open(r'bot/data/historical_datas_from_api/mini_ticker/DOGEUSDT.txt', 'r') as f:
    for line in f:
        if count_test_lines == 0:
            break
        message = json.loads(line)
        x = datetime.datetime.fromtimestamp(message['data']['E'] / 1000)
        y = float(message['data']['c'])
        list_rolling_real.append((x, y))
        count_test_lines-=1

list_rolling_test.sort(key = lambda x: x[0])
list_rolling_real.sort(key = lambda x: x[0])

print(len(list_rolling_real))
print(len(list_rolling_test))
print(list_rolling_real[0], list_rolling_real[-1])
x_test, y_test = zip(*list_rolling_test)
x_real, y_real = zip(*list_rolling_real)
print('devant plot')

plt.figure(figsize=(12, 6))
plt.plot(x_real, y_real, label='real')
plt.plot(x_test, y_test, label='test', alpha=0.6)
plt.xlabel('Time')
plt.ylabel('Volume')
plt.title('Comparaison des volumes test vs réel')
plt.legend()
plt.grid(True)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
 """