import os
import time
import datetime
import json
import logging
import pprint
import threading
from binance.spot import Spot as Client
from bot.trading.base_trading import TradingManager
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from binance.spot import Spot as Client
from bot.strategy.base_strategy import Strategy

class LiveTrading(TradingManager):
    def __init__(self, isTestMode, portfolio, durationTime, listTickers):
        super().__init__(isTestMode, portfolio, durationTime)
        self.websocketManager = WebsocketManager(isTestMode, self.api_key, self.api_secret)
        self.listTickers = listTickers
    
    def getTickerTickSize(self, ticker):
        resp = self.websocketManager.client.exchange_info()['symbols']
        for elem in resp:
            if elem['symbol'] == ticker:
                return float(elem['filters'][1]['stepSize']), float(elem['filters'][0]['tickSize'])

    def start(self):
        list_ticker_kline3m = [ticker.lower()+'@kline_3m' for ticker in self.listTickers]
        list_ticker_rolling1h = [ticker.lower()+'@ticker_1h' for ticker in self.listTickers]

        self.websocketManager.ws_client_kline3m.subscribe(stream = list_ticker_kline3m)
        self.websocketManager.ws_client_rolling1h.subscribe(stream = list_ticker_rolling1h)

        logging.info('start sleep')
        self.periodic_sleep(self.durationTime, 300)
        self.stop()


    def stop(self):
        #Ici appeler portfolio evaluate
        logging.info("unsubscribe user data")
        self.portfolio.generate_stats_for_storage()
        self.websocketManager.ws_user_data.user_data(self.websocketManager.listenKey, action=SpotWebsocketStreamClient.ACTION_UNSUBSCRIBE)
        self.websocketManager.ws_user_data.stop()
        self.websocketManager.ws_client_kline3m.stop()
        self.websocketManager.ws_client_rolling1h.stop()
    
    def place_stop_loss(self, ticker, quantity_bought, stopLossPrice):
        self.websocketManager.ws_api_client.new_order(symbol=ticker,
                                                        side="SELL",
                                                        type="STOP_LOSS",
                                                        quantity=quantity_bought,
                                                        stopPrice=stopLossPrice,
                                                        newClientOrderId=f'stop_loss_{ticker}',
                                                        newOrderRespType="FULL")

    def get_open_orders_and_cancel(self):
        if self.isTestMode == 'TEST':
            stream_url="wss://ws-api.testnet.binance.vision/ws-api/v3"
        elif self.isTestMode == 'PROD':
            stream_url = "wss://ws-api.binance.com:443/ws-api/v3"
        
        client = SpotWebsocketAPIClient(stream_url=stream_url,
                                        api_key=self.api_key,
                                        api_secret=self.api_secret,
                                        on_message=self.websocketManager.message_handler.message_handler_open_orders)
        client.get_open_orders()
        time.sleep(15)
        client.stop()

    def buy(self, ticker, cash_used, excuted_price=0, time=0):
        return self.websocketManager.ws_api_client.new_order(symbol=ticker,
                                                            side="BUY",
                                                            type="MARKET",
                                                            quoteOrderQty=cash_used,
                                                            newClientOrderId=f'buy_market_{ticker}',
                                                            newOrderRespType="FULL")

    def cancel_replace(self, ticker, quantity_bought, newStopLossPrice):
        self.websocketManager.ws_api_client.cancel_replace_order(ticker,
                                                                    side='SELL',
                                                                    cancelReplaceMode="ALLOW_FAILURE",
                                                                    cancelOrigClientOrderId = f'stop_loss_{ticker}',
                                                                    newClientOrderId=f"stop_loss_{ticker}",
                                                                    type="STOP_LOSS",
                                                                    quantity=quantity_bought,
                                                                    stopPrice=newStopLossPrice,
                                                                    newOrderRespType="FULL")



