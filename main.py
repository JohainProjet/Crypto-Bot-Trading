import pprint
import time
import json
import logging
import torch
import csv
import pandas as pd
from binance.lib.utils import config_logging
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from binance.spot import Spot as Client
from traitement import *

torch.set_printoptions(sci_mode=False)

def main(strategy : int, list_of_pairs : list):
    pass

if __name__ == '__main__':
    main()