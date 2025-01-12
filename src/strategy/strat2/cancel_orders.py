from binance.client import Client
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
import json
import time

api_key = ''
api_secret = ''
with open('src/spot_test_keys.txt') as f:
    lines = f.read().splitlines()
    api_key = lines[0][4:]
    api_secret = lines[1][7:]
list_crypto = []
def message_handler_orders(_, source):
    global list_crypto
    message = json.loads(source)
    result = message['result']
    print(result)
    for crypto in result:
        list_crypto.append(crypto['symbol'])


# Initialisation du client Binance
def get_open_orders_and_cancel(cancel = False):
    client = SpotWebsocketAPIClient(stream_url="wss://ws-api.testnet.binance.vision/ws-api/v3",
                                    api_key=api_key,
                                    api_secret=api_secret,
                                    on_message=message_handler_orders)
    client.get_open_orders()
    time.sleep(8)
    if cancel:
        for crypto in list_crypto:
            client.cancel_open_orders(symbol=crypto)
    time.sleep(8)
    client.stop()

get_open_orders_and_cancel(cancel=True)