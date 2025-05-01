import os
import datetime
import json
import time
from collections import defaultdict
from binance.spot import Spot as Client
from bot.trading.base_trading import TradingManager
from bot.strategy.base_strategy import Strategy

class BackTesting(TradingManager):
    def __init__(self, parameters, portfolio, simulation_saver):
        super().__init__(parameters,  portfolio, simulation_saver)
        self.list_tickers = parameters.list_tickers
        self.datas = Datas(parameters)
        self.orders = {}

    def set_pump_and_dump(self, pump_and_dump):
        self.pump_and_dump = pump_and_dump

    def message_processing_rolling_back_testing(self, message):
        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with rolling windows 1hour.')
            return None
        data = message['data']
        self.datas.strategy.update_parameters('1h', data)
        return None

    def get_ticker_tick_size(self, ticker):
        client = Client(self.api_key, base_url='https://api.binance.com')
        resp = client.exchange_info()['symbols']
        for elem in resp:
            if elem['symbol'] == ticker:
                return float(elem['filters'][1]['stepSize']), float(elem['filters'][0]['tickSize'])
        return None

    def message_processing_kline_back_testing(self, message):
        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with websocket kline.')
            return None
        data = message['data']
        ticker :str = data['k']['s']
        self.datas.strategy.update_parameters(self.parameters.kline_type, data['k'])
        self.datas.strategy.take_decision(data)

        matching_key = next((key for key in self.orders.keys() if key.startswith(ticker[:-4])), None)
        k = data['k']['s']
        if matching_key:
            self.check_stop_losses(matching_key, data)
        return None
    
        #{"stream": "1000catusdc@miniTicker", 
        # "data": {"e": "24hrMiniTicker", "E": 1745921398902, "s": "1000CATUSDC", 
        # "c": "0.00714000", "o": "0.00728000", "h": "0.00750000", "l": "0.00685000", 
        # "v": "14210343.70000000", "q": "102270.93361700"}}

    def message_processing_mini_ticker_back_testing(self, message):
        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with mini ticker.')
            return None
        data = message['data']
        self.datas.strategy.update_parameters(None, data)
        return None

    def start(self):
        print(len(self.datas.dict_time))
        assert len(self.datas.dict_time.keys()) > 0, "empty event list, input dates can be wrong"

        time_reference = list(self.datas.dict_time.keys())[0]
        for current_time, list_events in self.datas.dict_time.items():
            if current_time - time_reference >= datetime.timedelta(minutes=5):
                self.screenshot(current_time)
                time_reference = current_time
            for event in list_events:
                if 'kline' in event['stream']:
                    self.message_processing_kline_back_testing(event)
                elif 'ticker' in event['stream']:
                    self.message_processing_rolling_back_testing(event)
                elif 'miniTicker' in event['stream']:
                    self.message_processing_mini_ticker_back_testing(event)

        last_time = list(self.datas.dict_time.keys())[-1]
        self.portfolio.evaluate_portfolio_value(last_time)
        self.stop()

    def stop(self):
        with open(r"bot\results\TradesLogFile.txt", "a", encoding='utf-8') as f:
            f.write("\n")
            self.portfolio.df_transaction_history.to_string(f, index=True)
            f.write("\n\n")

    def buy(self, ticker, quote_order_qty, excecuted_price=0, time_=0):
        executed_qty = quote_order_qty/excecuted_price
        step_size = self.get_ticker_tick_size(ticker)[0]
        executed_qty = round((executed_qty//step_size)*step_size,8)
        working_time_order = datetime.datetime.fromtimestamp(int(time_)/1000)
        self.portfolio.transaction_order('BUY',
                                        working_time_order,
                                        ticker,
                                        executed_qty,
                                        excecuted_price)
        self.datas.strategy.define_stop_losses(ticker, excecuted_price)
        print(self.portfolio.df_transaction_history)

    def cancel_replace(self, pair : str, quantity_bought, new_stop_loss_price):
        self.place_stop_loss(pair, quantity_bought, new_stop_loss_price)
    
    def place_stop_loss(self, pair, quantity_bought, stop_loss_price):
        self.orders[pair] = {"quantity" : float(quantity_bought),
                               'stopLossPrice' : stop_loss_price}

    def check_stop_losses(self, ticker, data):
        working_time_order = datetime.datetime.fromtimestamp(int(data['E'])/1000)

        current_price = self.datas.strategy.prices[ticker][-1]
        if self.orders[ticker]['stopLossPrice'] >= current_price: #stoplossPrice is incorrect (in usdt when it needs to be in zrxbtc)
            try:
                self.portfolio.transaction_order('SELL',
                                                working_time_order,
                                                ticker,
                                                self.orders[ticker]['quantity'],
                                                current_price)
                del self.orders[ticker]
            except ValueError:
                return
            print(self.portfolio.df_transaction_history)

class Datas:
    dict_global = {}
    path_ = r'bot\data\historical_datas'
    path_files_klines = []
    path_files_rolling = []
    path_files_mini_ticker = []
    def __init__(self, parameters, strategy = None):
        self.list_tickers = parameters.list_tickers
        self.strategy = strategy
        self.start_date = parameters.start_date
        self.end_date = parameters.end_date
        if not Datas.path_files_klines:
            Datas.path_files_klines = [os.path.join(Datas.path_,
                                                    f'kline{parameters.kline_type}',
                                                    f'{ticker}.txt') for ticker in parameters.list_tickers if ticker.endswith('USDT')]
        if not Datas.path_files_rolling:
            Datas.path_files_rolling = [os.path.join(Datas.path_,
                                                     'historical_window_1h',
                                                     f'{ticker}.txt') for ticker in parameters.list_tickers if ticker.endswith('USDT')]
        if not Datas.path_files_mini_ticker:
            Datas.path_files_mini_ticker = [os.path.join(Datas.path_,
                                                     'mini_ticker',
                                                     f'{ticker}.txt') for ticker in parameters.list_tickers if not ticker.endswith('USDT')]
        if not type(self).dict_global:
            type(self).create_global_dict_time(self.start_date, self.end_date)
        self.dict_time = type(self).dict_global

    @classmethod
    def create_global_dict_time(cls, start_date, end_date):
        cls.dict_global = cls.fill_dict_time(start_date, end_date)

    def set_strategy(self, strategy : Strategy):
        self.strategy = strategy

    @classmethod
    def fill_dict_time(cls, start_date, end_date):
        t1 = time.time()
        dict_time = defaultdict(list)
        for path in cls.path_files_klines:
            try:
                with open(path, 'r', encoding="utf-8") as f:
                    for line in f:
                        try:
                            message = json.loads(line)
                            time_ = datetime.datetime.fromtimestamp(int(message['data']["E"])/1000)
                            if time_ > end_date:
                                break
                            if start_date <= time_:
                                dict_time[time_].append(message)
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                pass
        for path in cls.path_files_rolling:
            try:
                with open(path, 'r', encoding="utf-8") as f:
                    for line in f:
                        try:
                            message = json.loads(line)
                            time_ = datetime.datetime.fromtimestamp(int(message["data"]['E'])/1000)
                            if time_ > end_date:
                                break
                            if start_date <= time_ <= end_date:
                                dict_time[time_].append(message)
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                pass
        for path in cls.path_files_mini_ticker:
            try:
                with open(path, 'r', encoding="utf-8") as f:
                    for line in f:
                        try:
                            message = json.loads(line)
                            time_ = datetime.datetime.fromtimestamp(int(message["data"]['E'])/1000)
                            if time_ > end_date:
                                break
                            if start_date <= time_ <= end_date:
                                dict_time[time_].append(message)
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                pass

        sorted_items = dict(sorted(dict_time.items(), key=lambda item: item[0]))
        t2 = time.time()
        print(len(sorted_items))
        print("Temps pris pour former le dicitonnaire de taille", t2-t1)
        cls.dict_global = sorted_items
        return sorted_items