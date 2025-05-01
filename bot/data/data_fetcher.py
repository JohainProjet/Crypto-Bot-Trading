import os
import time
import json
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient

path = r'bot\data\historical_datas'

def get_tickers():
    with open(r"bot\data\list_all_pairs.txt", 'r') as f:
        listTickers = f.read().splitlines()
    return listTickers

def messageProcessingkline1m(_, source):
    message = json.loads(source)
    if message.get('result',0) is None:
        return
    with open(os.path.join(path, 'kline1m', message['data']['s'] + '.txt'), 'a') as f:
        f.write(json.dumps(message)+ '\n')

def messageProcessingkline3m(_, source):
    message = json.loads(source)
    if message.get('result',0) is None:
         return
    with open(os.path.join(path, 'kline3m', message['data']['s'] + '.txt'), 'a') as f:
        f.write(json.dumps(message)+ '\n')

def messageProcessingRolling1h(_, source):
    message = json.loads(source)
    if message.get('result',0) is None:
         return
    with open(os.path.join(path, 'historical_window_1h', message['data']['s'] + '.txt'), 'a') as f:
        f.write(json.dumps(message) + '\n')

def messageProcessingMiniTicker(_, source):
    message = json.loads(source)
    if message.get('result',0) is None:
         return
    with open(os.path.join(path, 'mini_ticker', message['data']['s'] + '.txt'), 'a') as f:
        f.write(json.dumps(message) + '\n')

def main():
    listTickers_usdt = get_tickers()

    list_ticker_kline1m_usdt = [ticker.lower()+'@kline_1m' for ticker in listTickers_usdt if ticker.endswith('USDT')]
    list_ticker_kline3m_usdt = [ticker.lower()+'@kline_3m' for ticker in listTickers_usdt if ticker.endswith('USDT')]
    list_ticker_rolling1h_usdt = [ticker.lower()+'@ticker_1h' for ticker in listTickers_usdt if ticker.endswith('USDT')]

    list_mini_ticker = [ticker.lower()+'@miniTicker' for ticker in listTickers_usdt if not ticker.endswith('USDT')]

    stream_url = "wss://stream.binance.com:9443"
    websocket_1m = SpotWebsocketStreamClient(stream_url=stream_url,
                                             on_message=messageProcessingkline1m,
                                             is_combined=True)
    websocket_3m= SpotWebsocketStreamClient(stream_url=stream_url,
                                             on_message=messageProcessingkline3m,
                                             is_combined=True)
    websocket_1h = SpotWebsocketStreamClient(stream_url=stream_url,
                                             on_message=messageProcessingRolling1h,
                                             is_combined=True)

    websocket_mini = SpotWebsocketStreamClient(stream_url=stream_url,
                                             on_message=messageProcessingMiniTicker,
                                             is_combined=True)
    
    websocket_mini.subscribe(stream = list_mini_ticker)
    websocket_1m.subscribe(stream = list_ticker_kline1m_usdt)
    websocket_3m.subscribe(stream = list_ticker_kline3m_usdt)
    websocket_1h.subscribe(stream = list_ticker_rolling1h_usdt)


    time.sleep(85000)

    websocket_1m.stop()
    websocket_3m.stop()
    websocket_1h.stop()
    websocket_mini.stop()


if __name__ == '__main__':
    main()