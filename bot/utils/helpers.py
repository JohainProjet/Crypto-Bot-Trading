import datetime
import time
import json
from dataclasses import dataclass
from dataclasses import field
import pandas as pd
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient


pd.set_option('display.float_format', lambda x: '%.10f' % x)

def load_tickers(list_tickers=[]):
    if not list_tickers:
        with open(r"bot/data/list_all_pairs.txt", 'r', encoding='utf-8') as f:
            list_tickers = f.read().splitlines()
    return list_tickers

@dataclass
class Parameters:
    GLOBAL_PARAMETERS : dict = field(default_factory=dict)
    SPECIFIC_PARAMETERS : dict = field(default_factory=dict)

class Portfolio:
    def __init__(self, program_type : str, cash : float, actifs : dict = {}):
        self.program_type : str = program_type
        self.creation_date : datetime.datetime = datetime.datetime.now()
        self.current_cash : float = cash
        self.initial_cash : float = cash
        self.actifs : dict[str, float] = actifs

        self.current_btc_usdt_price = None
        self.current_usdc_try_price = None

        self.df_transaction_history = pd.DataFrame(
            columns=['Time',
                     'Type',
                     'Ticker',
                     'Quantity',
                     'Ticker price',
                     'Cash cost']
        )

    def __str__(self):
        return (f'Cash : {self.current_cash} \n'
                f'Actifs : {self.actifs} \n'
                f'Transaction history : {self.df_transaction_history}')

    def check_buy_sell(self, transaction_type : str, pair : str, quantity : float, pair_price : float):
        """
        Check if it's possible to buy or sell

        Args:
            transaction_type (str): BUY or SELL.
            pair (str): Current pair to check.
            quantity (float): Current quantity to check.
            pair_price (float): The current price of pair.
        Raises:
            AssertionError
        """

        if transaction_type == 'BUY':
            assert self.current_cash >= quantity*pair_price, 'Transaction failed, not enough cash.'
        elif transaction_type == 'SELL':
            assert pair in self.actifs, 'Transaction failed, asset is not in portfolio.'

    @staticmethod
    def get_quoted_asset(pair : str):
        """
        Get quoted asset
        """
        if pair.endswith('USDC'):
            quote_asset = 'USDC'
        elif pair.endswith('BTC'):
            quote_asset = 'BTC'
        elif pair.endswith('TRY'):
            quote_asset = 'TRY'
        return quote_asset

    def convert_price_to_usdt(self, current_price : float, quote_asset : str)->float:
        """
        Convert the current price from BTC or TRY to USDT.

        Args:
            current_price (float): Current price of the pair.
            quote_asset (str): Quote asset of the current price (BTC/USDC/TRY):
        Returns:
            final_price (float): Price in USDT
        """
        if quote_asset == 'USDC':
            final_price = current_price
        elif quote_asset == 'BTC':
            final_price = current_price*self.current_btc_usdt_price
        elif quote_asset == 'TRY':
            final_price = current_price/self.current_usdc_try_price
        return final_price

    def transaction_order(self, 
                          transaction_type : str, 
                          transaction_time : datetime.datetime, 
                          pair : str, 
                          quantity : float, 
                          ticker_price : float):

        quote_asset = self.get_quoted_asset(pair)
        ticker_price_usdt = self.convert_price_to_usdt(ticker_price, quote_asset)
        self.check_buy_sell(transaction_type, pair, quantity, ticker_price_usdt)
        commission = self.calculate_transaction_fees(quantity)
        if transaction_type == 'BUY':
            cash_cost = quantity * ticker_price_usdt
            quantity -= commission
        elif transaction_type == 'SELL':
            cash_cost = (quantity - commission) * ticker_price_usdt
        if transaction_type == 'BUY':
            self.execute_buy(transaction_time, pair, quantity, ticker_price, cash_cost)
        elif transaction_type == 'SELL':
            self.execute_sell(transaction_time, pair, quantity, ticker_price, cash_cost)
        return None

    def execute_buy(self, 
                    transaction_time : datetime.datetime, 
                    ticker : str, 
                    quantity : float, 
                    entry_price : float, 
                    cash_paid : float):
        if ticker not in self.actifs:
            self.actifs[ticker] = {"quantity" : quantity,
                                   "entry_price" : entry_price,
                                   'current_price' : entry_price}
        else:
            self.actifs[ticker]['quantity'] += quantity
            self.actifs[ticker]['entry_price'] = entry_price
        self.current_cash -= cash_paid
        self.add_to_transaction_history('BUY', transaction_time, ticker, quantity, entry_price, - cash_paid)
        return None

    def execute_sell(self, 
                     transaction_time : datetime.datetime, 
                     ticker : str, 
                     quantity : float, 
                     ticker_price : float, 
                     cash_receive : float):
        quantity = min(quantity, self.actifs[ticker]['quantity'])
        self.actifs[ticker]['quantity']-=quantity
        self.current_cash += cash_receive
        self.add_to_transaction_history('SELL', transaction_time, ticker, quantity, ticker_price, cash_receive)
        del self.actifs[ticker]
 
    @staticmethod
    def calculate_transaction_fees(quantity : float, commission_asset = None)->float:
        """ fees in commission asset """
        fees_transaction = 0.0009500
        if commission_asset == 'BNB':
            fees_transaction = 0.0007125
        return quantity * fees_transaction

    def add_to_transaction_history(self,
                                   transaction_type : str,
                                   transaction_time : datetime.datetime,
                                   ticker : str, 
                                   quantity : float,
                                   ticker_price : float,
                                   cash_operation : float):
        """ Add current transaction to the dataframe of transaction history """
        transaction = {
            'Time' : transaction_time,
            'Type' : transaction_type,
            'Ticker' : ticker,
            'Quantity' : quantity,
            'Ticker price' : ticker_price,
            'Cash cost' : round(cash_operation, 2)
        }
        if self.df_transaction_history.empty:
            self.df_transaction_history = pd.DataFrame([transaction])
        else:
            self.df_transaction_history = pd.concat(
            [
                self.df_transaction_history,
                pd.DataFrame([transaction])
            ],
            ignore_index = True
        )
        return None

    def save(self, start_date, current_cash, assets_value):
        with open(r'bot/results/results.txt', 'a', encoding='utf-8') as f:
            f.write(f"Start Date : {start_date} |"
                    f"End Date : {datetime.datetime.now()} |"
                    f"Cash : {current_cash} |",
                    f"Assets_value : {assets_value} |",
                    f"Portfolio_change : {((current_cash+assets_value)/self.initial_cash - 1)*100:.2f}%\n")

    def get_assets_value(self):
        assets_value = 0
        for pair, dict_ in self.actifs.items():
            quote_asset = self.get_quoted_asset(pair)
            current_price_in_quote_quantity = float(dict_['current_price'])
            ticker_price_usdt = self.convert_price_to_usdt(current_price_in_quote_quantity, quote_asset)
            assets_value += dict_['quantity'] * ticker_price_usdt
        return assets_value

    def evaluate_portfolio_value(self, save_to_file = False, verbose = True):
        assets_value = self.get_assets_value()
        portfolio_value = self.current_cash+assets_value
        if verbose:
            print('---------------')
            print(f'Valeur du cash : {self.current_cash}')
            print(f'Valeur des actifs : {assets_value}')
            print(f'Valeur du Portefeuille : {portfolio_value}')
            print('---------------')
        if save_to_file:
            self.save(self.creation_date, self.current_cash, assets_value)
        return self.current_cash, assets_value

    def update_portfolio_value(self, pair, current_price):
        self.actifs[pair]['current_price'] = current_price

