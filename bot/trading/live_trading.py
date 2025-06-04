import os
import time
import datetime
import json
import logging
import pprint
import threading
from binance.spot import Spot as Client
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from bot.trading.base_trading import TradingManager, SimulationSaver
from bot.strategy.base_strategy import Strategy

class LiveTrading(TradingManager):
    """Manages live trading operations using Binance's WebSocket API."""
    def __init__(self, parameters, portfolio, simulation_saver : SimulationSaver):
        super().__init__(parameters, portfolio, simulation_saver)
        self.websocket_manager = WebsocketManager(parameters, self.api_key, self.api_secret)
        self.parameters = parameters

    def get_ticker_tick_size(self, ticker):
        resp = self.websocket_manager.client.exchange_info()['symbols']
        for elem in resp:
            if elem['symbol'] == ticker:
                return float(elem['filters'][1]['stepSize']), float(elem['filters'][0]['tickSize'])
        return None

    def start(self):
        """Start the live trading session by subscribing to necessary WebSocket streams.
         * Rolling windows 1h 
         * Kline 1m
         * Mini ticker.
        """
        list_tickers : list[str] = self.parameters.GLOBAL_PARAMETERS["LIST_TICKERS"]
        list_ticker_kline = [ticker.lower()+f'@kline_1m' for ticker in list_tickers if ticker.endswith('USDT')]
        list_ticker_rolling1h = [ticker.lower()+'@ticker_1h' for ticker in list_tickers if ticker.endswith('USDT')]
        list_ticker_price_update = [ticker.lower()+'@miniTicker' for ticker in list_tickers if not ticker.endswith('USDT')]

        self.websocket_manager.ws_client_kline.subscribe(stream = list_ticker_kline)
        self.websocket_manager.ws_client_rolling_1h.subscribe(stream = list_ticker_rolling1h)
        self.websocket_manager.ws_client_mini_ticker.subscribe(stream = list_ticker_price_update)

        logging.info('start sleep')
        self.periodic_sleep(self.parameters.GLOBAL_PARAMETERS['DURATION_TIME'], 300)
        self.stop()

    def stop(self):
        logging.info("unsubscribe user data")
        self.portfolio.evaluate_portfolio_value()
        self.websocket_manager.ws_user_data.user_data(
            self.websocket_manager.listen_key,
            action=SpotWebsocketStreamClient.ACTION_UNSUBSCRIBE
        )
        self.websocket_manager.ws_user_data.stop()
        self.websocket_manager.ws_client_kline.stop()
        self.websocket_manager.ws_client_rolling_1h.stop()
        self.websocket_manager.ws_client_mini_ticker.stop()

    def place_stop_loss(self, ticker, quantity_bought, stop_loss_price):
        """ Places a stop loss order for a given ticker."""
        self.websocket_manager.ws_api_client.new_order(symbol=ticker,
                                                        side="SELL",
                                                        type="STOP_LOSS",
                                                        quantity=quantity_bought,
                                                        stopPrice=stop_loss_price,
                                                        newClientOrderId=f'stop_loss_{ticker}',
                                                        newOrderRespType="FULL")

    def get_open_orders_and_cancel(self)->None:
        """
        Retrieves all current open orders and cancels them.
        This is useful to ensure that no previous orders interfere with the current trading strategy. 
        Returns:
            None
        """
        program_type : str = self.parameters.GLOBAL_PARAMETERS['DEFAULT_PROGRAM_MODE']
        stream_url = None
        if program_type == 'TEST':
            stream_url="wss://ws-api.testnet.binance.vision/ws-api/v3"
        elif program_type == 'PROD':
            stream_url = "wss://ws-api.binance.com:443/ws-api/v3"

        client = SpotWebsocketAPIClient(
            stream_url=stream_url,
            api_key=self.api_key,
            api_secret=self.api_secret,
            on_message=self.websocket_manager.message_handler.message_handler_open_orders
        )
        client.get_open_orders()
        time.sleep(15)
        client.stop()
        return None

    def buy(self, ticker, quote_order_qty, excecuted_price=0, time_=0):
        """ Place a market order to buy a ticker with a specified quote order quantity."""
        return self.websocket_manager.ws_api_client.new_order(symbol=ticker,
                                                            side="BUY",
                                                            type="MARKET",
                                                            quoteOrderQty=quote_order_qty,
                                                            newClientOrderId=f'buy_market_{ticker}',
                                                            newOrderRespType="FULL")

    def cancel_replace(self, ticker, quantity_bought, new_stop_loss_price):
        """Cancel the existing stop loss order and replace it with a new one at a different price."""
        self.websocket_manager.ws_api_client.cancel_replace_order(
            ticker,
            side='SELL',
            cancelReplaceMode="ALLOW_FAILURE",
            cancelOrigClientOrderId = f'stop_loss_{ticker}',
            newClientOrderId=f"stop_loss_{ticker}",
            type="STOP_LOSS",
            quantity=quantity_bought,
            stopPrice=new_stop_loss_price,
            newOrderRespType="FULL"
        )


