import os
import datetime
import json
import time
from pympler.tracker import SummaryTracker

from tqdm import tqdm
import pandas as pd
import zipfile
from collections import defaultdict, deque
from binance.spot import Spot as Client
from bot.trading.base_trading import TradingManager
from bot.strategy.base_strategy import Strategy

class BackTesting(TradingManager):
    def __init__(self, parameters, portfolio, simulation_saver):
        super().__init__(parameters,  portfolio, simulation_saver)
        self.list_tickers = parameters.list_tickers
        self.parameters = parameters
        self.datas = Datas(parameters)
        self.orders = {}

    def set_pump_and_dump(self, pump_and_dump):
        self.pump_and_dump = pump_and_dump

    def message_processing_rolling_back_testing(self, message):
        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with rolling windows 1hour.')
            return None
        data = message['data']
        self.datas.strategy.update_parameters('1h', data)
        return None

    def get_ticker_tick_size(self, ticker):
        client = Client(self.api_key, base_url='https://api.binance.com')
        resp = client.exchange_info()['symbols']
        for elem in resp:
            if elem['symbol'] == ticker:
                return float(elem['filters'][1]['stepSize']), float(elem['filters'][0]['tickSize'])
        return None

    def message_processing_kline_back_testing(self, message):
        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with websocket kline.')
            return None
        data = message['data']
        ticker :str = data['k']['s']
        self.datas.strategy.update_parameters(self.parameters.kline_type, data['k'])
        self.datas.strategy.take_decision(data)

        matching_key = next((key for key in self.orders.keys() if key.startswith(ticker[:-4])), None)
        k = data['k']['s']
        if matching_key:
            self.check_stop_losses(matching_key, data)
        return None
    
        #{"stream": "1000catusdc@miniTicker", 
        # "data": {"e": "24hrMiniTicker", "E": 1745921398902, "s": "1000CATUSDC", 
        # "c": "0.00714000", "o": "0.00728000", "h": "0.00750000", "l": "0.00685000", 
        # "v": "14210343.70000000", "q": "102270.93361700"}}

    def message_processing_mini_ticker_back_testing(self, message):
        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with mini ticker.')
            return None
        data = message['data']
        self.datas.strategy.update_parameters(None, data)
        return None

    def generate_list_month(self):
        current = datetime.datetime(self.parameters.start_date.year, self.parameters.start_date.month, 1)
        end_month = datetime.datetime(self.parameters.end_date.year, self.parameters.end_date.month, 1)

        month_list = [i.strftime("%Y-%m") for i in pd.date_range(start=current, end=end_month, freq='MS')]
        return month_list

    def start(self):
        list_months = self.generate_list_month()
        for month in tqdm(list_months):
            gen_sorted_items = self.datas.fill_dict_time(month)
            for sorted_items in gen_sorted_items:
                if len(sorted_items.keys()) == 0:
                    continue
                time_reference = list(sorted_items.keys())[0]
                print(time_reference)
                for current_time, list_events in sorted_items.items():
                    if current_time - time_reference >= datetime.timedelta(minutes=30):
                        self.screenshot(current_time)
                        time_reference = current_time
                    for event in list_events:
                        if 'kline' in event['stream']:
                            self.message_processing_kline_back_testing(event)
                        elif 'ticker' in event['stream']:
                            self.message_processing_rolling_back_testing(event)
                        elif 'miniTicker' in event['stream']:
                            self.message_processing_mini_ticker_back_testing(event)

                last_time = list(sorted_items.keys())[-1]
                self.portfolio.evaluate_portfolio_value(last_time, self.datas.data_manager)
        self.stop()

    def stop(self):
        with open(r"bot\results\TradesLogFile.txt", "a", encoding='utf-8') as f:
            f.write("\n")
            self.portfolio.df_transaction_history.to_string(f, index=True)
            f.write("\n\n")

    def buy(self, ticker, quote_order_qty, excecuted_price=0, time_=0):
        executed_qty = quote_order_qty/excecuted_price
        step_size = self.get_ticker_tick_size(ticker)[0]
        executed_qty = round((executed_qty//step_size)*step_size,8)
        working_time_order = datetime.datetime.fromtimestamp(int(time_)/1000)
        self.portfolio.transaction_order('BUY',
                                        working_time_order,
                                        ticker,
                                        executed_qty,
                                        excecuted_price)
        self.datas.strategy.define_stop_losses(ticker, excecuted_price)
        print(self.portfolio.df_transaction_history)

    def cancel_replace(self, pair : str, quantity_bought, new_stop_loss_price):
        self.place_stop_loss(pair, quantity_bought, new_stop_loss_price)
    
    def place_stop_loss(self, pair, quantity_bought, stop_loss_price):
        self.orders[pair] = {"quantity" : float(quantity_bought),
                               'stopLossPrice' : stop_loss_price}

    def check_stop_losses(self, ticker, data):
        working_time_order = datetime.datetime.fromtimestamp(int(data['E'])/1000)

        current_price = self.datas.strategy.prices[ticker][-1]
        if self.orders[ticker]['stopLossPrice'] >= current_price: #stoplossPrice is incorrect (in usdt when it needs to be in zrxbtc)
            try:
                self.portfolio.transaction_order('SELL',
                                                working_time_order,
                                                ticker,
                                                self.orders[ticker]['quantity'],
                                                current_price)
                del self.orders[ticker]
            except ValueError:
                return
            print(self.portfolio.df_transaction_history)


class DataManager:
    dict_time = defaultdict(list)
    def __init__(self):
        self.path = r'bot\data\historical_datas_from_api'
        self.klines : dict = {}
        self.rolling_window = {}
        self.kline_write_counter = {}
        self.window_ready = set()

        #for rolling
        self.current_volume = {}
        self.current_nb_of_trades = {}
        self.current_quantities = {}
        self.closes = defaultdict(list)
        self.volume_to_subtract = {}
        self.current_nb_of_trades_to_substract = {}
        self.current_quantities_to_substract = {}
         #test
        self.nb_of_trades = 0
        self.count = 0
        self.start_date = None
        self.count_debug = 0

        #miniTicker
        self.mini_ticker = {}

    def create_kline_1s(self, ticker, row):
        """         
        1 = t
        2 = o
        3 = h
        4 = l
        5 = c
        6 = v
        7 = T
        8 = q
        9 = n
        10 = V
        11 = Q 
        """
        t = row[1]//1000
        o = row[2]
        h = row[3]
        l = row[4]
        c = row[5]
        v = row[6]
        E = row[7]//1000
        q = row[8]
        n = row[9]
        V = row[10]
        Q = row[11]
        B = row[12]

        T = int(t + 59_999)
        k = {
            't': t,
            'T': T,
            'E': E,
            's': ticker,
            'i': '1m', 
            'f': None,
            'L': None,
            'o': o,
            'c': c,
            'h': h,
            'l': l,
            'v': v,
            'n': n,
            'x':'false',
            'q': q,
            'V': V,
            'Q': Q,
            'B': B
        }
        return k

    def update_klines(self, k_1s):
        symbol = k_1s['s']
        minute_timestamp = k_1s['t'] // 60000 * 60000  # début de la minute
        #Rajouter un compteur > 60 pour être sûr qu'on a bien une vraie kline, pareil pour rolling windows faudra > 3600

        symbol_data = self.klines.get(symbol)
        if symbol_data:
            last_minute = symbol_data['data']['k']['t']
            agg_data = symbol_data['data']

        if symbol not in self.klines or minute_timestamp != last_minute:
            k = {
                't': minute_timestamp,
                'T': k_1s['T'],
                's': symbol,
                'i': '1m',
                'f': None,
                'L': None,
                'o': k_1s['o'],
                'c': k_1s['c'],
                'h': k_1s['h'],
                'l': k_1s['l'],
                'v': float(k_1s['v']),
                'n': int(k_1s['n']),
                'x': 'false',
                'q': float(k_1s['q']),
                'V': float(k_1s['V']),
                'Q': float(k_1s['Q']),
                'B': k_1s['B']
                }
            data = {'e' : 'kline',
                    'E' : k_1s['E'],
                    's' : symbol,
                    'k' : k}
            
            full_kline = {'stream' : symbol.lower()+'@kline_1m',
                                'data' : data}
            self.klines[symbol] = full_kline
        else:
            agg_data['E'] = k_1s['E']
            agg = agg_data['k']
            agg['h'] = max(agg['h'], k_1s['h'], key=float)
            agg['l'] = min(agg['l'], k_1s['l'], key=float)
            agg['c'] = k_1s['c']
            agg['v'] += round(float(k_1s['v']), 8)
            agg['q'] += float(k_1s['q'])
            agg['n'] += int(k_1s['n'])
            agg['V'] += round(float(k_1s['V']), 8)
            agg['Q'] += float(k_1s['Q'])
            agg['B'] = k_1s['B']
        self.kline_write_counter[symbol] = self.kline_write_counter.get(symbol, 0) + 1
        if self.kline_write_counter[symbol] == 2:
            self.kline_write_counter[symbol] = 0
            if symbol in self.window_ready:
                time_ = datetime.datetime.fromtimestamp(self.klines[symbol]['data']['E']/1000)
                self.dict_time[time_].append(self.klines[symbol])
                """ with open(os.path.join(self.path, 'kline1m', symbol + '.txt'), 'a') as f:
                    f.write(json.dumps(self.klines[symbol])+ '\n') """

    def update_rolling_window(self, k_1s):
        symbol = k_1s['s']
        if symbol not in self.rolling_window:
            self.rolling_window[symbol] = deque()
        o = float(k_1s['o'])
        p = round((float(k_1s['c']) - o), 8)
        v = round(float(k_1s['v']), 8)
        q = round(float(k_1s['q']), 8)
        n = k_1s['n']
        E = k_1s['E']

        try:
            w = round(q/v, 8)
        except ZeroDivisionError:
            w = None
        data = {'e': '1hTicker',
                'E': E,
                's': symbol,
                'p': p,
                'P': round(100*p/o, 8),
                'w': w,
                'o': k_1s['o'],
                'h': k_1s['h'],
                'l': k_1s['l'],
                'c': k_1s['c'],
                'v': v,
                'q': q,
                'O': None,
                'C': None,
                'F': None,
                'L': None,
                'n': n}

        full_kline = {'stream' : symbol.lower()+'@ticker_1h',
                            'data' : data}
        self.rolling_window[symbol].append(full_kline)

        self.closes[symbol].append(float(k_1s['c']))
        self.current_volume[symbol] = self.current_volume.get(symbol, 0) + v
        self.current_nb_of_trades[symbol] = self.current_nb_of_trades.get(symbol, 0) + n
        self.current_quantities[symbol] = self.current_quantities.get(symbol, 0) + q
        window = self.rolling_window[symbol]
        if len(window) >= 3660:
            self.window_ready.add(symbol)
        if symbol in self.window_ready:
            if E % 60_000 <= 1000:
                volume_to_subtract, current_nb_of_trades_to_substract, current_quantities_to_substract = 0, 0, 0
                volume_to_subtract += float(window[0]['data']['v'])
                current_nb_of_trades_to_substract += window[0]['data']['n']
                current_quantities_to_substract += float(window[0]['data']['q'])
                window.popleft()
                self.closes[symbol].pop(0)
                while window[0]['data']['E'] % 60000 > 1000:
                    volume_to_subtract += float(window[0]['data']['v'])
                    current_nb_of_trades_to_substract += window[0]['data']['n']
                    current_quantities_to_substract += float(window[0]['data']['q'])
                    window.popleft()
                    self.closes[symbol].pop(0)
                self.current_volume[symbol] -= volume_to_subtract
                self.current_nb_of_trades[symbol] -= current_nb_of_trades_to_substract
                self.current_quantities[symbol] -= current_quantities_to_substract

            o = float(window[0]['data']['o'])
            p = (self.closes[symbol][-1] - o)
            q = round(self.current_quantities[symbol], 8)
            v = round(self.current_volume[symbol], 8)

            data = {'e': '1hTicker',
                    'E': E,
                    's': symbol,
                    'p': round((self.closes[symbol][-1] - o), 8),
                    'P': round(100*p/o, 8),
                    'w': round(q/v, 8),
                    'o': round(float(window[0]['data']['o']), 8),
                    'h': round(max(self.closes[symbol]), 8),
                    'l': round(min(self.closes[symbol]), 8),
                    'c': round(self.closes[symbol][-1], 8),
                    'v': v,
                    'q': q,
                    'O': None,
                    'C': None,
                    'F': None,
                    'L': None,
                    'n': self.current_nb_of_trades[symbol]}
            full_kline = {'stream' : symbol.lower()+'@ticker_1h',
                                'data' : data}
            time_ = datetime.datetime.fromtimestamp(E/1000)
            self.dict_time[time_].append(full_kline)
        """ with open(os.path.join(self.path, 'historical_window_1h', symbol + '.txt'), 'a') as f:
            f.write(json.dumps(full_kline)+ '\n') """

    def update_mini_ticker(self, k_1s):
        symbol = k_1s['s']
        E = k_1s['E']
        data = {
            'e': '24hrMiniTicker',
            'E': E,
            's': symbol,
            'c': k_1s['c'],
            'o': False,
            'h': False,
            'l': False,
            'v': False,
            'q': False,
            }
        full_kline = {'stream' : symbol.lower()+'@miniTicker',
                        'data' : data}
        self.mini_ticker[symbol] = full_kline
        if symbol in self.window_ready:
            time_ = datetime.datetime.fromtimestamp(E/1000)
            self.dict_time[time_].append(self.mini_ticker[symbol])
            """ with open(os.path.join(self.path, 'mini_ticker', symbol + '.txt'), 'a') as f:
                f.write(json.dumps(self.mini_ticker[symbol])+ '\n') """

    def extract_zip_stream(self, zip_path):
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # On suppose qu'il y a un seul fichier à l'intérieur
            for name in zip_ref.namelist():
                if name.endswith('.csv') or name.endswith('.csv.gz'):
                    return zip_ref.open(name)
            raise FileNotFoundError("Aucun fichier .csv ou .csv.gz trouvé dans le zip.")

    def extract_zip(self, zip_path):
        # Crée le dossier d'extraction
        extract_dir = os.path.splitext(zip_path)[0]
        os.makedirs(extract_dir, exist_ok=True)

        # Extraction du zip
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        # Recherche du premier fichier CSV ou CSV.GZ extrait
        for file in os.listdir(extract_dir):
            if file.endswith('.csv') or file.endswith('.csv.gz'):
                file_path = os.path.join(extract_dir, file)
                break
        else:
            raise FileNotFoundError("Aucun fichier .csv ou .csv.gz trouvé dans le zip.")
        return file_path

    def process_dataframe(self, ticker, df):
        """
        Lit le DataFrame ligne par ligne et crée un dictionnaire par ligne.
        Retourne une liste de dictionnaires.
        """
        df["t"] = df["t"] // 1000
        df["E"] = df["E"] // 1000
        df['T'] = df['t'].astype(int) + 59999
        df["i"] = "1m"
        df["f"] = None
        df["L"] = None
        df["x"] = "false"
        df["s"] = ticker
        moyenne_update_rolling = []
        moyenne_update_klines = []
        for kline in df.to_dict(orient='records'):
            #kline = self.create_kline_1s(ticker, row)
            if ticker.endswith('USDT'):
                t1 = time.time()
                self.update_rolling_window(kline)
                moyenne_update_rolling.append(time.time()-t1)
                t1 = time.time()
                self.update_klines(kline)
                moyenne_update_klines.append(time.time()-t1)
            else:
                self.update_mini_ticker(kline)
        if moyenne_update_klines and moyenne_update_rolling:
            print('rolling_mean', sum(moyenne_update_rolling)/len(moyenne_update_rolling))
            print('klines_mean', sum(moyenne_update_klines)/len(moyenne_update_klines))

class Datas:
    path_ = r'bot\data\historical_datas'
    path_files_klines = []
    path_files_rolling = []
    path_files_mini_ticker = []
    end_of_the_file = False
    COLUMNS_NAMES = ["t", "o", "h", "l", "c", "v", "E", "q", "n", "V", "Q", "B"]
    def __init__(self, parameters, strategy = None):
        self.list_tickers = parameters.list_tickers
        self.strategy = strategy
        self.start_date : datetime.datetime = parameters.start_date
        self.end_date : datetime.datetime = parameters.end_date
        self.data_manager  : DataManager = DataManager()
        if not Datas.path_files_klines:
            Datas.path_files_klines = [os.path.join(Datas.path_,
                                                    f'kline{parameters.kline_type}',
                                                    f'{ticker}.txt') for ticker in parameters.list_tickers if ticker.endswith('USDT')]
        if not Datas.path_files_rolling:
            Datas.path_files_rolling = [os.path.join(Datas.path_,
                                                     'historical_window_1h',
                                                     f'{ticker}.txt') for ticker in parameters.list_tickers if ticker.endswith('USDT')]
        if not Datas.path_files_mini_ticker:
            Datas.path_files_mini_ticker = [os.path.join(Datas.path_,
                                                     'mini_ticker',
                                                     f'{ticker}.txt') for ticker in parameters.list_tickers if not ticker.endswith('USDT')]

    def set_strategy(self, strategy : Strategy):
        self.strategy = strategy

    def build_path(self, symbol, month):
        base_folder = (
            r"C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading"
            r"\bot\data\historical_datas_from_api\zip_klines\data\spot\monthly\klines"
        )
        path = (
            f"{base_folder}\\{symbol}\\1s\\2025-01-01_2025-04-30\\"
            f"{symbol}-1s-{month}.zip"
        )
        return path

    def generate_list_month(self):
        
        current = datetime(self.start_date.year, self.start_date.month, 1)
        end_month = datetime(self.end_date.year, self.end_date.month, 1)

        month_list = [i.strftime("%Y-%m") for i in pd.date_range(start=current, end=end_month, freq='MS')]
        return month_list
    
    def fill_dict_time(self, month):
        
        start_time = 1735689600000
        end_time = 	1745971199000

        #On découpe en intervalles de 999_000 millisecondes
        interval = 1_000_000
        ranges = []
        current = start_time
        while current < end_time:
            next_time = min(current + interval, end_time)
            ranges.append((current, next_time))
            current = next_time
        

        print(f"\n Traitement du mois : {month}")
        

        generators = []

        for i, symbol in enumerate(self.list_tickers[:100]):
            file_path = self.build_path(symbol, month)
            file_path_csv = self.data_manager.extract_zip_stream(file_path)
            gen = pd.read_csv(file_path_csv, chunksize=10000, compression='infer', names = self.COLUMNS_NAMES)
            generators.append((symbol, gen))
            print(i)

        # Lecture par chunks de 1000 lignes
        while True:
            t1 = time.time()
            all_exhausted = True
            chunks = []

            for symbol, gen in generators:
                try:
                    chunk = next(gen)
                    chunks.append((symbol, chunk))
                    all_exhausted = False
                except StopIteration:
                    chunks.append((symbol, None))

            if all_exhausted:
                print("Tous les fichiers de ce mois ont été traités.")
                break

            # Traitement des chunks du mois en cours
            # Chaque chunk représente 1000 lignes d'un ticker
            self.data_manager.dict_time = defaultdict(list) #On reset le dictionnaire des events avant chaque nouvelles 1000 lignes traitées
            count= 0
            for symbol, chunk in chunks:
                count+=1
                print(count)
                if chunk is not None:
                    self.data_manager.process_dataframe(symbol, chunk)
                    # process_chunk(chunk, symbol, month)
            t1b = time.time()
            sorted_items = dict(sorted(self.data_manager.dict_time.items(), key=lambda item: item[0]))
            
            t2 = time.time()
            print('sorted_time', t2 - t1b)
            print()
            print(len(sorted_items))
            print("Temps pris pour former le dicitonnaire :", t2-t1)
            yield sorted_items