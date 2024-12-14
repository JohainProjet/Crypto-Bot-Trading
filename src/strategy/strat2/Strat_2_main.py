import logging.config
import time
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from .get_data_2 import messageProcessing, dataframe_storage, crypto_bought, portefeuille_test
import logging

logging.basicConfig(level=logging.INFO)

with open(r"C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading\src\strategy\strat2\listpairs.txt", 'r') as f:
    listTickers = f.read().splitlines()

def strategy2_main(time_to_sleep : int):
    ws_client = SpotWebsocketStreamClient(on_message=messageProcessing, is_combined=True)
    
    list_ticker_kline = []
    for ticker in listTickers:
        list_ticker_kline.append(ticker+'@kline_2h')
        list_ticker_kline.append(ticker+'@kline_3m')
    ws_client.subscribe(stream=list_ticker_kline)

    time.sleep(time_to_sleep)
    logging.info("closing ws connection")
    ws_client.unsubscribe(stream=list_ticker_kline)
    logging.info('writing in excel')
    logging.info(crypto_bought)
    dataframe_storage.to_excel("Storage_stats.xlsx")
    print(portefeuille_test.df_transaction_history)
    ws_client.stop()
if __name__ == '__main__':
    strategy2_main()