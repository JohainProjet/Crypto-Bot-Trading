import datetime
import time
import json
from dataclasses import dataclass
from dataclasses import field
import pandas as pd
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient


def binary_search_get_price(dict_global_time, crypto, timestamp:datetime.datetime):
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
    #i représente l'indice après le timestamp recherché
    final_time = 0
    for j in range(i, -1, -1):
        final_time = list_values[j]
        for flux in dict_global_time[final_time]:
            try:
                if crypto in flux["data"]['s']:
                    res = {'symbol': crypto, 'price': float(flux['data']['k']['c'])}

                    return res
            except Exception:
                continue
    return 'ERROR'

@dataclass
class Parameters:
    limits : dict
    stop_loss_price : int
    type_ : str
    start_date : datetime.datetime = field(default_factory=datetime.datetime.now)
    end_date : datetime.datetime = field(default_factory=datetime.datetime.now)
    ticker_bought_actual_max_price : dict = field(default_factory=dict)
    crypto_bought : list = field(default_factory=list)


class Portfolio:
    def __init__(self, cash : float, parameters : Parameters, actifs : dict = {}):
        self.creation_date = datetime.datetime.now()
        self.parameters = parameters
        self.cash = cash
        self.cash_at_start = cash
        self.actifs = actifs
        self.list_prices = []
        self.portfolio_values = [cash]
        self.asset_value = self.get_assets_value() if self.actifs else 0
        self.df_transaction_history = pd.DataFrame(
            columns=['Time',
                     'Type',
                     'Ticker',
                     'Quantity',
                     'Ticker price',
                     'Cash cost']
        )

    def __str__(self):
        return (f'Cash : {self.cash} \n'
                f'Actifs : {self.actifs} \n'
                f'Transaction history : {self.df_transaction_history}')

    def check_buy_sell(self, transaction_type, ticker, quantity, ticker_price):
        fees_operation = self.calculate_transaction_fees(quantity, ticker_price)
        if transaction_type == 'BUY':
            assert self.cash >= quantity*ticker_price + fees_operation,'Transaction failed, not enough cash.'
        elif transaction_type == 'SELL':
            assert ticker in self.actifs, 'Transaction failed, asset is not in portfolio.'

    def transaction_order(self, transaction_type, transaction_time, ticker, quantity, ticker_price):
        fees_operation = self.calculate_transaction_fees(quantity, ticker_price)
        self.check_buy_sell(transaction_type, ticker, quantity, ticker_price)
        if transaction_type == 'BUY':
            self.execute_buy(transaction_time, ticker, quantity, ticker_price, fees_operation)
        elif transaction_type == 'SELL':
            self.execute_sell(transaction_time, ticker, quantity, ticker_price, fees_operation)
        else:
            raise ValueError("Le type de transaction doit être 'BUY' ou 'SELL'.")

    def execute_buy(self, transaction_time, ticker, quantity, ticker_price, fees_operation):
        if ticker not in self.actifs:
            self.actifs[ticker] = {"quantity" : quantity, "ticker_price" : ticker_price}
        else:
            self.actifs[ticker]['quantity'] += quantity
            self.actifs[ticker]['ticker_price'] = ticker_price
        self.cash -= quantity*ticker_price + fees_operation
        self.add_to_transaction_history('BUY', transaction_time, ticker, quantity, ticker_price)

    def execute_sell(self, transaction_time, ticker, quantity, ticker_price, fees_operation):
        usd_price = quantity*ticker_price
        if ticker not in self.actifs:
            print('Transaction failed, asset is not in portfolio.')
            return
        quantity = min(quantity, self.actifs[ticker]['quantity'])
        self.actifs[ticker]['quantity']-=quantity
        self.cash += usd_price-fees_operation
        self.add_to_transaction_history('SELL', transaction_time, ticker, quantity, ticker_price)
        del self.actifs[ticker]

    @staticmethod
    def calculate_transaction_fees(quantity, ticker_price):
        fees_transaction = 0.001
        return quantity * ticker_price * fees_transaction

    def add_to_transaction_history(self,
                                   transaction_type,
                                   transaction_time,
                                   ticker, quantity,
                                   ticker_price):
        cash_cost = (quantity * ticker_price * (-1 if transaction_type == 'BUY' else 1)
                     - self.calculate_transaction_fees(quantity, ticker_price))
        transaction = {
            'Time' : transaction_time,
            'Type' : transaction_type,
            'Ticker' : ticker,
            'Quantity' : quantity,
            'Ticker price' : ticker_price,
            'Cash cost' : round(cash_cost, 2)
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

    def save(self, start_date, cash, assets_value):
        with open(r'bot\results\results.txt', 'a', encoding='utf-8') as f:
            f.write(f"Start Date : {start_date} |"
                    f"End Date : {datetime.datetime.now()} |"
                    f"Cash : {cash} |",
                    f"Assets_value : {assets_value} |",
                    f"Portfolio_change : {((cash+assets_value)/self.cash_at_start - 1)*100:.2f}%\n")

    def message_api(self, _, source):
        message : dict = json.loads(source)
        if 'error' in message:
            print(message['error']['msg'])
        else:
            self.list_prices = message["result"]

    def fetch_prices(self, timestamp = None):
        if self.parameters.type_ in ['PROD', 'TEST']:
            try:
                binance_get_price_api_client = SpotWebsocketAPIClient(on_message=self.message_api)
                if self.actifs:
                    binance_get_price_api_client.ticker_price(symbols=list(self.actifs.keys()))
                time.sleep(10)
                binance_get_price_api_client.stop()
            except Exception as e:
                print(f"Prix non récupéré : {e}")
        else:
            dict_global_time = self.get_dict_global_times()
            t1 = time.time()
            self.list_prices = [
                binary_search_get_price(
                    dict_global_time,
                    crypto,
                    timestamp
                ) for crypto in self.actifs.keys()
            ]
            print("temps pour binary search", time.time()-t1)

    @staticmethod
    def get_dict_global_times():
        from bot.trading.backtesting import Datas
        return Datas.dict_global

    def get_assets_value(self, timestamp = None):
        self.fetch_prices(timestamp)
        assets_value = 0
        for dict_symbol_price in self.list_prices:
            try:#TO MODIFY (self.list_prices, self.actifs needs to be merge maybe)
                assets_value += self.actifs[dict_symbol_price['symbol']]['quantity'] * float(dict_symbol_price['price'])
            except KeyError:
                assets_value += 0
        return assets_value

    def evaluate_portfolio_value(self, timestamp = None, save_to_file = True, verbose = True):
        assets_value = self.get_assets_value(timestamp)
        portfolio_value = self.cash+assets_value
        if verbose:
            print('---------------')
            print(f'Valeur du cash : {self.cash}')
            print(f'Valeur des actifs : {assets_value}')
            print(f'Valeur du Portefeuille : {portfolio_value}')
            print('---------------')
            self.portfolio_values.append(portfolio_value)
        if save_to_file:
            self.save(self.creation_date, self.cash, assets_value)
        return portfolio_value

    def generate_stats_for_storage(self, timestamp = None):
        self.evaluate_portfolio_value(timestamp)
        portfolio_perf = (self.portfolio_values[-1]/self.cash_at_start - 1)*100
        start_date = None
        end_date = None
        if self.parameters.type_ in ['PROD', 'TEST']:
            start_date = self.creation_date
            end_date = datetime.datetime.now()
        elif self.parameters.type_ == 'BACKTEST':
            start_date = self.parameters.start_date
            end_date = self.parameters.end_date

        nouvelle_ligne = {
                            "Type": 'NEW'+self.parameters.type_,
                            "StartDate": start_date,
                            "EndDate": end_date,
                            "Volume Limit": self.parameters.limits['volume'],
                            "Variation Limit": self.parameters.limits['variation'],
                            "NbOfTrades Limit": self.parameters.limits['nbOfTrades'],
                            "Stop Loss Percentage": self.parameters.stop_loss_price,
                            "Portfolio Values":self.portfolio_values,
                            "BTC Perf":'',
                            "Portfolio Perf": f"{portfolio_perf:.2f}%",
                        }
        df_nouvelle = pd.DataFrame([nouvelle_ligne])
        df_nouvelle.to_csv(r'bot\results\Storage_stats.csv', mode='a', index = False, header=False)

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

    volumes = [1, 1.3, 1.5, 1.8]
    variations = [1, 1.3, 1.5, 1.8]
    nb_of_trades = [1, 2]
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
