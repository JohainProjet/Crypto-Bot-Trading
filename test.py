#!/usr/bin/env python

import time
import logging
from binance.lib.utils import config_logging
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
import matplotlib.pyplot as plt
import json

config_logging(logging, logging.DEBUG)

current_mid_people_usdt = None
current_mid_people_usdc = None
spread_list = []

TICKER = 'BTC'

def compute_spread(current_mid_people_usdc, current_mid_people_usdt):
    spread = current_mid_people_usdt - current_mid_people_usdc
    spread_list.append(spread)
    if len(spread_list) > 100_000:
        spread_list.pop(0)

def message_handler(_, source):
    global current_mid_people_usdt
    global current_mid_people_usdc
    message : dict = json.loads(source)
    ticker = message.get('s', None)
    bid = message.get('b', None)
    ask = message.get('a', None)
    if bid and ask:
        mid = (float(ask)+float(bid))/2
    if ticker:
        if 'USDT' in ticker:
            current_mid_people_usdt = mid
        elif 'USDC' in ticker:
            current_mid_people_usdc = mid
    if current_mid_people_usdt and current_mid_people_usdc:
        compute_spread(current_mid_people_usdc, current_mid_people_usdt)

        


my_client = SpotWebsocketStreamClient(on_message=message_handler)


my_client.book_ticker(symbol=TICKER + 'USDT')
my_client.book_ticker(symbol=TICKER + 'USDC')
time.sleep(500)

logging.debug("closing ws connection")
my_client.stop()
print(len(spread_list))
plt.plot(spread_list)
plt.show()