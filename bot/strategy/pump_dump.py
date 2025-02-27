import datetime
import pandas as pd
from bot.utils.helpers import Portfolio, Parameters
from bot.strategy.base_strategy import Strategy
from bot.trading.backtesting import BackTesting
from bot.trading.live_trading import LiveTrading


class PumpDump(Strategy):
    def __init__(self, parameters : Parameters,  portfolio : Portfolio, durationTime : int, isTestMode : str, startDate, endDate):
        if durationTime <= 0:
            raise ValueError("durationTime must be positive.")
        if not isinstance(isTestMode, str):
            raise TypeError("isTestMode must be a string.")
        super().__init__(durationTime, isTestMode)

        self.tickersPairs = self.getTickerPairs()
        self.parameters = parameters
        self.dataframe_storage = self.create_dataframe_for_storage()
        self.startDate = startDate
        self.endDate = endDate
        if isTestMode in ['TEST', 'PROD']:
            self.tradingManager = LiveTrading(isTestMode, portfolio, durationTime, self.tickersPairs)
        else:
            self.tradingManager = BackTesting(isTestMode, portfolio, durationTime, self.tickersPairs, startDate, endDate)

    @staticmethod
    def getTickerPairs():
        with open(r"C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading\bot\data\list_all_pairs.txt", 'r') as f:
            listTickers = f.read().splitlines()
        return listTickers

    def define_stop_losses(self, ticker, entry_price):
        stepSize, tickSize = self.tradingManager.getTickerTickSize(ticker)
        self.parameters.ticker_bought_actual_max_price[ticker] = {'entry_price' : entry_price,
                                                                'stepSize' : stepSize,
                                                                'tickSize' : tickSize}
        stopLossPrice = round((self.parameters.stop_loss_price*entry_price//tickSize)*tickSize,8)
        quantity_bought = str(round((self.tradingManager.portfolio.actifs[ticker]['quantity']//stepSize)*stepSize,8))
        print("Entry_price : ", entry_price, "StopPrice : ", stopLossPrice)
        self.tradingManager.place_stop_loss(ticker, quantity_bought, stopLossPrice)

    @staticmethod
    def create_dataframe_for_storage():
        multi_columns = pd.MultiIndex.from_tuples([('Variation', '3m'), ('Variation', '1h'),
                                            ('Volume', '3m'), ('Volume', '1h'), ('NbOfTrades', '3m'),
                                            ('NbOfTrades', '1h'), ('Price is going up', None)])
        dataframe_storage = pd.DataFrame(columns = multi_columns)
        return dataframe_storage

    def detect_pump(self, dataframe_storage, ticker, limits, crypto_bought):
        if ticker in crypto_bought:
            return False
        variation_condition = (limits['variation']*dataframe_storage.loc[ticker,('Variation', '3m')] > 
                                dataframe_storage.loc[ticker,('Variation', '1h')])

        volume_condition = (limits['volume']*dataframe_storage.loc[ticker,('Volume', '3m')] > 
                            dataframe_storage.loc[ticker,('Volume', '1h')])
        nb_of_trades_condition = (limits['nbOfTrades']*dataframe_storage.loc[ticker,('NbOfTrades', '3m')] > 
                                dataframe_storage.loc[ticker,('NbOfTrades', '1h')])
        price_is_going_up_condition = dataframe_storage.loc[ticker, ('Price is going up', '')]
        return variation_condition and volume_condition and price_is_going_up_condition and nb_of_trades_condition

    def take_decision(self, data):
        k = data['k']
        ticker = k['s']
        variation = float(k['h']) - float(k['l'])
        volume = float(k['v'])
        close_price = float(k['c'])
        price_is_going_up = bool(close_price > float(k['o']))
        self.dataframe_storage.loc[ticker, ('Variation', '3m')] = variation
        self.dataframe_storage.loc[ticker, ('Volume', '3m')] = volume
        self.dataframe_storage.loc[ticker, ('Price is going up', '')] = price_is_going_up
        pump_detected = self.detect_pump(self.dataframe_storage,
                                        ticker,
                                        self.parameters.limits,
                                        self.parameters.crypto_bought)
        if isinstance(self.tradingManager, LiveTrading):
            now = datetime.datetime.now()
        elif isinstance(self.tradingManager, BackTesting):
            now=datetime.datetime.fromtimestamp(int(data['E'])/1000)
        if pump_detected:
            cash_used = '10'
            if now.minute % 15 == 0:
                cash_used = '30'
            self.parameters.crypto_bought.append(ticker)
            try:
                self.tradingManager.portfolio.check_buy_sell('BUY', ticker, float(cash_used)/close_price, close_price)
                self.tradingManager.buy(ticker, float(cash_used), close_price, data['E'])
            except AssertionError:
                print(f'Order to buy {ticker} was not send, not enough cash on portfolio.')

            #print(f'TICKER : {ticker}')
            #print(f"Variation 3m : {self.pump_dump_instance.dataframe_storage.loc[ticker, ('Variation', '3m')]} | Volume 3m : {self.pump_dump_instance.dataframe_storage.loc[ticker, ('Volume', '3m')]}")
            #print(f"Variation 2h : {self.pump_dump_instance.dataframe_storage.loc[ticker, ('Variation', '2h')]} | Volume 2h : {self.pump_dump_instance.dataframe_storage.loc[ticker, ('Volume', '2h')]}")

        if ticker in self.tradingManager.portfolio.actifs and ticker in self.parameters.ticker_bought_actual_max_price:#Les deux dict doivent être fusionnés
            #print(ticker, close_price, self.parameters.ticker_bought_actual_max_price[ticker]['entry_price'])
            if close_price > self.parameters.ticker_bought_actual_max_price[ticker]['entry_price']:

                self.parameters.ticker_bought_actual_max_price[ticker]['entry_price'] = close_price
                stepSize = self.parameters.ticker_bought_actual_max_price[ticker]['stepSize']
                tickSize = self.parameters.ticker_bought_actual_max_price[ticker]['tickSize']

                quantity_bought = str(round((self.tradingManager.portfolio.actifs[ticker]['quantity']//stepSize)*stepSize,8))
                newStopLossPrice = round((self.parameters.stop_loss_price*close_price//tickSize)*tickSize,8)
                #print(ticker, newStopLossPrice)
                self.tradingManager.cancel_replace(ticker, quantity_bought, newStopLossPrice)

    def update_parameters(self, websocket_stream, data):
        ticker = data['s']
        variation = float(data['h'])-float(data['l'])
        volume = float(data['v'])
        nbOfTrades = data['n']
        self.dataframe_storage.loc[ticker, ('Variation', websocket_stream)] = variation
        self.dataframe_storage.loc[ticker, ('Volume', websocket_stream)] = volume
        self.dataframe_storage.loc[ticker, ('NbOfTrades', websocket_stream)] = nbOfTrades
        #print(ticker +' ' + websocket_stream+ ' :',  nbOfTrades)
        if websocket_stream == '3m':
            price_is_going_up = bool(float(data['c']) > float(data['o']))
            self.dataframe_storage.loc[ticker, ('Price is going up', '')] = price_is_going_up
