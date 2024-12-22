import json
import pandas as pd
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from src.strategy.classes import Portfolio
from src.strategy.strat2.utils import add_order, detect_pump, detect_dump
import datetime

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
dataframe_storage = pd.DataFrame(columns = multi_columns)

limits = {'volume' : 2, 'variation' : 2.3}#(2, 2.3) à tester.
price_is_going_up : bool = False
crypto_bought = []
portefeuille_test = Portfolio(1000, {})

def messageProcessingkline3m(_, source):
    global global_dictionnary
    global price_is_going_up
    global crypto_bought

    message : dict = json.loads(source)
    if message.get('result',0) == None:
        print(f'Connection open at {datetime.datetime.now()} with websocket kline 3minutes.')
        return
    if not '3m' in message['stream']:
        print('erreur')
    
    ticker = message['stream'].upper().split('@')[0]
    data :dict = message['data']['k']
    variation_3m = float(data['h'])-float(data['l'])
    volume_3m = float(data['v'])
    closed_price = message['data']['k']['c']
    open_price = message['data']['k']['o']
    price_is_going_up = bool(closed_price > open_price)
    global_dictionnary['variation3m'] = variation_3m
    global_dictionnary['volume3m'] = volume_3m
    dataframe_storage.loc[ticker, ('Variation', '3m')] = variation_3m
    dataframe_storage.loc[ticker, ('Volume', '3m')] = volume_3m
    dataframe_storage.loc[ticker, ('Price is going up', '')] = price_is_going_up

    if detect_pump(dataframe_storage, limits):
        cost_in_usd = 10
        if datetime.datetime.now().minute % 15 == 0:
            cost_in_usd = 100

        crypto_to_buy = dataframe_storage[dataframe_storage.loc[:, ('Order', 'Buy')]].index.to_list()
        real_crypto_to_buy = [crypto for crypto in crypto_to_buy if crypto not in crypto_bought]
        crypto_bought.extend(real_crypto_to_buy)
        for local_ticker in real_crypto_to_buy:
            ticker_price = float(message['data']['k']['c'])
            add_order("BUY", "MARKET", local_ticker, cost_in_usd/ticker_price)
            print(f'TICKER : {ticker}')
            print(f"Variation 3m : {dataframe_storage.loc[ticker, ('Variation', '3m')]} | Volume 3m : {dataframe_storage.loc[ticker, ('Volume', '3m')]}")
            print(f"Variation 2h : {dataframe_storage.loc[ticker, ('Variation', '2h')]} | Volume 2h : {dataframe_storage.loc[ticker, ('Volume', '2h')]}")          
            portefeuille_test.transaction_order("BUY", datetime.datetime.fromtimestamp(message['data']['E']/1000), ticker, cost_in_usd/ticker_price, ticker_price)
    if detect_dump(ticker, portefeuille_test, float(message['data']['k']['c'])):
        ticker_price = float(message['data']['k']['c'])
        quantity_bought = portefeuille_test.actifs[ticker]['quantity']
        add_order("SELL", "MARKET", ticker, quantity_bought)
        crypto_bought.remove(ticker)
        portefeuille_test.transaction_order("SELL", datetime.datetime.fromtimestamp(message['data']['E']/1000), ticker, quantity_bought, ticker_price)
    else:
        pass

def messageProcessingkline2h(_, source):
    global global_dictionnary
    global price_is_going_up
    global crypto_bought

    message : dict = json.loads(source)
    if message.get('result',0) == None:
        print(f'Connection open at {datetime.datetime.now()} with websocket kline 2hours.')
        return
    if not '2h' in message['stream']:
        print('erreur')
    ticker = message['stream'].upper().split('@')[0]
    data :dict = message['data']['k']
    variation_2h = float(data['h'])-float(data['l'])
    volume_2h = float(data['v'])
    global_dictionnary['variation2h'] = variation_2h
    global_dictionnary['volume2h'] = volume_2h
    dataframe_storage.loc[ticker, ('Variation', '2h')] = variation_2h
    dataframe_storage.loc[ticker, ('Volume', '2h')] = volume_2h

def on_open(_):
    print(f'Strategy start : {datetime.datetime.now()}')

def on_close(_):
    print(portefeuille_test)
    print(portefeuille_test.evaluate_portfolio_value())

    dataframe_storage.to_excel("Storage_stats.xlsx")
    portefeuille_test.df_transaction_history.to_excel("Transaction History.xlsx")