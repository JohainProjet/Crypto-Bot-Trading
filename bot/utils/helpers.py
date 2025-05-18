import datetime
import time
import json
import sqlite3
from dataclasses import dataclass
from dataclasses import field
import pandas as pd
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient

pd.set_option('display.float_format', lambda x: '%.10f' % x)

def load_tickers_if_empty(list_tickers=[]):
    if not list_tickers:
        with open(r"bot\data\list_all_pairs.txt", 'r', encoding='utf-8') as f:
            list_tickers = f.read().splitlines()
    return list_tickers

def binary_search_get_price(dict_global_time, pair, timestamp:datetime.datetime): # A corriger
    #unix_timestamp = (int(timestamp.timestamp() * 1000))
    list_values = list(dict_global_time.keys())
    i, j = 0, len(list_values)-1
    while i <= j:
        mid = (i+j)//2
        if list_values[mid] > timestamp:
            j = mid - 1
        elif list_values[mid] < timestamp:
            i = mid + 1
        else:
            i = mid
            break
    if i == len(list_values):
        i-=1
    #i représente l'indice après le timestamp recherché
    final_time = 0
    for j in range(i, -1, -1):
        final_time = list_values[j]
        for flux in dict_global_time[final_time]:
            try:
                #{"stream": "btcusdt@kline_1m", "data": {"e": "kline", "E": 1744636236028, "s": "BTCUSDT", 
                # "k": {"t": 1744636200000, "T": 1744636259999, "s": "BTCUSDT", "i": "1m", 
                # "f": 4823905090, "L": 4823906662, "o": "85017.61000000", "c": "84979.26000000", 
                # "h": "85032.50000000", "l": "84979.25000000", "v": "6.80097000", "n": 1573, 
                # "x": false, "q": "578151.63693140", "V": "1.78783000", "Q": "151995.52453060", "B": "0"}}}

                #{"stream": "btcusdt@ticker_1h", 
                # "data": {"e": "1hTicker", "E": 1744636235738, "s": "BTCUSDT", "p": "89.60000000", 
                # "P": "0.106", "w": "85056.30762628", "o": "84889.66000000", "h": "85279.99000000", 
                # "l": "84752.01000000", "c": "84979.26000000", "v": "899.57125000", "q": "76514208.97175620", 
                # "O": 1744632600000, "C": 1744636235436, "F": 4823788130, "L": 4823906659, "n": 118530}}


                #{"stream": "tstusdc@miniTicker", 
                # "data": {"e": "24hrMiniTicker", "E": 1745921095961, 
                # "s": "TSTUSDC", "c": "0.06680000", "o": "0.07220000", 
                # "h": "0.07310000", "l": "0.06610000", "v": "7242908.00000000", "q": "503029.22845000"}}

                data = flux['data']

                """ if pair.endswith('USDT') or pair.endswith('USDC'):
                    ticker = pair[:-4]
                elif pair.endswith('BTC') or pair.endswith('TRY'):
                    ticker = pair[:-3] """

                if pair == data['s']:
                    last_price = data.get('k', data)['c']
                    res = {'symbol': pair, 'price': last_price}
                    return res
            except Exception:
                continue
    return ['ERROR']

@dataclass
class Parameters:
    duration_time : int
    limits : dict
    stop_loss_prct : int
    program_type : str
    kline_type : str
    std_rolling_size : int
    mean_rolling_size : int
    start_date : datetime.datetime = field(default_factory=datetime.datetime.now)
    end_date : datetime.datetime = field(default_factory=datetime.datetime.now)
    list_tickers : list = field(default_factory=list)
    ticker_bought_actual_max_price : dict = field(default_factory=dict)
    crypto_bought : list = field(default_factory=list)

