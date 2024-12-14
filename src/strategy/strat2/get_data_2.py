import json
import pandas as pd
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from src.utils import get_api_key
from src.strategy.classes import Portfeuille
import time
from datetime import datetime

api_key, api_secret = get_api_key()

binance_api_client = SpotWebsocketAPIClient(stream_url="wss://ws-api.testnet.binance.vision/ws-api/v3", 
                                            api_key=api_key,
                                            api_secret=api_secret)

global_dictionnary : dict = {'variation2h' : 0,
                            'volume2h' : 0,
                            'variation3m' : 0,
                            'volume3m' : 0,
                            'buy' : 0}
multi_columns = pd.MultiIndex.from_tuples([('Variation', '3m'), ('Variation', '2h'),
                                          ('Volume', '3m'), ('Volume', '2h'), 
                                          ('Order', 'Buy'), ('Order', 'Sell'),
                                          ('Crypto Bought', ''), ('Crypto Sell', ''), 
                                          ('Price is going up', None)])
dataframe_storage = pd.DataFrame(index = ['btcusdt', 'troyusdt'], columns = multi_columns)

limits = {'volume' : 3, 'variation' : 3}
price_is_going_up : bool = False
crypto_bought = []
portefeuille_test = Portfeuille(1000, {})
def messageProcessing(_, source):
    global global_dictionnary
    global price_is_going_up
    global crypto_bought

    message : dict = json.loads(source)
    crypto_name = message['stream'].upper().split('@')[0]
    if '2h' in message['stream']:
        data :dict = message['data']['k']
        variation_2h = float(data['h'])-float(data['l'])
        volume_2h = float(data['v'])
        global_dictionnary['variation2h'] = variation_2h
        global_dictionnary['volume2h'] = volume_2h
        dataframe_storage.loc[crypto_name, ('Variation', '2h')] = variation_2h
        dataframe_storage.loc[crypto_name, ('Volume', '2h')] = volume_2h
    elif '3m' in message['stream']:
        data :dict = message['data']['k']
        variation_3m = float(data['h'])-float(data['l'])
        volume_3m = float(data['v'])
        closed_price = message['data']['k']['c']
        open_price = message['data']['k']['o']
        price_is_going_up = bool(closed_price > open_price)
        global_dictionnary['variation3m'] = variation_3m
        global_dictionnary['volume3m'] = volume_3m
        dataframe_storage.loc[crypto_name, ('Variation', '3m')] = variation_3m
        dataframe_storage.loc[crypto_name, ('Volume', '3m')] = volume_3m
        dataframe_storage.loc[crypto_name, ('Price is going up', '')] = price_is_going_up
    if detect_pump(dataframe_storage, limits):
        crypto_to_buy = dataframe_storage[dataframe_storage.loc[:, ('Order', 'Buy')]].index.to_list()
        real_crypto_to_buy = [crypto for crypto in crypto_to_buy if crypto not in crypto_bought]
        crypto_bought.extend(real_crypto_to_buy)
        for ticker in real_crypto_to_buy:
            price = float(message['data']['k']['c'])
            add_order("BUY", "MARKET", ticker, 10/price)
            print(f"Variation 3m : {dataframe_storage.loc[crypto_name, ('Variation', '3m')]} | Volume 3m : {dataframe_storage.loc[crypto_name, ('Volume', '3m')]}")
            print(f"Variation 2h : {dataframe_storage.loc[crypto_name, ('Variation', '2h')]} | Volume 2h : {dataframe_storage.loc[crypto_name, ('Volume', '2h')]}")          
            portefeuille_test.transaction_order("BUY", datetime.fromtimestamp(message['data']['E']/1000), ticker, 5/price, price)
    if crypto_name in portefeuille_test.actifs and 0.8*portefeuille_test[ticker]['price'] <= message['data']['k']['c']:
        add_order("SELL", "MARKET", ticker, 10/price)
        portefeuille_test.transaction_order("SELL", datetime.fromtimestamp(message['data']['E']/1000), ticker, 5/price, price)
    else:
        pass
def detect_pump(dataframe_storage, limits):
    variation_condition = (limits['variation']*dataframe_storage.loc[:,('Variation', '3m')] > 
    dataframe_storage.loc[:,('Variation', '2h')])
    volume_condition = (limits['volume']*dataframe_storage.loc[:,('Volume', '3m')] > 
    dataframe_storage.loc[:,('Volume', '2h')])
    price_is_going_up_condition = dataframe_storage.loc[: , ('Price is going up', '')]
    dataframe_storage.loc[:, ('Order', 'Buy')] = variation_condition & volume_condition & price_is_going_up_condition
    if any(dataframe_storage.loc[:, ('Order', 'Buy')].to_list()):
        return True
    return False

def add_order(order, order_type, symbol, quantity):
    binance_api_client.new_order_test(symbol=symbol,
                                      side=order,
                                      type=order_type,
                                      quantity=quantity,
                                      newClientOrderId="my_order_id_1",
                                      newOrderRespType="RESULT")
    
def get_ticker_price(ticker):
    return binance_api_client.ticker_price(symbol=ticker)["result"]['price']