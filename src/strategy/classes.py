import datetime
import pandas as pd
import time
import json
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient


class Portfolio:
    cash_at_start = 200
    def __init__(self, cash : float, actifs : dict = {}):
        self.creation_date = datetime.datetime.now()
        self.cash = cash
        self.actifs = actifs
        self.list_prices = []
        self.asset_value = self.get_assets_value() if self.actifs else 0
        self.df_transaction_history = pd.DataFrame(columns=['Time', 'Type', 'Ticker', 'Quantity', 'Ticker price', 'Cash cost'])

    def __str__(self):
        return f'Cash : {self.cash} \n Actifs : {self.actifs} \n Transaction history : {self.df_transaction_history}'

    def transaction_order(self, transaction_type, transaction_time, ticker, quantity, ticker_price):
        fees_operation = self.calculate_transaction_fees(quantity, ticker_price)

        if transaction_type == 'BUY':
            self.execute_buy(transaction_time, ticker, quantity, ticker_price, fees_operation)
        elif transaction_type == 'SELL':
            self.execute_sell(transaction_time, ticker, quantity, ticker_price, fees_operation)
        else:
            raise ValueError("Le type de transaction doit être 'BUY' ou 'SELL'.")
    
    def execute_buy(self, transaction_time, ticker, quantity, ticker_price, fees_operation):
        usd_price = quantity*ticker_price
        if self.cash <= usd_price + fees_operation:
            print('Transaction failed, not enough cash')
            return
        if ticker not in self.actifs:
            self.actifs[ticker] = {"quantity" : quantity, "ticker_price" : ticker_price}
        else:
            self.actifs[ticker]['quantity'] += quantity
            self.actifs[ticker]['ticker_price'] = ticker_price
        self.cash -= usd_price + fees_operation
        self.add_to_transaction_history('BUY', transaction_time, ticker, quantity, ticker_price)

    def execute_sell(self, transaction_time, ticker, quantity, ticker_price, fees_operation):
        usd_price = quantity*ticker_price
        if ticker not in self.actifs:
            print('Transaction failed, asset is not in portfolio.')
            return
        if quantity > self.actifs[ticker]['quantity']:
            quantity = self.actifs[ticker]['quantity']
        self.actifs[ticker]['quantity']-=quantity
        self.cash += usd_price-fees_operation
        self.add_to_transaction_history('SELL', transaction_time, ticker, quantity, ticker_price)
        if self.actifs[ticker]['quantity'] == 0:
            del self.actifs[ticker]
    
    @staticmethod
    def calculate_transaction_fees(quantity, ticker_price):
        fees_transaction = 0.001
        return quantity * ticker_price * fees_transaction

    def add_to_transaction_history(self, transaction_type, transaction_time, ticker, quantity, ticker_price):
        cash_cost = quantity * ticker_price * (-1 if transaction_type == 'BUY' else 1) - self.calculate_transaction_fees(quantity, ticker_price)
        transaction = {'Time' : transaction_time, 
                        'Type' : transaction_type,
                        'Ticker' : ticker,
                        'Quantity' : quantity,
                        'Ticker price' : ticker_price,
                        'Cash cost' : round(cash_cost, 2)}

        self.df_transaction_history = pd.concat([self.df_transaction_history, pd.DataFrame([transaction])], ignore_index = True)

    def save(self, start_date, cash, assets_value):
        with open('results.txt', 'a') as f:
            f.write(f"Start Date : {start_date} | End Date : {datetime.datetime.now()} | Cash : {cash} | Assets_value : {assets_value} | Portfolio_change : {((cash+assets_value)/self.cash_at_start - 1)*100:.2f}%\n")

    def message_api(self, _, source):
        message : dict = json.loads(source)
        if 'error' in message:
            print(message['error']['msg'])
        else:
            self.list_prices = message["result"]
    
    def fetch_prices(self):
        try:
            binance_get_price_api_client = SpotWebsocketAPIClient(on_message=self.message_api)
            if self.actifs:
                binance_get_price_api_client.ticker_price(symbols=list(self.actifs.keys()))
            time.sleep(10)
            binance_get_price_api_client.stop()
        except Exception as e:
            print(f"Prix non récupéré : {e}")

    def get_assets_value(self):
        self.fetch_prices()
        assets_value = 0
        for dict_symbol_price in self.list_prices:
             assets_value+= self.actifs[dict_symbol_price['symbol']]['quantity'] * float(dict_symbol_price['price'])
        return assets_value
    
    def evaluate_portfolio_value(self, save_to_file = True, verbose = True):
        cash = self.cash
        assets_value = self.get_assets_value()
        portfolio_value = cash+assets_value
        if verbose:
            print('---------------')
            print(f'Valeur du cash : {cash}')
            print(f'Valeur des actifs : {assets_value}')
            print(f'Valeur du Portefeuille : {portfolio_value}')
            print('---------------')
        if save_to_file:
            self.save(self.creation_date, cash, assets_value)
        return portfolio_value