class WebsocketManager:
    """Manages WebSocket connections for live trading operations."""
    def __init__(self, parameters, api_key, api_secret):
        self.program_type = parameters.GLOBAL_PARAMETERS['DEFAULT_PROGRAM_MODE']
        self.api_key = api_key
        self.api_secret = api_secret
        self.message_handler : MessageHandler = MessageHandler(None)
        self.ws_api_client =  self.create_websocket_api()
        self.client = self.create_client()
        self.listen_key = self.get_listen_key()
        self.ws_user_data = self.create_websocket_stream('userData')
        self.ws_client_kline = self.create_websocket_stream('kline')
        self.ws_client_rolling_1h = self.create_websocket_stream('rolling1h')
        self.ws_client_mini_ticker = self.create_websocket_stream('mini_ticker')

    def create_client(self):
        base_url_client = None
        if self.program_type == 'TEST':
            base_url_client = "https://testnet.binance.vision"
        elif self.program_type in ['PROD', 'BACKTEST']:
            base_url_client = 'https://api.binance.com'
        return Client(self.api_key, base_url=base_url_client)

    def create_websocket_api(self):
        stream_url = None
        if self.program_type == 'TEST':
            stream_url = "wss://ws-api.testnet.binance.vision/ws-api/v3"
        elif self.program_type in ['PROD', 'BACKTEST']:
            stream_url = "wss://ws-api.binance.com:443/ws-api/v3"
        return SpotWebsocketAPIClient(stream_url=stream_url,
                                        api_key=self.api_key,
                                        api_secret=self.api_secret,
                                        on_message=self.message_handler.message_handler_orders)

    def get_listen_key(self):
        response = self.client.new_listen_key()
        listen_key = response["listenKey"]
        return listen_key

    def create_websocket_stream(self, on_message_stream_name : str):
        if self.program_type == 'TEST':
            stream_url = "wss://stream.testnet.binance.vision"
        else:
            stream_url = "wss://stream.binance.com:9443"
        if on_message_stream_name == 'userData':
            logging.info("Receving listen key : %s", self.listen_key)
            ws_user_data = SpotWebsocketStreamClient(
                stream_url=stream_url,
                on_message=self.message_handler.message_user_data
            )
            ws_user_data.user_data(listen_key=self.listen_key)
            return ws_user_data
        elif on_message_stream_name == 'kline':
            #Si on utilise "wss://stream.testnet.binance.vision",
            # #on va récupérer les données du test net qui sont très peu représentatatives du marché
            stream_url = "wss://stream.binance.com:9443"
            return SpotWebsocketStreamClient(
                stream_url=stream_url,
                on_message=self.message_handler.message_processing_kline,
                is_combined=True
            )
        elif on_message_stream_name == 'rolling1h':
            stream_url = "wss://stream.binance.com:9443"
            return SpotWebsocketStreamClient(
                stream_url=stream_url,
                on_message=self.message_handler.message_processing_rolling,
                is_combined=True
            )
        elif on_message_stream_name == 'mini_ticker':
            stream_url = "wss://stream.binance.com:9443"
            return SpotWebsocketStreamClient(
                stream_url=stream_url,
                on_message=self.message_handler.message_processing_mini_ticker,
                is_combined=True
            )
        raise ValueError('Wrong parameter')


