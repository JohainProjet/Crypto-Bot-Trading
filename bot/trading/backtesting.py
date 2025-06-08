import os
import datetime
import time
import pandas as pd
import zipfile
from tqdm import tqdm
from collections import defaultdict, deque
from binance.spot import Spot as Client
from bot.trading.base_trading import TradingManager
from bot.strategy.base_strategy import Strategy
from bot.utils.helpers import PAIRS_FOR_BACKTEST


class BackTesting(TradingManager):
    """ BackTesting class for simulating trading strategies on historical data."""
    def __init__(self, parameters, portfolio, simulation_saver):
        super().__init__(parameters,  portfolio, simulation_saver)
        self.list_tickers = parameters.GLOBAL_PARAMETERS['LIST_TICKERS']
        self.parameters = parameters
        self.datas = Datas(parameters)
        self.orders : dict[dict[str,float]]= {} #Only ticker+USDT

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
        current_pair = data['k']['s']
        self.datas.strategy.update_parameters('1m', data['k'])
        self.datas.strategy.take_decision(data)

        for pair in self.orders:
            if pair.startswith(current_pair[:-4]):
                self.check_stop_losses(pair, data)
                break
        return None

    def message_processing_mini_ticker_back_testing(self, message):
        if message.get('result',0) is None:
            print(f'Connection open at {datetime.datetime.now()} with mini ticker.')
            return None
        data = message['data']
        self.datas.strategy.update_parameters(None, data)
        return None

    def generate_list_month(self):
        start_date : datetime.datetime = self.parameters.GLOBAL_PARAMETERS['START_DATE']
        end_date : datetime.datetime = self.parameters.GLOBAL_PARAMETERS['END_DATE']
        current = datetime.datetime(start_date.year, start_date.month, 1)
        end_month = datetime.datetime(end_date.year, end_date.month, 1)

        month_list = [i.strftime("%Y-%m") for i in pd.date_range(start=current, end=end_month, freq='MS')]
        return month_list

    def start(self)->None:
        """ 
        Start the backtesting process by iterating through historical data.
        Every month of data is processed, and events are handled based on the time intervals.
        The method generates a list of months based on the start and end dates, processes each month
        by filling a dictionary with time as keys and events (list) as values. 
        It then iterates through the events.
        """
        t1=time.time()
        list_months = self.generate_list_month()
        for month in tqdm(list_months):
            gen_sorted_items = self.datas.fill_dict_time(month)
            try:
                for sorted_items in gen_sorted_items:
                    if len(sorted_items.keys()) == 0:
                        continue
                    time_reference = list(sorted_items.keys())[0]
                    #print(time_reference)
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
                    self.portfolio.evaluate_portfolio_value()
            except EndOfBacktest:
                print(time.time()-t1)
                self.stop()
                return None
        return None


    def stop(self):
        with open(r"bot/results/TradesLogFile.txt", "a", encoding='utf-8') as f:
            f.write("\n")
            self.portfolio.df_transaction_history.to_string(f, index=True)
            f.write("\n\n")

    def buy(self, pair, quote_order_qty, excecuted_price=0, time_=0):
        """ 
        Simulate a buy order by calculating the executed quantity 
        based on the quote order quantity and executed price.
        """
        executed_qty = quote_order_qty/excecuted_price
        step_size = self.get_ticker_tick_size(pair)[0]
        executed_qty = round((executed_qty//step_size)*step_size,8)
        working_time_order = datetime.datetime.fromtimestamp(int(time_)/1000)
        self.portfolio.transaction_order('BUY',
                                        working_time_order,
                                        pair,
                                        executed_qty,
                                        excecuted_price)
        self.datas.strategy.define_stop_losses(pair, excecuted_price)
        #print(self.portfolio.df_transaction_history)

    def cancel_replace(self, pair : str, quantity_bought, new_stop_loss_price):
        self.place_stop_loss(pair, quantity_bought, new_stop_loss_price)
    
    def place_stop_loss(self, pair, quantity_bought, stop_loss_price):
        self.orders[pair] = {"quantity" : float(quantity_bought),
                               'stopLossPrice' : stop_loss_price}

    def check_stop_losses(self, ticker : str, data : dict):
        """
        Check if the current price is below the stop loss price for a given ticker.
        If it is, execute a sell order and remove the ticker from the orders dictionary.
        """
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
            #print(self.portfolio.df_transaction_history)


class DataManager:
    """
    DataManager class for managing historical data and processing kline updates.
    One of the main problem is that only klines are available in the websocket,
    so we need to create rolling windows and miniTicker from kline.
    """
    dict_time = defaultdict(list)
    def __init__(self):
        self.path = r'bot/data/historical_datas_from_api'

        #Used to store the klines
        self.klines : dict = {}
        self.rolling_window = {}
        self.kline_write_counter = {}
        self.window_ready = set()

        #Used to store the current state of the rolling window
        self.current_volume = {}
        self.current_nb_of_trades = {}
        self.current_quantities = {}
        self.closes = defaultdict(list)
        self.volume_to_subtract = {}
        self.current_nb_of_trades_to_substract = {}
        self.current_quantities_to_substract = {}
        
        #Used for debugging
        self.nb_of_trades = 0
        self.count = 0
        self.start_date = None
        self.count_debug = 0

        #miniTicker
        self.mini_ticker = {}

    def create_kline_1s(self, ticker, row):
        """"""
        t = int(row[0]//1000)
        o = row[1]
        h = row[2]
        l = row[3]
        c = row[4]
        v = row[5]
        E = int(row[6]//1000)
        q = row[7]
        n = row[8]
        V = row[9]
        Q = row[10]
        B = row[11]

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
        """ Create from kline 1s a kline 1m and store it in the klines dictionary."""
        symbol = k_1s['s']
        minute_timestamp = k_1s['t'] // 60000 * 60000

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
        """ Create from kline 1s a rolling window 1h and store it in the rolling_window dictionary."""
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
        """ Create from kline 1s a mini ticker and store it in the mini_ticker dictionary."""
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
        if symbol[:-4]+'USDT' in self.window_ready:
            time_ = datetime.datetime.fromtimestamp(E/1000)
            self.dict_time[time_].append(self.mini_ticker[symbol])
            """ with open(os.path.join(self.path, 'mini_ticker', symbol + '.txt'), 'a') as f:
                f.write(json.dumps(self.mini_ticker[symbol])+ '\n') """

    def extract_zip_stream(self, zip_path):
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for name in zip_ref.namelist():
                if name.endswith('.csv') or name.endswith('.csv.gz'):
                    return zip_ref.open(name)
            raise FileNotFoundError("Aucun fichier .csv ou .csv.gz trouvé dans le zip.")

    def extract_zip(self, zip_path):
        """ Extracts a zip file and returns the path of the first .csv or .csv.gz file found inside. 
        (Currently not used)."""
        extract_dir = os.path.splitext(zip_path)[0]
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        for file in os.listdir(extract_dir):
            if file.endswith('.csv') or file.endswith('.csv.gz'):
                file_path = os.path.join(extract_dir, file)
                break
        else:
            raise FileNotFoundError("Aucun fichier .csv ou .csv.gz trouvé dans le zip.")
        return file_path

    def process_dataframe(self,
                          start_date : str,
                          end_date : str,
                          ticker : str,
                          df : pd.DataFrame,
                          num_cryptos_completed : int) -> int:
        """
        Read the dataframe and process it to create the kline
        Args:
            start_date (int): Start date of the data in timestamp UTC
            end_date (int): End date of the data in timestamp UTC
            ticker (str): Ticker name
            df (pd.DataFrame): Dataframe to process
        Returns:
            num_cryptos_completed: True if the first date is greater than the end date (end of backtest), False otherwise
        """
        if df['E'].iloc[0] > end_date:
            num_cryptos_completed+=1
            return num_cryptos_completed
        
        df : pd.DataFrame = df[(df['E'] >= start_date) & (df['E'] <= end_date)].copy()

        if df.empty:
            return num_cryptos_completed

        print(datetime.datetime.fromtimestamp(int((df["E"].iloc[0]-7_200_000)/1_000_000)))
        for kline in df.values:
            kline = self.create_kline_1s(ticker, kline)
            if ticker.endswith('USDT'):
                self.update_rolling_window(kline)
                self.update_klines(kline)
            else:
                self.update_mini_ticker(kline)
        return num_cryptos_completed
    

class Datas:
    path_ = r'bot/data/historical_datas'
    path_files_klines = []
    path_files_rolling = []
    path_files_mini_ticker = []
    end_of_the_file = False
    COLUMNS_NAMES = ["t", "o", "h", "l", "c", "v", "E", "q", "n", "V", "Q", "B"]
    def __init__(self, parameters, strategy=None):
        self.list_tickers: list[str] = parameters.GLOBAL_PARAMETERS['LIST_TICKERS']
        self.strategy = strategy
        self.start_date: datetime.datetime = parameters.GLOBAL_PARAMETERS['START_DATE']
        self.end_date: datetime.datetime = parameters.GLOBAL_PARAMETERS['END_DATE']
        self.data_manager: DataManager = DataManager()
        if not Datas.path_files_klines:
            Datas.path_files_klines = [
                os.path.join(Datas.path_, 'kline1m', f'{ticker}.txt')
                for ticker in self.list_tickers if ticker.endswith('USDT')
            ]
        if not Datas.path_files_rolling:
            Datas.path_files_rolling = [
                os.path.join(Datas.path_, 'historical_window_1h', f'{ticker}.txt')
                for ticker in self.list_tickers if ticker.endswith('USDT')
            ]
        if not Datas.path_files_mini_ticker:
            Datas.path_files_mini_ticker = [
                os.path.join(Datas.path_, 'mini_ticker', f'{ticker}.txt')
                for ticker in self.list_tickers if not ticker.endswith('USDT')
            ]

    def set_strategy(self, strategy : Strategy):
        self.strategy = strategy

    def build_path(self, symbol, month):
        base_folder = (
            r"./"
            r"bot/data/historical_datas_from_api/zip_klines/data/spot/monthly/klines"
        )
        path = (
            f"{base_folder}/{symbol}/1s/2025-01-01_2025-04-30/"
            f"{symbol}-1s-{month}.zip"
        )
        return path

    def generate_list_month(self):
        
        current = datetime.datetime(self.start_date.year, self.start_date.month, 1)
        end_month = datetime.datetime(self.end_date.year, self.end_date.month, 1)

        month_list = [i.strftime("%Y-%m") for i in pd.date_range(start=current, end=end_month, freq='MS')]
        return month_list

    def fill_dict_time(self, month):
        print(f"\n Traitement du mois : {month}")

        start_date_timestamp = int(self.start_date.timestamp() * 1_000_000)
        end_date_timestamp = int(self.end_date.timestamp() * 1_000_000)

        generators = []

        for i, symbol in enumerate(PAIRS_FOR_BACKTEST):
            file_path = self.build_path(symbol, month)
            file_path_csv = self.data_manager.extract_zip_stream(file_path)
            gen = pd.read_csv(file_path_csv, chunksize=1_000, compression='infer', names = self.COLUMNS_NAMES)
            generators.append((symbol, gen))
            print(i)

        #Lecture par chunks de 1000 lignes
        while True:
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
                raise EndOfBacktest()

            # Traitement des chunks du mois en cours
            # Chaque chunk représente 1000 lignes d'un ticker
            self.data_manager.dict_time = defaultdict(list) #On reset le dictionnaire des events avant chaque nouvelles 1000 lignes traitées
            num_cryptos_completed = 0
            for symbol, chunk in chunks:
                print(symbol)
                if chunk is not None:
                    num_cryptos_completed = self.data_manager.process_dataframe(start_date_timestamp, 
                                                                                end_date_timestamp, 
                                                                                symbol, 
                                                                                chunk,
                                                                                num_cryptos_completed)
                    if num_cryptos_completed == len(PAIRS_FOR_BACKTEST):
                        raise EndOfBacktest()
            sorted_items = dict(sorted(self.data_manager.dict_time.items(), key=lambda item: item[0]))

            #print()
            #print(len(sorted_items))
            #print("Temps pris pour former le dicitonnaire :", t2-t1)
            yield sorted_items


class EndOfBacktest(Exception):
    pass