class WebsocketManager:
    def __init__(self, isTestMode : str, api_key, api_secret):
        self.isTestMode = isTestMode
        self.api_key = api_key
        self.api_secret = api_secret
        self.message_handler : MessageHandler = MessageHandler(None)
        self.ws_api_client =  self.createWebsocketAPI()
        self.client = self.createClient()
        self.listenKey = self.get_listen_key()
        self.ws_user_data = self.createWebsocketStream('userData')
        self.ws_client_kline3m = self.createWebsocketStream('kline3m')
        self.ws_client_rolling1h = self.createWebsocketStream('rolling1h')

    def createClient(self):
        if self.isTestMode == 'TEST':
            base_url_client = "https://testnet.binance.vision"
        elif self.isTestMode == 'PROD' or self.isTestMode == 'BACKTEST':
            base_url_client = 'https://api.binance.com'
        return Client(self.api_key, base_url=base_url_client)

    def createWebsocketAPI(self):
        if self.isTestMode == 'TEST':
            stream_url = "wss://ws-api.testnet.binance.vision/ws-api/v3"
        elif self.isTestMode == 'PROD' or self.isTestMode == 'BACKTEST':
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
        if self.isTestMode == 'TEST':
            stream_url = "wss://stream.testnet.binance.vision"
        elif self.isTestMode == 'PROD' or self.isTestMode == 'BACKTEST':
            stream_url = "wss://stream.binance.com:9443"
        if on_message_stream_name == 'userData':
            logging.info("Receving listen key : {}".format(self.listenKey))
            ws_user_data = SpotWebsocketStreamClient(stream_url=stream_url, on_message=self.message_handler.messageUserData)
            ws_user_data.user_data(listen_key=self.listenKey)
            return ws_user_data
        elif on_message_stream_name == 'kline3m':
            #Si on utilise "wss://stream.testnet.binance.vision", on va récupérer les données du test net qui sont très peu représentatatives du marché
            stream_url = "wss://stream.binance.com:9443" 
            return SpotWebsocketStreamClient(stream_url=stream_url, on_message=self.message_handler.messageProcessingkline3m, is_combined=True)
        elif on_message_stream_name == 'rolling1h':
            #Si on utilise "wss://stream.testnet.binance.vision", on va récupérer les données du test net qui sont très peu représentatatives du marché
            stream_url = "wss://stream.binance.com:9443"
            return SpotWebsocketStreamClient(stream_url=stream_url, on_message=self.message_handler.messageProcessingRolling1h, is_combined=True)
        else:
            raise ValueError('Wrong parameter')


class MessageHandler:
    def __init__(self, pump_and_dump : Strategy):
        self.pump_and_dump = pump_and_dump

    def set_strategy(self, pump_and_dump : Strategy):
        self.pump_and_dump = pump_and_dump
    
    def messageProcessingRolling1h(self, _, source):
        message : dict = json.loads(source)

        if message.get('result',0) == None:
            print(f'Connection open at {datetime.datetime.now()} with websocket rolling windows 1hour.')
            return

        self.pump_and_dump.update_parameters('1h', message['data'])
        self.save_datas(message)

    def messageProcessingkline3m(self, _, source):
        message : dict = json.loads(source)
        if message.get('result',0) == None:
            print(f'Connection open at {datetime.datetime.now()} with websocket kline 3minutes.')
            return
        self.pump_and_dump.take_decision(message['data'])
        self.pump_and_dump.update_parameters('3m', message['data']['k'])
        self.save_datas(message)

    @staticmethod
    def save_datas(message):
        path = r'C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading\bot\data\historical_datas'
        if 'kline' in message['stream']:
            with open(os.path.join(path, 'kline3m', message['data']['s'] + '.txt'), 'a') as f:
                f.write(json.dumps(message)+ '\n')
        elif 'ticker' in message['stream']:
            with open(os.path.join(path, 'historical_window_1h', message['data']['s'] + '.txt'), 'a') as f:
                f.write(json.dumps(message) + '\n')

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
            self.pump_and_dump.tradingManager.websocketManager.ws_api_client.cancel_open_orders(symbol=list_crypto)

    """ def message_handler_open_orders(self, _, source):
        list_crypto = []
        message = json.loads(source)
        result = message['result']
        for crypto in result:
            list_crypto.append(crypto['symbol'])
        print(list_crypto)
        for crypto in list_crypto:
            self.pump_and_dump.tradingManager.websocketManager.client.cancel_open_orders(symbol=crypto) """
    
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
                ticker = message['s']
                excuted_price = float(message['L'])
                logging.debug(f'{side} DONE')
                if side == 'BUY':
                    logging.debug(f"Ticker : {message['s']} | Prix d'achat : {message['L']}")
                    threading.Thread(target=self.pump_and_dump.define_stop_losses, args = (ticker, excuted_price)).start()
                elif side == 'SELL':
                    logging.debug(f'Ticker : {message['s']} | USDT en plus : {message['Z']} | Au prix : {message['L']}')
                logging.debug('---------------')
                workingTimeOrder = datetime.datetime.fromtimestamp(int(message['T'])/1000)
                executedQty = float(message['l'])
                try:
                    print(side, workingTimeOrder, ticker, executedQty, excuted_price)
                    self.pump_and_dump.tradingManager.portfolio.transaction_order(side, 
                                                                                workingTimeOrder, 
                                                                                ticker,
                                                                                executedQty, 
                                                                                excuted_price)
                except:
                    print("error impossible de sell")
                    return