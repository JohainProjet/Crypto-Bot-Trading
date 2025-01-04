import time
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from src.strategy.strat2.strategy2 import messageProcessingkline3m, messageProcessingRolling1h
from src.strategy.strat2.shared import dataframe_storage, crypto_bought, portefeuille_test
import logging
from binance.lib.utils import config_logging

config_logging(logging, logging.DEBUG)



def strategy2_main(time_to_sleep : int):
    
    with open(r"C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading\src\strategy\strat2\list_all_pairs.txt", 'r') as f:
        listTickers = f.read().splitlines()

    ws_client_kline3m = SpotWebsocketStreamClient(on_message=messageProcessingkline3m, is_combined=True)
    ws_client_rolling1h = SpotWebsocketStreamClient(on_message=messageProcessingRolling1h, is_combined=True)

    list_ticker_kline3m = [ticker.lower()+'@kline_3m' for ticker in listTickers]
    list_ticker_rolling1h = [ticker.lower()+'@ticker_1h' for ticker in listTickers]
    
    ws_client_rolling1h.subscribe(stream = list_ticker_rolling1h)
    ws_client_kline3m.subscribe(stream=list_ticker_kline3m)
    logging.info('start sleep')
    time.sleep(time_to_sleep)

    logging.info(portefeuille_test.evaluate_portfolio_value())

    ws_client_kline3m.stop()
    ws_client_rolling1h.stop()
    
    logging.info('writing in excel')
    logging.info(crypto_bought)
    dataframe_storage.to_excel("Storage_stats.xlsx")
    portefeuille_test.df_transaction_history.to_excel("Transaction History.xlsx")




if __name__ == '__main__':
    strategy2_main()