class Portfolio:
    def __init__(self, program_type : str, cash : float, actifs : dict = {}):
        self.program_type = program_type
        self.creation_date = datetime.datetime.now()
        self.current_cash = cash
        self.initial_cash = cash
        self.actifs = actifs #{"quantity" : quantity, "entry_price" : entry_price}

        self.current_btc_usdt_price = 94500
        self.current_usdc_try_price = 38.41

        self.df_transaction_history = pd.DataFrame(
            columns=['Time',
                     'Type',
                     'Ticker',
                     'Quantity',
                     'Ticker price',
                     'Cash cost']
        )

    def __str__(self):
        return (f'Cash : {self.current_cash} \n'
                f'Actifs : {self.actifs} \n'
                f'Transaction history : {self.df_transaction_history}')

    def check_buy_sell(self, transaction_type, ticker, quantity, ticker_price):
        if transaction_type == 'BUY':
            assert self.current_cash >= quantity*ticker_price,'Transaction failed, not enough cash.'
        elif transaction_type == 'SELL':
            assert ticker in self.actifs, 'Transaction failed, asset is not in portfolio.'

    @staticmethod
    def get_quoted_asset(ticker):
        if ticker.endswith('USDC'):
            quote_asset = 'USDC'
        elif ticker.endswith('BTC'):
            quote_asset = 'BTC'
        elif ticker.endswith('TRY'):
            quote_asset = 'TRY'
        return quote_asset

    def convert_price_to_usdt(self, current_price, quote_asset):
        if quote_asset == 'USDC':
            final_price = current_price
        elif quote_asset == 'BTC':
            final_price = current_price*self.current_btc_usdt_price
        elif quote_asset == 'TRY':
            final_price = current_price/self.current_usdc_try_price
        return final_price

    def convert_price_to_try_or_btc(self, current_price, quote_asset):
        if quote_asset == 'USDC':
            final_price = current_price
        elif quote_asset == 'BTC':
            final_price = current_price/self.current_btc_usdt_price
        elif quote_asset == 'TRY':
            final_price = current_price*self.current_usdc_try_price
        return final_price

    def transaction_order(self, transaction_type, transaction_time, pair, quantity, ticker_price):
        quote_asset = self.get_quoted_asset(pair)

        ticker_price_usdt = self.convert_price_to_usdt(ticker_price, quote_asset)
        self.check_buy_sell(transaction_type, pair, quantity, ticker_price_usdt)
        commission = self.calculate_transaction_fees(quantity)
        if transaction_type == 'BUY':
            cash_cost = quantity * ticker_price_usdt
            quantity -= commission
        elif transaction_type == 'SELL':
            cash_cost = (quantity - commission) * ticker_price_usdt
        if transaction_type == 'BUY':
            self.execute_buy(transaction_time, pair, quantity, ticker_price, cash_cost)
        elif transaction_type == 'SELL':
            self.execute_sell(transaction_time, pair, quantity, ticker_price, cash_cost)

    def execute_buy(self, transaction_time, ticker, quantity, entry_price, cash_paid):
        if ticker not in self.actifs:
            self.actifs[ticker] = {"quantity" : quantity,
                                   "entry_price" : entry_price,
                                   'current_price' : entry_price}
        else:
            self.actifs[ticker]['quantity'] += quantity
            self.actifs[ticker]['entry_price'] = entry_price
        self.current_cash -= cash_paid
        self.add_to_transaction_history('BUY', transaction_time, ticker, quantity, entry_price, - cash_paid)

    def execute_sell(self, transaction_time, ticker, quantity, ticker_price, cash_receive):
        print('inside sell', transaction_time, ticker, quantity, ticker_price, cash_receive)
        quantity = min(quantity, self.actifs[ticker]['quantity'])
        self.actifs[ticker]['quantity']-=quantity
        self.current_cash += cash_receive
        self.add_to_transaction_history('SELL', transaction_time, ticker, quantity, ticker_price, cash_receive)
        del self.actifs[ticker]
 
    @staticmethod
    def calculate_transaction_fees(quantity, commission_asset = None):
        """ fees in commission asset"""
        fees_transaction = 0.0009500
        if commission_asset == 'BNB':
            fees_transaction = 0.0007125
        return quantity * fees_transaction

    def add_to_transaction_history(self,
                                   transaction_type,
                                   transaction_time,
                                   ticker, 
                                   quantity,
                                   ticker_price,
                                   cash_operation):
        transaction = {
            'Time' : transaction_time,
            'Type' : transaction_type,
            'Ticker' : ticker,
            'Quantity' : quantity,
            'Ticker price' : ticker_price,
            'Cash cost' : round(cash_operation, 2)
        }
        if self.df_transaction_history.empty:
            self.df_transaction_history = pd.DataFrame([transaction])
        else:
            self.df_transaction_history = pd.concat(
            [
                self.df_transaction_history,
                pd.DataFrame([transaction])
            ],
            ignore_index = True
        )

    def save(self, start_date, current_cash, assets_value):
        with open(r'bot\results\results.txt', 'a', encoding='utf-8') as f:
            f.write(f"Start Date : {start_date} |"
                    f"End Date : {datetime.datetime.now()} |"
                    f"Cash : {current_cash} |",
                    f"Assets_value : {assets_value} |",
                    f"Portfolio_change : {((current_cash+assets_value)/self.initial_cash - 1)*100:.2f}%\n")

    def message_api(self, _, source):
        message : dict = json.loads(source)
        if 'error' in message:
            print(message['error']['msg'])
        else:
            self.update_current_price(message["result"]) 

    def update_current_price(self, list_current_prices):
        for dict_symbol_price in list_current_prices:
            ticker = dict_symbol_price['symbol']
            price = float(dict_symbol_price['price'])
            if ticker == 'BTCUSDT':
                self.current_btc_usdt_price = price
                continue
            elif ticker == 'USDCTRY':
                self.current_usdc_try_price = price
                continue
            self.actifs[ticker]['current_price'] = price #PROBLEME VENANT DE CETTE LIGNE, en fait current_price n'est pas bon donc ça vient de update le prob
            #Ca doit sûrement update et mettre les prix usdt dans current_price alors que c'est pas du tout ce qu'on veut puisqu'ils sont en try btc


    def fetch_prices(self, timestamp = None, dict_global_time = None):
        if self.program_type in ['PROD', 'TEST']:
            try:
                binance_get_price_api_client = SpotWebsocketAPIClient(on_message=self.message_api)
                if self.actifs:
                    binance_get_price_api_client.ticker_price(symbols=list(self.actifs.keys())+['BTCUSDT']+['USDCTRY'])
                time.sleep(7)
                binance_get_price_api_client.stop()
            except Exception as e:
                print(f"Prix non récupéré : {e}")
        else:
            list_tickers = list(self.actifs.keys())
            for pair in list_tickers:
                self.update_current_price([
                    binary_search_get_price(
                        dict_global_time,
                        pair,
                        timestamp)
                ])

    @staticmethod
    def get_dict_global_times():
        from bot.trading.backtesting import Datas
        return Datas.data_manager.dict_global

    def get_assets_value(self, timestamp = None, dict_global_time = None):
        self.fetch_prices(timestamp, dict_global_time)
        assets_value = 0
        for pair, dict_ in self.actifs.items():
            quote_asset = self.get_quoted_asset(pair)
            current_price_in_quote_quantity = float(dict_['current_price'])
            ticker_price_usdt = self.convert_price_to_usdt(current_price_in_quote_quantity, quote_asset)
            assets_value += dict_['quantity'] * ticker_price_usdt
        return assets_value

    def evaluate_portfolio_value(self, timestamp = None, dict_global_time = None, save_to_file = False, verbose = True):
        assets_value = self.get_assets_value(timestamp, dict_global_time)
        portfolio_value = self.current_cash+assets_value
        if verbose:
            print('---------------')
            print(f'Valeur du cash : {self.current_cash}')
            print(f'Valeur des actifs : {assets_value}')
            print(f'Valeur du Portefeuille : {portfolio_value}')
            print('---------------')
        if save_to_file:
            self.save(self.creation_date, self.current_cash, assets_value)
        return self.current_cash, assets_value

def periodic_sleep(total_duration, interval):
    elapsed_time = 0

    while elapsed_time < total_duration:
        time.sleep(interval)
        elapsed_time += interval

        remaining_time = total_duration- elapsed_time
        print(f"Temps écoulé : {elapsed_time} secondes. Temps restant : {remaining_time} secondes.")


    """
    #Define parameters
    limits = {'volume' : 5,#2
              'variation' : 5,#2.3
              'nbOfTrades' : 5}#6 trop haut # 4 encore trop haut même si mieux ? #3
    stop_loss_price = 0.995 #0.985
     """

def generate_parameters_combinaison():
    list_parameters = []

    volumes = [1.5, 1.8, 2.1]
    variations = [1.5, 1.8, 2.1]
    nb_of_trades = [3, 4, 5]
    stop_loss_prices = [0.97, 0.98, 0.99]

    for stop_price in stop_loss_prices:
        for volume in volumes:
            for variation in variations:
                for nbOfTrade in nb_of_trades:
                    limits = {'volume' : volume,
                            'variation' : variation,
                            'nbOfTrades' : nbOfTrade}
                    list_parameters.append((limits, stop_price))
    return list_parameters
if __name__ == '__main__':
    generate_parameters_combinaison()

