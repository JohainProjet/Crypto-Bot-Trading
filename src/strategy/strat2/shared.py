import pandas as pd
from src.strategy.classes import Portfolio
from binance.client import Client
from src.utils import get_api_key

api_key, api_secret = get_api_key()
client = Client(api_key, api_secret)

ticker_bought_actual_max_price = {}

global_dictionnary : dict = {'variation2h' : 0,
                            'volume2h' : 0,
                            'variation3m' : 0,
                            'volume3m' : 0,
                            'buy' : 0}

multi_columns = pd.MultiIndex.from_tuples([('Variation', '3m'), ('Variation', '2h'),
                                          ('Volume', '3m'), ('Volume', '2h'),
                                          ('Price is going up', None)])

dataframe_storage = pd.DataFrame(columns = multi_columns)

limits = {'volume' : 7, 'variation' : 7}#(2, 2.3)

crypto_bought = []

portefeuille_test = Portfolio(200)
