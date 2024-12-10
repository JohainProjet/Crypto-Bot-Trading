import json
from binance.spot import Spot as Client

order_book = {
    "lastUpdateId": 0,
    "bids": [],
    "asks": []
}

symbol = 'jstusdt'

#function = 'depth'
#stream_url = f'wss://stream.binance.com:9443/ws/{symbol}@{function}'

list_tensors = []

spot_client = Client(base_url="https://api.binance.com") #API REST

X_data = [] 
Y_data = []
local_X_data : list = []

def message_handler(_, source):
    global order_book
    message : dict = json.loads(source)
    if message['e'] == 'aggTrade':
        price = message['p']
        print(price)
        Y_data.append(price)
        X_data.append(local_X_data)
        local_X_data.clear()
    elif message['e'] == 'depthUpdate':
        last_update_id = order_book['lastUpdateId']
        if message['u'] <= last_update_id:
            return
        if message['U'] <= last_update_id+1 <= message['u']:
            order_book['lastUpdateId'] = message['u']
            process_updates(message)
            local_X_data.append(order_book)
        else:
            order_book = spot_client.depth(symbol.upper(), limit=5)

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
