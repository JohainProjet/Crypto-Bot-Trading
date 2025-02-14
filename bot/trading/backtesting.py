import os
import datetime
import json
from binance.spot import Spot as Client
from bot.trading.base_trading import TradingManager
from bot.strategy.base_strategy import Strategy
from collections import defaultdict

class BackTesting(TradingManager):
    def __init__(self, isTestMode, portfolio, durationTime, listTickers, startDate, endDate):
        super().__init__(isTestMode,  portfolio, durationTime)
        self.listTickers = listTickers
        self.datas = Datas(listTickers, startDate, endDate)
        self.orders = {}

    def set_pump_and_dump(self, pump_and_dump):
        self.pump_and_dump = pump_and_dump

    def messageProcessingRolling1hBackTesting(self, message):
        if message.get('result',0) == None:
            print(f'Connection open at {datetime.datetime.now()} with websocket rolling windows 1hour.')
            return
        self.datas.strategy.update_parameters('1h', message['data'])

    def getTickerTickSize(self, ticker):
        client = Client(self.api_key, base_url='https://api.binance.com')
        resp = client.exchange_info()['symbols']
        for elem in resp:
            if elem['symbol'] == ticker:
                return float(elem['filters'][1]['stepSize']), float(elem['filters'][0]['tickSize'])

    def messageProcessingkline3mBackTesting(self, message):
        if message.get('result',0) == None:
            print(f'Connection open at {datetime.datetime.now()} with websocket kline 3minutes.')
            return
        data = message['data']
        self.datas.strategy.take_decision(data)
        self.datas.strategy.update_parameters('3m', data['k'])
        if data['s'] in self.orders:
            self.check_stop_losses(data)
        
    def start(self):
        print(len(self.datas.dict_time))
        for time_, list_events in self.datas.dict_time.items():
            for event in list_events:
                if 'kline' in event['stream']:
                    self.messageProcessingkline3mBackTesting(event)
                elif 'ticker' in event['stream']:
                    self.messageProcessingRolling1hBackTesting(event)

    def stop(self):
        pass

    def buy(self, ticker, cash_used, excuted_price=0, time=0):
        executedQty = cash_used/excuted_price
        workingTimeOrder = datetime.datetime.fromtimestamp(int(time)/1000)
        self.portfolio.transaction_order('BUY',
                                        workingTimeOrder,
                                        ticker,
                                        executedQty,
                                        excuted_price)
        self.datas.strategy.define_stop_losses(ticker, excuted_price)
        print(self.portfolio.df_transaction_history)


    def cancel_replace(self, ticker, quantity_bought, newStopLossPrice):
        self.place_stop_loss(ticker, quantity_bought, newStopLossPrice)

    def place_stop_loss(self, ticker, quantity_bought, stopLossPrice):
        self.orders[ticker] = {"quantity" : float(quantity_bought),
                               'stopLossPrice' : stopLossPrice}

    def check_stop_losses(self, data):
        ticker = data['s']
        workingTimeOrder = datetime.datetime.fromtimestamp(int(data['E'])/1000)

        current_price = float(data['k']['c'])
        print(self.orders[ticker]['stopLossPrice'], current_price)
        if self.orders[ticker]['stopLossPrice'] >= current_price:
            try:
                self.portfolio.transaction_order('SELL',
                                                workingTimeOrder,
                                                ticker,
                                                self.orders[ticker]['quantity'],
                                                current_price)
                del self.orders[ticker]
            except ValueError:
                return
            
            print(self.portfolio.df_transaction_history)
    


class Datas:
    def __init__(self, listTickers, startDate, endDate, strategy = None):
        self.listTickers = listTickers
        self.strategy = strategy
        self.path = r'C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading\bot\data\historical_datas'
        self.path_files_klines = [os.path.join(self.path, 'kline3m', f'{ticker}.txt') for ticker in listTickers]
        self.path_files_rolling = [os.path.join(self.path, 'historical_window_1h', f'{ticker}.txt') for ticker in listTickers]
        self.startDate = startDate
        self.endDate = endDate
        self.dict_time = self.fill_dict_time()

    def set_strategy(self, strategy : Strategy):
        self.strategy = strategy

    def fill_dict_time(self):
        dict_time = defaultdict(list)
        for path in self.path_files_klines:
            try:
                with open(path, 'r') as f:
                    for line in f:
                        try:
                            message = json.loads(line)
                            time = datetime.datetime.fromtimestamp(int(message['data']["E"])/1000)
                            if self.startDate <= time <= self.endDate: 
                                dict_time[time].append(message)
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                pass
        for path in self.path_files_rolling:
            try:
                with open(path, 'r') as f:
                    for line in f:
                        try:
                            message = json.loads(line)
                            time = datetime.datetime.fromtimestamp(int(message["data"]['E'])/1000)
                            if self.startDate <= time <= self.endDate: 
                                dict_time[time].append(message)
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                pass
        
        sorted_items = dict(sorted(dict_time.items(), key=lambda item: item[0]))
        return sorted_items