from datetime import datetime
import pandas as pd
import time
import json
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient

list_prices = []
def message_api(_, source):
    global list_prices
    message : dict = json.loads(source)
    if 'error' in message:
        print(message['error']['msg'])
    else:
        list_prices = message["result"]

binance_get_price_api_client = SpotWebsocketAPIClient(on_message=message_api)

class Portfolio:
    def __init__(self, cash : float, actifs : dict):
        self.cash = cash
        self.actifs = actifs
        self.df_transaction_history = pd.DataFrame(columns=['Time', 'Type', 'Ticker', 'Quantity', 'Ticker price', 'Cash cost'])

    def __str__(self):
        return f'Cash : {self.cash} \n Actifs : {self.actifs} \n Transaction history : {self.df_transaction_history}'

    def transaction_order(self, transaction_type, transaction_time, ticker, quantity, ticker_price):
        if transaction_type == 'BUY':
            if self.cash <= quantity*ticker_price:
                print('Transaction failed, not enough cash')
                return
            elif not ticker in self.actifs:
                self.actifs[ticker] = {"quantity" : quantity,
                                    "ticker_price" : ticker_price}
                self.cash -= quantity*ticker_price
            else:
                self.actifs[ticker]['quantity']+=quantity
                self.actifs[ticker]['ticker_price']+=ticker_price
            self.add_to_transaction_history(transaction_type, transaction_time, ticker, quantity, ticker_price) 
        elif transaction_type == 'SELL':
            if not ticker in self.actifs:
                print("problème l'actif n'est pas possédé")
                return
            elif quantity >= self.actifs[ticker]['quantity']:
                quantity = self.actifs[ticker]['quantity']
            self.actifs[ticker]['quantity']-=quantity
            self.cash += quantity*ticker_price
            self.add_to_transaction_history(transaction_type, transaction_time, ticker, quantity, ticker_price)
            if self.actifs[ticker]['quantity'] == 0:
                self.actifs.pop(ticker, None)
    def add_to_transaction_history(self, transaction_type, transaction_time, ticker, quantity, ticker_price):
        number=1
        if transaction_type == 'BUY':
            number=-1
        dict_ = {'Time' : transaction_time, 
                 'Type' : transaction_type,
                 'Ticker' : ticker,
                 'Quantity' : quantity,
                 'Ticker price' : ticker_price,
                 'Cash cost' : round(quantity*ticker_price*number, 2)}
        
        self.df_transaction_history = pd.concat([self.df_transaction_history, pd.DataFrame(dict_, index=[0])])
        print(self.df_transaction_history)

    def evaluate_portfolio_value(self):
        assets_value = 0
        if len(list(self.actifs.keys())) > 0:
            binance_get_price_api_client.ticker_price(symbols=list(self.actifs.keys()))
        time.sleep(10)
        binance_get_price_api_client.stop()
        print(list_prices)
        for dict_symbol_price in list_prices:
             assets_value+= self.actifs[dict_symbol_price['symbol']]['quantity']*float(dict_symbol_price['price'])
        print('---------------')
        print(f'Valeur du cash : {self.cash}')
        print(f'Valeur des actifs : {assets_value}')
        print(f'Valeur du Portefeuille : {self.cash+assets_value}')
        print('---------------')
        
        df_results = self.df_transaction_history.pivot_table(index=['Ticker', 'Type', 'Time'], values = ['Quantity', 'Ticker price', 'Cash cost'], margins=True, margins_name = 'Totaux')
        print(df_results)
        pass