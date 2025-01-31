import time
import logging
import pprint
import json
import datetime
import pandas as pd
import threading
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from binance.spot import Spot as Client
from binance.lib.utils import config_logging
from bot.strategy.base_strategy import Strategy
from bot.utils.helpers import Portfolio, Parameters, periodic_sleep
from config import get_api_keys
from bot.data.data_fetcher import Kline, RollingWindow
import collections
config_logging(logging, logging.INFO)

class WebsocketManager:
    def __init__(self, isTestMode : bool):
        self.isTestMode = isTestMode
        self.api_key, self.api_secret = get_api_keys(environnement=isTestMode)
        self.message_handler : MessageHandler = MessageHandler(None)
        self.ws_api_client =  self.createWebsocketAPI()
        self.client = self.createClient()
        self.listenKey = self.get_listen_key()
        self.ws_user_data = self.createWebsocketStream('userData')
        self.ws_client_kline3m = self.createWebsocketStream('kline3m')
        self.ws_client_rolling1h = self.createWebsocketStream('rolling1h')

    def createClient(self):
        if self.isTestMode:
            base_url_client = "https://testnet.binance.vision"
        else:
            base_url_client = 'https://api.binance.com'
        return Client(self.api_key, base_url=base_url_client)

    def createWebsocketAPI(self):
        if self.isTestMode:
            stream_url = "wss://ws-api.testnet.binance.vision/ws-api/v3"
        else:
            stream_url = "wss://ws-api.binance.com:443/ws-api/v3"
        return SpotWebsocketAPIClient(stream_url=stream_url,
                                        api_key=self.api_key,
                                        api_secret=self.api_secret,
                                        on_message=self.message_handler.message_handler_orders)

    def get_listen_key(self):
        response = self.client.new_listen_key()
        listenKey = response["listenKey"]
        return listenKey

    def createWebsocketStream(self, on_message_stream_name : str):
        if self.isTestMode:
            stream_url = "wss://stream.testnet.binance.vision"
        else:
            stream_url = "wss://stream.binance.com:9443"
        if on_message_stream_name == 'userData':
            logging.info("Receving listen key : {}".format(self.listenKey))
            ws_user_data = SpotWebsocketStreamClient(stream_url=stream_url, on_message=self.message_handler.messageUserData)
            ws_user_data.user_data(listen_key=self.listenKey)
            return ws_user_data
        elif on_message_stream_name == 'kline3m':
            stream_url = "wss://stream.binance.com:9443"
            return SpotWebsocketStreamClient(stream_url=stream_url, on_message=self.message_handler.messageProcessingkline3m, is_combined=True)
        elif on_message_stream_name == 'rolling1h':
            stream_url = "wss://stream.binance.com:9443"
            return SpotWebsocketStreamClient(stream_url=stream_url, on_message=self.message_handler.messageProcessingRolling1h, is_combined=True)
        else:
            raise ValueError('Wrong parameter')


