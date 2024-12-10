import pprint
import time
import pandas as pd
from binance.lib.utils import config_logging
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from get_data_2 import message_handler2


def main():

    ws_client = SpotWebsocketStreamClient(on_message=message_handler2, is_combined=True)
    ws_client.kline(symbol="troyusdt", interval="2h")
    ws_client.kline(symbol="troyusdt", interval="3m")
    
    time.sleep(40)

    print("closing ws connection")
    ws_client.stop()


if __name__ == '__main__':
    main()