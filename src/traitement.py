import pprint
import time
import json
import logging
import torch
import csv
import pandas as pd
from binance.lib.utils import config_logging
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from binance.spot import Spot as Client

torch.set_printoptions(sci_mode=False)

#-----------------------

order_book = {
    "lastUpdateId": 0,
    "bids": [],
    "asks": []
}

symbol = 'bnbbtc'
function = 'depth'
base_url = 'https://api.binance.com'
stream_url = f'wss://stream.binance.com:9443/ws/{symbol}@{function}'

list_tensors = []

spot_client = Client(base_url="https://api.binance.com") #API REST

def get_snapshot():
    return spot_client.depth(symbol.upper(), limit=5)

def message_handler(_, message):
    global order_book
    message = json.loads(message)
    last_update_id = order_book['lastUpdateId']
    if message['u'] <= last_update_id:
        return
    if message['U'] <= last_update_id+1 <= message['u']:
        order_book['lastUpdateId'] = message['u']
        process_updates(message)
        stock_datas()

    else:
        order_book = get_snapshot()

def process_updates(message):
    for update in message['a']:
        manage_order_book('asks', update)
    for update in message['b']:
        manage_order_book('bids', update)

def manage_order_book(side, update):
    price, quantity = update

    for i in range(0, len(order_book[side])):
        if price == order_book[side][i][0]:
            if float(quantity) == 0:
                order_book[side].pop(i)
                return
            else:
                order_book[side][i] = update
                return
    if float(quantity) != 0:
        order_book[side].insert(-1, update)
        if side == 'asks':
            order_book[side] = sorted(order_book[side], key = lambda x: float(x[0]))

        else:
            order_book[side] = sorted(order_book[side], key=lambda x:float(x[0]) ,reverse=True)

    if len(order_book[side]) > 5:
        order_book[side].pop(len(order_book[side]) -1)

def stock_datas():
    global list_tensors

    final_list = [float(item) for sublist in order_book["asks"] for item in sublist]
    list_bids = [float(item) for sublist in order_book["bids"] for item in sublist]
    final_list.extend(list_bids)
    
    new_tensor = torch.tensor(final_list)
    
    list_tensors.append(new_tensor)
    

def stack_tensors():
    global list_tensors

    X = torch.stack(list_tensors)
    print(X)
    return X