def periodic_sleep(total_duration, interval):
    elapsed_time = 0

    while elapsed_time < total_duration:
        time.sleep(interval)
        elapsed_time += interval

        remaining_time = total_duration- elapsed_time
        print(f"Temps écoulé : {elapsed_time} secondes. Temps restant : {remaining_time} secondes.")


TRADING_PAIRS = {'1000CAT': {'USDC', 'TRY', 'USDT'},
					'1000CHEEMS': {'USDC', 'USDT'},
					'1000SATS': {'USDC', 'TRY', 'USDT'},
					'1INCH': {'BTC', 'USDT'},
					'1MBABYDOGE': {'USDC', 'TRY', 'USDT'},
					'AAVE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ACA': {'TRY', 'BTC', 'USDT'},
					'ACE': {'TRY', 'USDT'},
					'ACH': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ACT': {'USDC', 'TRY', 'USDT'},
					'ACX': {'USDC', 'TRY', 'USDT'},
					'ADA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ADX': {'BTC', 'USDT'},
					'AEVO': {'TRY', 'BTC', 'USDT'},
					'AGLD': {'BTC', 'USDT'},
					'AI': {'TRY', 'BTC', 'USDT'},
					'AIXBT': {'USDC', 'TRY', 'USDT'},
					'ALGO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ALICE': {'TRY', 'USDT'},
					'ALPINE': {'TRY', 'USDT'},
					'ALT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AMP': {'TRY', 'USDT'},
					'ANIME': {'USDC', 'TRY', 'USDT'},
					'ANKR': {'TRY', 'BTC', 'USDT'},
					'APE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'API3': {'USDC', 'TRY', 'BTC', 'USDT'},
					'APT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AR': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ARB': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ARDR': {'BTC', 'USDT'},
					'ARK': {'TRY', 'USDT'},
					'ARKM': {'USDC', 'BTC', 'TRY', 'USDT'},
					'ARPA': {'TRY', 'BTC', 'USDT'},
					'ASR': {'TRY', 'USDT'},
					'ASTR': {'BTC', 'USDT'},
					'ATA': {'BTC', 'USDT'},
					'ATM': {'TRY', 'USDT'},
					'ATOM': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AUCTION': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AUDIO': {'TRY', 'BTC', 'USDT'},
					'AVA': {'BTC', 'USDT'},
					'AVAX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AXL': {'TRY', 'BTC', 'USDT'},
					'AXS': {'TRY', 'BTC', 'USDT'},
					'BABY': {'USDC', 'TRY', 'USDT'},
					'BAKE': {'TRY', 'BTC', 'USDT'},
					'BANANA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BANANAS31': {'USDC', 'USDT'},
					'BAND': {'BTC', 'USDT'},
					'BAR': {'TRY', 'USDT'},
					'BAT': {'BTC', 'USDT'},
					'BB': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BCH': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BEAMX': {'USDC', 'TRY', 'USDT'},
					'BEL': {'TRY', 'BTC', 'USDT'},
					'BERA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BICO': {'BTC', 'USDT'},
					'BIGTIME': {'USDC', 'USDT'},
					'BIO': {'USDC', 'TRY', 'USDT'},
					'BLUR': {'USDC', 'TRY', 'USDT'},
					'BMT': {'USDC', 'TRY', 'USDT'},
					'BNB': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BOME': {'USDC', 'TRY', 'USDT'},
					'BONK': {'USDC', 'TRY', 'USDT'},
					'BROCCOLI714': {'USDC', 'USDT'},
					'BSW': {'TRY', 'USDT'},
					'BTC': {'USDC', 'TRY', 'USDT'},
					'BTTC': {'TRY', 'USDT'},
					'CAKE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'CATI': {'USDC', 'TRY', 'USDT'},
					'CELO': {'TRY', 'BTC', 'USDT'},
					'CETUS': {'USDC', 'TRY', 'USDT'},
					'CFX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'CGPT': {'USDC', 'USDT'},
					'CHESS': {'USDC', 'USDT'},
					'CHR': {'BTC', 'USDT'},
					'CHZ': {'USDC', 'TRY', 'BTC', 'USDT'},
					'CITY': {'TRY', 'USDT'},
					'CKB': {'USDC', 'TRY', 'USDT'},
					'COMP': {'TRY', 'BTC', 'USDT'},
					'COOKIE': {'USDC', 'USDT'},
					'COS': {'TRY', 'USDT'},
					'COTI': {'TRY', 'BTC', 'USDT'},
					'COW': {'USDC', 'TRY', 'USDT'},
					'CRV': {'USDC', 'TRY', 'BTC', 'USDT'},
					'CTK': {'BTC', 'USDT'},
					'CTSI': {'BTC', 'USDT'},
					'CVC': {'USDC', 'USDT'},
					'CYBER': {'TRY', 'BTC', 'USDT'},
					'D': {'TRY', 'USDT'},
					'DASH': {'BTC', 'USDT'},
					'DATA': {'BTC', 'USDT'},
					'DENT': {'TRY', 'USDT'},
					'DEXE': {'USDT'},
					'DF': {'USDC', 'USDT'},
					'DIA': {'BTC', 'USDT'},
					'DODO': {'BTC', 'USDT'},
					'DOGE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'DOGS': {'USDC', 'TRY', 'USDT'},
					'DOT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'DUSK': {'BTC', 'USDT'},
					'DYDX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'DYM': {'TRY', 'USDT'},
					'EDU': {'TRY', 'USDT'},
					'EGLD': {'USDC', 'TRY', 'BTC', 'USDT'},
					'EIGEN': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ENA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ENJ': {'TRY', 'BTC', 'USDT'},
					'ENS': {'USDC', 'TRY', 'BTC', 'USDT'},
					'EOS': {'USDC', 'TRY', 'BTC', 'USDT'},
					'EPIC': {'USDC', 'USDT'},
					'ETC': {'TRY', 'BTC', 'USDT'},
					'ETH': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ETHFI': {'USDC', 'TRY', 'USDT'},
					'FET': {'USDC', 'TRY', 'BTC', 'USDT'},
					'FIDA': {'TRY', 'BTC', 'USDT'},
					'FIL': {'USDC', 'TRY', 'BTC', 'USDT'},
					'FIO': {'BTC', 'USDT'},
					'FIS': {'BTC', 'USDT'},
					'FLM': {'BTC', 'USDT'},
					'FLOKI': {'USDC', 'TRY', 'USDT'},
					'FLOW': {'BTC', 'USDT'},
					'FLUX': {'BTC', 'USDT'},
					'FORM': {'TRY', 'USDT', 'USDC'},
					'FORTH': {'BTC', 'USDT'},
					'G': {'TRY', 'USDT'},
					'GALA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'GAS': {'TRY', 'BTC', 'USDT'},
					'GHST': {'USDT'},
					'GLM': {'BTC', 'USDT'},
					'GLMR': {'BTC', 'USDT'},
					'GMT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'GMX': {'USDC', 'USDT'},
					'GPS': {'USDC', 'TRY', 'USDT'},
					'GRT': {'TRY', 'BTC', 'USDT'},
					'GUN': {'USDC', 'TRY', 'USDT'},
					'HBAR': {'USDC', 'TRY', 'BTC', 'USDT'},
					'HEI': {'USDC', 'BTC', 'USDT'},
					'HFT': {'BTC', 'USDT'},
					'HIGH': {'TRY', 'USDT'},
					'HIVE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'HMSTR': {'USDC', 'TRY', 'USDT'},
					'HOT': {'TRY', 'USDT'},
					'HYPER': {'USDC', 'TRY', 'USDT'},
					'ICP': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ICX': {'BTC', 'USDT'},
					'ID': {'TRY', 'BTC', 'USDT'},
					'IDEX': {'USDC', 'USDT'},
					'ILV': {'BTC', 'USDT'},
					'IMX': {'BTC', 'USDT'},
					'INIT': {'USDC', 'TRY', 'USDT'},
					'INJ': {'USDC', 'TRY', 'BTC', 'USDT'},
					'IO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'IOTA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'IOTX': {'BTC', 'USDT'},
					'JASMY': {'TRY', 'USDT'},
					'JOE': {'BTC', 'USDT'},
					'JST': {'BTC', 'USDT'},
					'JTO': {'USDC', 'TRY', 'USDT'},
					'JUP': {'USDC', 'TRY', 'USDT'},
					'JUV': {'USDC', 'TRY', 'USDT'},
					'KAIA': {'USDC', 'USDT'},
					'KAITO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'KAVA': {'BTC', 'USDT'},
					'KDA': {'BTC', 'USDT'},
					'KERNEL': {'TRY', 'USDT', 'USDC'},
					'KMD': {'BTC', 'USDT'},
					'KNC': {'BTC', 'USDT'},
					'KSM': {'TRY', 'BTC', 'USDT'},
					'LAYER': {'USDC', 'TRY', 'BTC', 'USDT'},
					'LAZIO': {'TRY', 'USDT'},
					'LDO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'LEVER': {'TRY', 'USDT'},
					'LINK': {'USDC', 'TRY', 'BTC', 'USDT'},
					'LISTA': {'TRY', 'USDT'},
					'LOKA': {'BTC', 'USDT'},
					'LPT': {'TRY', 'BTC', 'USDT'},
					'LQTY': {'USDT'},
					'LRC': {'TRY', 'BTC', 'USDT'},
					'LSK': {'BTC', 'USDT'},
					'LTC': {'USDC', 'TRY', 'BTC', 'USDT'},
					'LTO': {'BTC', 'USDT'},
					'LUMIA': {'TRY', 'USDT'},
					'LUNA': {'TRY', 'USDT'},
					'LUNC': {'TRY', 'USDT'},
					'MAGIC': {'TRY', 'BTC', 'USDT'},
					'MANA': {'TRY', 'BTC', 'USDT'},
					'MANTA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'MASK': {'TRY', 'USDT'},
					'MAV': {'TRY', 'BTC', 'USDT'},
					'MBOX': {'TRY', 'USDT'},
					'ME': {'TRY', 'BTC', 'USDT'},
					'MEME': {'USDC', 'TRY', 'USDT'},
					'METIS': {'TRY', 'USDT'},
					'MINA': {'TRY', 'BTC', 'USDT'},
					'MKR': {'USDC', 'TRY', 'BTC', 'USDT'},
					'MOVE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'MOVR': {'TRY', 'BTC', 'USDT'},
					'MTL': {'BTC', 'USDT'},
					'MUBARAK': {'USDC', 'USDT'},
					'NEAR': {'USDC', 'TRY', 'BTC', 'USDT'},
					'NEIRO': {'USDC', 'TRY', 'USDT'},
					'NEO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'NEXO': {'BTC', 'USDT'},
					'NFP': {'TRY', 'BTC', 'USDT'},
					'NIL': {'USDC', 'TRY', 'USDT'},
					'NKN': {'BTC', 'USDT'},
					'NMR': {'BTC', 'USDT'},
					'NOT': {'USDC', 'TRY', 'USDT'},
					'NTRN': {'TRY', 'USDT'},
					'OG': {'TRY', 'BTC', 'USDT'},
					'OGN': {'TRY', 'BTC', 'USDT'},
					'OM': {'USDC', 'TRY', 'BTC', 'USDT'},
					'OMNI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ONDO': {'USDC', 'TRY', 'USDT'},
					'ONE': {'TRY', 'BTC', 'USDT'},
					'ONG': {'BTC', 'USDT'},
					'ONT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'OP': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ORCA': {'USDC', 'TRY', 'USDT'},
					'ORDI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'OSMO': {'USDC', 'USDT'},
					'OXT': {'BTC', 'USDT'},
					'PARTI': {'USDC', 'TRY', 'USDT'},
					'PAXG': {'USDC', 'TRY', 'BTC', 'USDT'},
					'PENDLE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'PENGU': {'USDC', 'TRY', 'USDT'},
					'PEOPLE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'PEPE': {'USDC', 'TRY', 'USDT'},
					'PHA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'PHB': {'TRY', 'BTC', 'USDT'},
					'PIVX': {'BTC', 'USDT'},
					'PIXEL': {'USDC', 'TRY', 'USDT'},
					'PNUT': {'USDC', 'BTC', 'TRY', 'USDT'},
					'POL': {'TRY', 'BTC', 'USDT', 'USDC'},
					'POLYX': {'TRY', 'BTC', 'USDT'},
					'PORTAL': {'TRY', 'BTC', 'USDT'},
					'PORTO': {'TRY', 'USDT'},
					'POWR': {'BTC', 'USDT'},
					'PSG': {'TRY', 'USDT'},
					'PYR': {'BTC', 'USDT'},
					'PYTH': {'USDC', 'TRY', 'BTC', 'USDT'},
					'QNT': {'USDC', 'BTC', 'USDT'},
					'QTUM': {'TRY', 'BTC', 'USDT'},
					'RAD': {'TRY', 'USDT'},
					'RARE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'RAY': {'USDC', 'TRY', 'USDT'},
					'RDNT': {'TRY', 'USDT'},
					'RED': {'USDC', 'TRY', 'BTC', 'USDT'},
					'RENDER': {'USDC', 'TRY', 'BTC', 'USDT'},
					'REQ': {'BTC', 'USDT'},
					'REZ': {'USDC', 'TRY', 'USDT'},
					'RIF': {'BTC', 'USDT'},
					'RLC': {'BTC', 'USDT'},
					'RONIN': {'TRY', 'BTC', 'USDT'},
					'ROSE': {'TRY', 'BTC', 'USDT'},
					'RPL': {'USDC', 'USDT'},
					'RSR': {'USDC', 'TRY', 'USDT'},
					'RUNE': {'USDC', 'BTC', 'USDT'},
					'RVN': {'TRY', 'BTC', 'USDT'},
					'S': {'TRY', 'BTC', 'USDT', 'USDC'},
					'SAGA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SAND': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SANTOS': {'TRY', 'BTC', 'USDT'},
					'SCR': {'TRY', 'BTC', 'USDT'},
					'SCRT': {'BTC', 'USDT'},
					'SEI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SFP': {'BTC', 'USDT'},
					'SHELL': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SHIB': {'USDC', 'TRY', 'USDT'},
					'SKL': {'TRY', 'BTC', 'USDT'},
					'SLF': {'TRY', 'BTC', 'USDT', 'USDC'},
					'SLP': {'TRY', 'USDT'},
					'SNX': {'TRY', 'BTC', 'USDT'},
					'SOL': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SOLV': {'TRY', 'USDT'},
					'SPELL': {'TRY', 'USDT'},
					'SSV': {'BTC', 'USDT'},
					'STEEM': {'USDC', 'BTC', 'USDT'},
					'STG': {'BTC', 'USDT'},
					'STORJ': {'TRY', 'BTC', 'USDT'},
					'STPT': {'BTC', 'USDT'},
					'STRAX': {'TRY', 'BTC', 'USDT'},
					'STRK': {'USDC', 'TRY', 'BTC', 'USDT'},
					'STX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SUI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SUN': {'TRY', 'USDT'},
					'SUPER': {'TRY', 'BTC', 'USDT'},
					'SUSHI': {'TRY', 'BTC', 'USDT'},
					'SXP': {'TRY', 'BTC', 'USDT'},
					'SYN': {'USDC', 'USDT'},
					'SYS': {'BTC', 'USDT'},
					'T': {'USDC', 'USDT'},
					'TAO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TFUEL': {'BTC', 'USDT'},
					'THE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'THETA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TIA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TLM': {'USDC', 'TRY', 'USDT'},
					'TNSR': {'USDC', 'TRY', 'USDT'},
					'TON': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TRB': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TRU': {'TRY', 'BTC', 'USDT'},
					'TRUMP': {'USDC', 'TRY', 'USDT'},
					'TRX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TST': {'USDC', 'TRY', 'USDT'},
					'TURBO': {'USDC', 'TRY', 'USDT'},
					'TUT': {'USDC', 'USDT'},
					'TWT': {'TRY', 'USDT'},
					'UMA': {'TRY', 'BTC', 'USDT'},
					'UNI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'USTC': {'TRY', 'USDT'},
					'USUAL': {'USDC', 'TRY', 'BTC', 'USDT'},
					'UTK': {'USDC', 'USDT'},
					'VANA': {'USDC', 'TRY', 'USDT'},
					'VANRY': {'USDC', 'TRY', 'USDT'},
					'VELODROME': {'USDC', 'USDT'},
					'VET': {'USDC', 'TRY', 'BTC', 'USDT'},
					'VIC': {'TRY', 'USDT'},
					'VIRTUAL': {'USDC', 'USDT'},
					'VOXEL': {'USDT'},
					'VTHO': {'TRY', 'USDT'},
					'W': {'USDC', 'TRY', 'BTC', 'USDT'},
					'WAN': {'BTC', 'USDT'},
					'WAXP': {'BTC', 'USDT'},
					'WBETH': {'USDT'},
					'WBTC': {'BTC', 'USDT'},
					'WCT': {'TRY', 'USDT', 'USDC'},
					'WIF': {'USDC', 'TRY', 'BTC', 'USDT'},
					'WLD': {'USDC', 'TRY', 'BTC', 'USDT'},
					'XAI': {'TRY', 'USDT'},
					'XEC': {'TRY', 'USDT'},
					'XLM': {'USDC', 'TRY', 'BTC', 'USDT'},
					'XNO': {'BTC', 'USDT'},
					'XRP': {'USDC', 'TRY', 'BTC', 'USDT'},
					'XTZ': {'USDC', 'BTC', 'USDT'},
					'XVG': {'TRY', 'USDT'},
					'XVS': {'TRY', 'BTC', 'USDT'},
					'YFI': {'BTC', 'USDT'},
					'YGG': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ZEC': {'BTC', 'USDT'},
					'ZEN': {'USDC', 'BTC', 'USDT'},
					'ZIL': {'TRY', 'BTC', 'USDT'},
					'ZK': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ZRO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ZRX': {'BTC', 'USDT'}}


PAIRS_FOR_BACKTEST = ['ETHUSDT', 'LTCUSDT', 'ZILUSDT', 'BTCUSDT', 'THETAUSDC', 'USDCTRY', 'LINKUSDC', 'ETHUSDC', 
                      'REQBTC', 'XLMUSDT', 'SYSUSDT', 'POWRUSDT', 'ATOMUSDC', 'KNCUSDT', 'VETUSDC', 'MANATRY', 
                      'PIVXUSDT', 'ONTUSDC', 'RLCBTC', 'ONGUSDT', 'GASTRY', 'KMDUSDT', 'ONGBTC', 'STORJTRY', 
                      'ADAUSDT', 'HOTUSDT', 'MANAUSDT', 'DATABTC', 'RVNTRY', 'ZILTRY', 'ICXUSDT', 'EOSUSDT', 
                      'XRPUSDC', 'FETUSDC', 'LSKUSDT', 'SYSBTC', 'KMDBTC', 'VETUSDT', 'ARDRBTC', 'BTCUSDC', 
                      'PHBTRY', 'TRXUSDC', 'THETAUSDT', 'DASHBTC', 'LRCUSDT', 'BATUSDT', 'IOTXUSDT', 'GASUSDT',
                      'HOTTRY', 'ZECUSDT', 'ZENUSDT', 'ZENUSDC', 'IOTAUSDT', 'EOSUSDC', 'IOTAUSDC', 'ZRXBTC', 
                      'ZECBTC', 'REQUSDT', 'PIVXBTC', 'ETCUSDT', 'STEEMUSDT', 'ONTUSDT', 'ADAUSDC', 'ADXBTC', 
                      'KNCBTC', 'ZRXUSDT', 'IOTXBTC', 'MTLBTC', 'NEOUSDT', 'ATOMUSDT', 'TRXUSDT', 'ENJUSDT', 
                      'ARDRUSDT', 'ADXUSDT', 'MTLUSDT', 'XLMUSDC', 'NEOUSDC', 'RLCUSDT', 'QTUMTRY', 'DATAUSDT', 
                      'BNBUSDT', 'QTUMUSDT', 'BATBTC', 'LINKUSDT', 'BNBUSDC', 'POWRBTC', 'PHBUSDT', 'ETCTRY', 
                      'LRCTRY', 'LTCUSDC', 'DASHUSDT', 'STORJUSDT', 'XRPUSDT', 'LSKBTC', 'ICXBTC', 'WANBTC', 
                      'RVNUSDT', 'ENJTRY', 'WANUSDT', 'FETUSDT', 'STEEMUSDC']

def generate_parameters_combinaison():
    list_parameters = []

    volumes = [1.5, 1.8, 2.1]
    variations = [1.5, 1.8, 2.1]
    nb_of_trades = [3, 4, 5]
    stop_loss_prices = [0.97, 0.98, 0.99]

    for stop_price in stop_loss_prices:
        for volume in volumes:
            for variation in variations:
                for nbOfTrade in nb_of_trades:
                    limits = {'volume' : volume,
                            'variation' : variation,
                            'nbOfTrades' : nbOfTrade}
                    list_parameters.append((limits, stop_price))
    return list_parameters
if __name__ == '__main__':
    generate_parameters_combinaison()