class PumpDump(Strategy):
    def __init__(self, portfolio : Portfolio, parameters : Parameters, durationTime : int, isTestMode : bool):
        if durationTime <= 0:
            raise ValueError("durationTime must be positive.")
        if not isinstance(isTestMode, bool):
            raise TypeError("isTestMode must be a boolean.")
        super().__init__(durationTime, isTestMode)
        
        self.tickersPairs = self.getTickerPairs()
        self.parameters = parameters
        self.dataframe_storage = self.create_dataframe_for_storage()
        self.websocketManager = WebsocketManager(isTestMode)
        self.portfolio = portfolio

    def getTickerTickSize(self, ticker):
        resp = self.websocketManager.client.exchange_info()['symbols']
        for elem in resp:
            if elem['symbol'] == ticker:
                return float(elem['filters'][1]['stepSize']), float(elem['filters'][0]['tickSize'])

    @staticmethod
    def getTickerPairs():
        with open(r"C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading\src\strategy\strat2\list_all_pairs.txt", 'r') as f:
            listTickers = f.read().splitlines()
        return listTickers

    def define_stop_losses(self, ticker, entry_price):

        stepSize, tickSize = self.getTickerTickSize(ticker)
        self.parameters.ticker_bought_actual_max_price[ticker] = {'entry_price' : entry_price,
                                                                'stepSize' : stepSize,
                                                                'tickSize' : tickSize}
        stopLossPrice = round((self.parameters.stop_loss_price*entry_price//tickSize)*tickSize,8)
        quantity_bought = str(round((self.portfolio.actifs[ticker]['quantity']//stepSize)*stepSize,8))
        #logging.debug("Entry_price : ", entry_price, "StopPrice : ", stopLossPrice)
        self.websocketManager.ws_api_client.new_order(symbol=ticker,
                                                        side="SELL",
                                                        type="STOP_LOSS",
                                                        quantity=quantity_bought,
                                                        stopPrice=stopLossPrice,
                                                        newClientOrderId=f'stop_loss_{ticker}',
                                                        newOrderRespType="FULL")


    def start(self):
        list_ticker_kline3m = [ticker.lower()+'@kline_3m' for ticker in self.tickersPairs]
        list_ticker_rolling1h = [ticker.lower()+'@ticker_1h' for ticker in self.tickersPairs]

        self.websocketManager.ws_client_kline3m.subscribe(stream = list_ticker_kline3m)
        self.websocketManager.ws_client_rolling1h.subscribe(stream = list_ticker_rolling1h)

        logging.info('start sleep')
        self.periodic_sleep(self.durationTime, 300)
        self.stop()

    @staticmethod
    def create_dataframe_for_storage():
        multi_columns = pd.MultiIndex.from_tuples([('Variation', '3m'), ('Variation', '1h'),
                                            ('Volume', '3m'), ('Volume', '1h'), ('NbOfTrades', '3m'),
                                            ('NbOfTrades', '1h'), ('Price is going up', None)])
        dataframe_storage = pd.DataFrame(columns = multi_columns)
        return dataframe_storage

    def periodic_sleep(self, total_duration, interval):
        elapsed_time = 0

        while elapsed_time < total_duration:
            time.sleep(interval)
            elapsed_time += interval

            remaining_time = total_duration - elapsed_time
            print(f"Temps écoulé : {elapsed_time} secondes. Temps restant : {remaining_time} secondes.")
            self.screenshot()

    def screenshot(self):
        print('-------------------')
        print(f'Crypto bought : {self.parameters.crypto_bought}')
        print('Transaction history :')
        print(self.portfolio.df_transaction_history)
        self.portfolio.evaluate_portfolio_value(verbose=True)

    def stop(self):
        logging.info(self.portfolio.evaluate_portfolio_value())
        logging.info("unsubscribe user data")
        self.websocketManager.ws_user_data.user_data(self.websocketManager.listenKey, action=SpotWebsocketStreamClient.ACTION_UNSUBSCRIBE)
        self.websocketManager.ws_user_data.stop()
        self.websocketManager.ws_client_kline3m.stop()
        self.websocketManager.ws_client_rolling1h.stop()

        logging.info('writing in excel')
        logging.info(self.portfolio.actifs)
        self.dataframe_storage.to_excel("Storage_stats.xlsx")
        self.portfolio.df_transaction_history.to_excel("Transaction History.xlsx")

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

    def message_handler_open_orders(self, _, source):
        list_crypto = []
        message = json.loads(source)
        result = message['result']
        for crypto in result:
            list_crypto.append(crypto['symbol'])
        for crypto in list_crypto:
            self.websocketManager.client.cancel_open_orders(symbol=crypto)

    def get_open_orders_and_cancel(self):
        if self.isTestMode:
            stream_url="wss://ws-api.testnet.binance.vision/ws-api/v3"
        else:
            stream_url = "wss://ws-api.binance.com:443/ws-api/v3"
        
        client = SpotWebsocketAPIClient(stream_url=stream_url,
                                        api_key=self.api_key,
                                        api_secret=self.api_secret,
                                        on_message=self.websocketManager.message_handler.message_handler_open_orders)
        client.get_open_orders()
        time.sleep(15)
        client.stop()

    def take_decision(self, k):
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
        if pump_detected:
            if not self.isTestMode:
                cash_used = '5.5'
            else:
                cash_used = '10'
            if datetime.datetime.now().minute % 15 == 0:
                if not self.isTestMode:
                    cash_used = '5.5'
                else:
                    cash_used = '50'
            self.parameters.crypto_bought.append(ticker)
            try:
                self.portfolio.check_buy_sell('BUY', ticker, float(cash_used)/close_price, close_price)
                self.websocketManager.ws_api_client.new_order(symbol=ticker,
                                                            side="BUY",
                                                            type="MARKET",
                                                            quoteOrderQty=cash_used,
                                                            newClientOrderId=f'buy_market_{ticker}',
                                                            newOrderRespType="FULL")
            except AssertionError:
                print(f'Order to buy {ticker} was not send, not enough cash on portfolio.')

            #print(f'TICKER : {ticker}')
            #print(f"Variation 3m : {self.pump_dump_instance.dataframe_storage.loc[ticker, ('Variation', '3m')]} | Volume 3m : {self.pump_dump_instance.dataframe_storage.loc[ticker, ('Volume', '3m')]}")
            #print(f"Variation 2h : {self.pump_dump_instance.dataframe_storage.loc[ticker, ('Variation', '2h')]} | Volume 2h : {self.pump_dump_instance.dataframe_storage.loc[ticker, ('Volume', '2h')]}")

        if ticker in self.parameters.ticker_bought_actual_max_price:
            #print(ticker, close_price, self.pump_dump_instance.parameters.ticker_bought_actual_max_price[ticker]['entry_price'])
            if close_price > self.parameters.ticker_bought_actual_max_price[ticker]['entry_price']:

                self.parameters.ticker_bought_actual_max_price[ticker]['entry_price'] = close_price
                stepSize = self.parameters.ticker_bought_actual_max_price[ticker]['stepSize']
                tickSize = self.parameters.ticker_bought_actual_max_price[ticker]['tickSize']

                quantity_bought = str(round((self.portfolio.actifs[ticker]['quantity']//stepSize)*stepSize,8))
                newStopLossPrice = round((self.parameters.stop_loss_price*close_price//tickSize)*tickSize,8)

                self.websocketManager.ws_api_client.cancel_replace_order(ticker,
                                                                            side='SELL',
                                                                            cancelReplaceMode="ALLOW_FAILURE",
                                                                            cancelOrigClientOrderId = f'stop_loss_{ticker}',
                                                                            newClientOrderId=f"stop_loss_{ticker}",
                                                                            type="STOP_LOSS",
                                                                            quantity=quantity_bought,
                                                                            stopPrice=newStopLossPrice,
                                                                            newOrderRespType="FULL")

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

class MessageHandler:
    def __init__(self, pump_and_dump : PumpDump):
        self.pump_and_dump = pump_and_dump

    def set_pump_and_dump(self, pump_and_dump):
        self.pump_and_dump = pump_and_dump
    
    def messageProcessingRolling1h(self, _, source):
        message : dict = json.loads(source)

        if message.get('result',0) == None:
            print(f'Connection open at {datetime.datetime.now()} with websocket rolling windows 1hour.')
            return

        self.pump_and_dump.update_parameters('1h', message['data'])
        
        """ rolling_window = RollingWindow(ticker=data['s'], open_price=float(data['o']), high_price=float(data['h']),
                                        low_price=float(data['l']), close_price=float(data['c']), volume=float(data['v']),
                                        num_trades=data['n']) """

    def messageProcessingkline3m(self, _, source):
        
        message : dict = json.loads(source)
        if message.get('result',0) == None:
            print(f'Connection open at {datetime.datetime.now()} with websocket kline 3minutes.')
            return
        k = message['data']['k']
        print(k)
        self.pump_and_dump.take_decision(k)
        self.pump_and_dump.update_parameters('3m', k)

    def message_handler_open_orders(self, _, source):
        """
        Get existing open orders to cancel them.
        """
        list_crypto = []
        message = json.loads(source)
        result = message['result']
        for crypto in result:
            list_crypto.append(crypto['symbol'])
        if list_crypto:
            self.pump_and_dump.websocketManager.ws_api_client.cancel_open_orders(symbol=list_crypto)
    
    def message_handler_orders(self, _, source):
        message : dict = json.loads(source)
        if message.get('result', 0) == None:
            return
        if 'error' in message:
            error : dict = message['error']
            logging.debug('Code : ', error['code'])
            logging.debug('Message : ', error['msg'])
            logging.debug(f'data_error : {error.get('data', None)}')
            return
        result = message.get("result")

        if 'cancelResult' in result:
            if result['cancelResult'] == 'SUCCESS' and result['newOrderResult'] == 'SUCCESS':
                logging.debug('Order canceled successfully.')
            pass
        elif result['status'] == 'FILLED':
            clientOrderId = result['clientOrderId']
            executedBaseQty = float(result['cummulativeQuoteQty'])
            executedQty = float(result['executedQty'])
            workingTimeOrder = datetime.datetime.fromtimestamp(int(result['workingTime'])/1000)
            side = result['side']
            fills = result['fills'][0]
            excuted_price = float(fills['price'])
            ticker = result['symbol']
            commission = float(fills['commission'])
            commissionAsset = fills['commissionAsset']

        elif result['status'] == 'NEW':
            pass
            #pprint.pprint(message)
        else:
            pprint.pprint(message)
            pprint.pprint(result['status'])
        pass

    def messageUserData(self, _, source):
        message : dict = json.loads(source)
        if message.get('e', None) == 'outboundAccountPosition': #contient la balance avec l'asset qui a changé uniquement
            pass
        elif message.get('e', None) == 'executionReport':
            side = message['S']
            if message.get('x', None) == 'CANCELED' and side == 'SELL':
                logging.debug("OLD STOP LOSS CANCELED")
                logging.debug(f'Ticker {side} | Stop_loss : {message['P']}')
                logging.debug('---------------')
            
            elif message.get('x', None) == 'NEW':
                if side == 'SELL':
                    logging.debug("NEW STOP LOSS SEND")
                elif side == 'BUY':
                    logging.debug("NEW BUY ORDER SEND")
                logging.debug(f'Ticker {message['s']} | Stop_loss : {message['P']}')
                logging.debug('---------------')
            
            elif message.get('x', None) == 'TRADE':
                logging.debug(f'{side} DONE')
                if side == 'BUY':
                    logging.debug(f"Ticker : {message['s']} | Prix d'achat : {message['L']}")
                elif side == 'SELL':
                    logging.debug(f'Ticker : {message['s']} | USDT en plus : {message['Z']} | Au prix : {message['L']}')
                logging.debug('---------------')
                workingTimeOrder = datetime.datetime.fromtimestamp(int(message['T'])/1000)
                ticker = message['s']
                executedQty = float(message['l'])
                excuted_price = float(message['L'])
                self.pump_and_dump.portfolio.transaction_order(side, 
                                                                workingTimeOrder, 
                                                                ticker,
                                                                executedQty, 
                                                                excuted_price)
                if side == 'BUY':
                    threading.Thread(target=self.pump_and_dump.define_stop_losses, args = (ticker, excuted_price)).start()
                elif side == 'SELL':
                    del self.pump_and_dump.portfolio.actifs[message['s']]