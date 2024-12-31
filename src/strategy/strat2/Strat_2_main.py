import logging.config
import time
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from .get_data_2 import messageProcessingkline3m, messageProcessingRolling1h, dataframe_storage, crypto_bought, portefeuille_test
from .get_data_2 import on_open, on_close
import logging

logging.basicConfig(level=logging.INFO)

with open(r"C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading\src\strategy\strat2\list_all_pairs.txt", 'r') as f:
    listTickers = f.read().splitlines()

def strategy2_main(time_to_sleep : int):

    ws_client_kline3m = SpotWebsocketStreamClient(on_open=on_open, on_message=messageProcessingkline3m, on_close=on_close, is_combined=True)
    ws_client_rolling1h = SpotWebsocketStreamClient(on_message=messageProcessingRolling1h, is_combined=True)

    list_ticker_kline3m = [ticker.lower()+'@kline_3m' for ticker in listTickers]
    list_ticker_rolling1h = [ticker.lower()+'@ticker_1h' for ticker in listTickers]
    
    ws_client_rolling1h.subscribe(stream = list_ticker_rolling1h)
    ws_client_kline3m.subscribe(stream=list_ticker_kline3m)

    time.sleep(time_to_sleep)

    print(portefeuille_test.evaluate_portfolio_value())

    logging.info("closing ws connection")

    ws_client_kline3m.unsubscribe(stream=list_ticker_kline3m)
    ws_client_rolling1h.unsubscribe(stream = list_ticker_rolling1h)
    print(portefeuille_test.evaluate_portfolio_value())
    ws_client_kline3m.stop()
    ws_client_rolling1h.stop()
    logging.info('writing in excel')
    logging.info(crypto_bought)


if __name__ == '__main__':
    strategy2_main()