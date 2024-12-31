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
                                          ('Price is going up', None)])
dataframe_storage = pd.DataFrame(columns = multi_columns)

limits = {'volume' : 2, 'variation' : 2.3}#(2, 2.3) à tester.
crypto_bought = []
portefeuille_test = Portfolio(200, {})

def messageProcessingkline3m(_, source=None, test_data=None):
    global global_dictionnary
    global crypto_bought
    if test_data:
        message = test_data
    else:
        message : dict = json.loads(source)
    if message.get('result',0) == None:
        print(f'Connection open at {datetime.datetime.now()} with websocket kline 3minutes.')
        return
    
    data = message['data']['k']
    ticker = data['s']
    variation_3m = float(data['h'])-float(data['l'])
    volume_3m = float(data['v'])
    closed_price = float(data['c'])
    open_price = float(data['o'])
    price_is_going_up = bool(closed_price > open_price)
    global_dictionnary['variation3m'] = variation_3m
    global_dictionnary['volume3m'] = volume_3m
    dataframe_storage.loc[ticker, ('Variation', '3m')] = variation_3m
    dataframe_storage.loc[ticker, ('Volume', '3m')] = volume_3m
    dataframe_storage.loc[ticker, ('Price is going up', '')] = price_is_going_up


    if detect_pump(dataframe_storage, ticker, limits, crypto_bought):
        cost_in_usd = 5
        if datetime.datetime.now().minute % 15 == 0:
            cost_in_usd = 50

        crypto_bought.append(ticker)
        ticker_price = float(message['data']['k']['c'])

        add_order("BUY", "MARKET", ticker, cost_in_usd/ticker_price)
        print(f'TICKER : {ticker}')
        print(f"Variation 3m : {dataframe_storage.loc[ticker, ('Variation', '3m')]} | Volume 3m : {dataframe_storage.loc[ticker, ('Volume', '3m')]}")
        print(f"Variation 2h : {dataframe_storage.loc[ticker, ('Variation', '2h')]} | Volume 2h : {dataframe_storage.loc[ticker, ('Volume', '2h')]}")

        portefeuille_test.transaction_order("BUY", datetime.datetime.fromtimestamp(message['data']['E']/1000), ticker, cost_in_usd/ticker_price, ticker_price)

    if detect_dump(ticker, portefeuille_test, closed_price):
        quantity_bought = portefeuille_test.actifs[ticker]['quantity']
        add_order("SELL", "MARKET", ticker, quantity_bought)
        #crypto_bought.remove(ticker)
        portefeuille_test.transaction_order("SELL", datetime.datetime.fromtimestamp(message['data']['E']/1000), ticker, quantity_bought, closed_price)
    else:
        pass

def messageProcessingRolling1h(_, source):
    global global_dictionnary

    message : dict = json.loads(source)
    if message.get('result',0) == None:
        print(f'Connection open at {datetime.datetime.now()} with websocket rolling windows 1hour.')
        return

    data = message['data']
    ticker = data['s']
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
    #print(portefeuille_test.evaluate_portfolio_value())

    dataframe_storage.to_excel("Storage_stats.xlsx")
    portefeuille_test.df_transaction_history.to_excel("Transaction History.xlsx")