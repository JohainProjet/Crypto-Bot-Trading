
import time
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from binance.spot import Spot as Client
from get_data_1 import *


def main():
    
    ws_client = SpotWebsocketStreamClient(on_message=message_handler)

    ws_client.diff_book_depth(symbol = 'jstusdt', speed = 1000)
    ws_client.agg_trade(symbol = 'jstusdt')

    time.sleep(240)

    print("closing ws connection")
    ws_client.stop()
    print(len(X_data))
    print(len(Y_data))


if __name__ == '__main__':
    main()

#{"e":"depthUpdate","E":1726908347945,"s":"JSTUSDT","U":849543915,"u":849543928,"b":[["0.02898000","517.60000000"]],
# "a":[["0.02900000","185561.00000000"],["0.02901000","29070.20000000"],["0.02925000","1014.80000000"]]}