class MessageHandler:
    """Handles incoming WebSocket messages and processes them according to the trading strategy."""
    def __init__(self, pump_and_dump : Strategy):
        self.pump_and_dump = pump_and_dump

    def set_strategy(self, pump_and_dump : Strategy):
        self.pump_and_dump = pump_and_dump

    def message_processing_rolling(self, _, source):
        message : dict = json.loads(source)

        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with rolling windows 1hour.')
            return
        self.pump_and_dump.update_parameters('1h', message['data'])
        #self.save_datas(message)
        return None

    def message_processing_mini_ticker(self, _, source):
        message : dict = json.loads(source)
        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with websocket mini ticker.')
            return None
        self.pump_and_dump.update_parameters(None, message['data'])
        #self.save_datas(message)
        return None

    def message_processing_kline(self, _, source):
        message : dict = json.loads(source)
        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with websocket kline.')
            return None
        self.pump_and_dump.update_parameters('1m', message['data']['k'])
        self.pump_and_dump.take_decision(message['data'])
        #self.save_datas(message)
        return None

    @staticmethod
    def save_datas(message):
        """ Save the incoming message data to a file for historical analysis. (Currently not used)"""
        path = r'bot/data/historical_datas'
        if 'kline' in message['stream']:
            with open(
                os.path.join(path, 'kline1m', message['data']['s'] + '.txt'),
                'a',
                encoding= 'utf-8'
            ) as f:
                f.write(json.dumps(message)+ '\n')
        elif 'miniTicker' in message['stream']:
            with open(
                os.path.join(path, 'mini_ticker', message['data']['s'] + '.txt'),
                'a', 
                encoding = 'utf-8'
            ) as f:
                f.write(json.dumps(message) + '\n')
        elif 'ticker' in message['stream']:
            with open(
                os.path.join(path, 'historical_window_1h', message['data']['s'] + '.txt'),
                'a', 
                encoding = 'utf-8'
            ) as f:
                f.write(json.dumps(message) + '\n')

    def message_handler_open_orders(self, _, source):
        """Get existing open orders to cancel them."""
        list_crypto = []
        message = json.loads(source)
        result = message['result']
        for crypto in result:
            list_crypto.append(crypto['symbol'])
        if list_crypto:
            self.pump_and_dump.trading_manager.websocket_manager.ws_api_client.cancel_open_orders(
                symbol=list_crypto
            )

    def message_handler_orders(self, _, source):
        message : dict = json.loads(source)
        if message.get('result', 0) is None:
            return None
        if 'error' in message:
            
            error : dict = message['error']
            logging.debug("Code : %s", error['code'])
            logging.debug("Message : %s", error['msg'])
            logging.debug("data_error : %s", error.get('data', None))
            logging.debug(self.pump_and_dump.trading_manager.portfolio.actifs)
            return None
        result = message.get("result")

        if 'cancelResult' in result:
            if result['cancelResult'] == 'SUCCESS' and result['newOrderResult'] == 'SUCCESS':
                logging.debug('Order canceled successfully.')
        elif result['status'] == 'FILLED':
            pass

        elif result['status'] == 'NEW':
            pass
        else:
            pprint.pprint(message)
            pprint.pprint(result['status'])
        return None

    def message_user_data(self, _, source):
        message : dict = json.loads(source)
        if message.get('e', None) == 'outboundAccountPosition':
            pass
        elif message.get('e', None) == 'executionReport':
            side = message['S']
            if message.get('x', None) == 'CANCELED' and side == 'SELL':
                logging.debug("OLD STOP LOSS CANCELED")
                logging.debug("Ticker %s | Stop_loss : %s", side, message['P'])
                logging.debug('---------------')
            elif message.get('x', None) == 'NEW':
                if side == 'SELL':
                    logging.debug("NEW STOP LOSS SEND")
                elif side == 'BUY':
                    logging.debug("NEW BUY ORDER SEND")
                logging.debug("Ticker %s | Stop_loss : %s", message['s'], message['P'])
                logging.debug('---------------')
            elif message.get('x', None) == 'TRADE':
                ticker = message['s']
                executed_price = float(message['L'])
                logging.debug('%s DONE', side)
                working_time_order = datetime.datetime.fromtimestamp(int(message['T'])/1000)
                executed_qty = float(message['l'])
                commission, commission_asset = float(message['n']), message['N']

                print(side, working_time_order, ticker, executed_qty, executed_price, commission, commission_asset)

                try:
                    self.pump_and_dump.trading_manager.portfolio.transaction_order(
                        side,
                        working_time_order,
                        ticker,
                        executed_qty,
                        executed_price
                    )
                except Exception:
                    print(self.pump_and_dump.trading_manager.portfolio.actifs)


                if side == 'BUY':
                    logging.debug("Ticker : %s | Prix d'achat : %s", message['s'], message['L'])
                    threading.Thread(
                        target=self.pump_and_dump.define_stop_losses,
                        args = (ticker, executed_price)
                    ).start()
                elif side == 'SELL':
                    if message['s'].endswith('USDT'):
                        logging.debug("Ticker : %s | USDC en plus : %s | Au prix : %s",
                                    message['s'],
                                    message['Y'],
                                    message['L'])
                    elif message['s'].endswith('TRY'):
                        logging.debug("Ticker : %s | TRY en plus : %s | Au prix : %s",
                                    message['s'],
                                    message['Y'],
                                    message['L']) 
                    elif message['s'].endswith('BTC'):
                        logging.debug("Ticker : %s | BTC en plus : %s | Au prix : %s",
                                    message['s'],
                                    message['Y'],
                                    message['L'])
                logging.debug('---------------')
