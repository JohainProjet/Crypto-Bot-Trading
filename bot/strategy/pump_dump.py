import datetime
import numpy as np
from bot.utils.helpers import Portfolio, Parameters
from bot.strategy.base_strategy import Strategy
from bot.trading.backtesting import BackTesting
from bot.trading.live_trading import LiveTrading


class PumpDump(Strategy):

    COLUMN_MAPPING = {
        ("Variation", "3m"): 0, ("Variation", "1h"): 1,
        ("Volume", "3m"): 2, ("Volume", "1h"): 3,
        ("NbOfTrades", "3m"): 4, ("NbOfTrades", "1h"): 5,
        ("Price is going up", ""): 6
    }

    def __init__(self,
                parameters : Parameters,
                portfolio : Portfolio,
                duration_time : int,
                is_test_mode : str,
                start_date,
                end_date):
        if duration_time <= 0:
            raise ValueError("durationTime must be positive.")
        if not isinstance(is_test_mode, str):
            raise TypeError("isTestMode must be a string.")
        super().__init__(duration_time, is_test_mode)
        self.tickers_pairs = self.get_ticker_pairs()
        self.parameters = parameters
        self.data_storage = self.create_dataframe_for_storage()
        self.ticker_mapping = {}
        self.next_free_index = 0

        self.start_date = start_date
        self.end_date = end_date
        if is_test_mode in ['TEST', 'PROD']:
            self.trading_manager = LiveTrading(
                is_test_mode,
                portfolio,
                duration_time,
                self.tickers_pairs
            )
        else:
            self.trading_manager = BackTesting(
                is_test_mode,
                portfolio,
                duration_time,
                self.tickers_pairs,
                start_date,
                end_date)

    @staticmethod
    def get_ticker_pairs():
        with open(r"bot\data\list_all_pairs.txt", 'r', encoding='utf-8') as f:
            list_tickers = f.read().splitlines()
        return list_tickers

    def define_stop_losses(self, ticker, entry_price):
        step_size, tick_size = self.trading_manager.get_ticker_tick_size(ticker)
        self.parameters.ticker_bought_actual_max_price[ticker] = {'entry_price' : entry_price,
                                                                'stepSize' : step_size,
                                                                'tickSize' : tick_size}
        scaled_price = self.parameters.stop_loss_price * entry_price
        price_step = scaled_price // tick_size
        stop_loss_price = round(price_step*tick_size,8)
        quantity = self.trading_manager.portfolio.actifs[ticker]['quantity']
        quantity_step = quantity//step_size
        quantity_bought = str(round(quantity_step*step_size,8))
        print("Entry_price : ", entry_price, "StopPrice : ", stop_loss_price)
        self.trading_manager.place_stop_loss(ticker, quantity_bought, stop_loss_price)

    @staticmethod
    def create_dataframe_for_storage():
        return np.full((300, len(PumpDump.COLUMN_MAPPING)), np.inf, dtype=np.float32)

    def get_ticker_index(self, ticker):
        if ticker not in self.ticker_mapping:
            if self.next_free_index >= 300:
                raise ValueError("Plus de place disponible dans le tableau")

            self.ticker_mapping[ticker] = self.next_free_index
            self.next_free_index += 1

        return self.ticker_mapping[ticker]

    def detect_pump(self, ticker):
        if ticker in self.parameters.crypto_bought:
            return False
        row_idx = self.get_ticker_index(ticker)

        variation_3m = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Variation", "3m")]]
        variation_1h = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Variation", "1h")]]

        #print("Variation", variation_3m, variation_1h,
        #self.parameters.limits['variation']*variation_3m <= variation_1h)

        if self.parameters.limits['variation']*variation_3m <= variation_1h:
            return False

        volume_3m = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Volume", "3m")]]
        volume_1h = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Volume", "1h")]]

        #print("Volume", volume_3m, volume_1h,
        # self.parameters.limits['volume']*volume_3m <= volume_1h)

        if self.parameters.limits['volume']*volume_3m <= volume_1h:
            return False

        nb_of_trades_3m = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("NbOfTrades", "3m")]]
        nb_of_trades_1h = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("NbOfTrades", "1h")]]

        #print("NbOftrades", nb_of_trades_3m, nb_of_trades_1h,
        # self.parameters.limits['nbOfTrades']*nb_of_trades_3m <= nb_of_trades_1h)

        if self.parameters.limits['nbOfTrades']*nb_of_trades_3m <= nb_of_trades_1h:
            return False

        price_is_going_up = self.data_storage[
            row_idx, PumpDump.COLUMN_MAPPING[("Price is going up", "")]
        ]

        #print('Price is going up', price_is_going_up)

        if not price_is_going_up:
            return False
        if price_is_going_up == np.float32('inf'):
            return False
        return True

    def take_decision(self, data):
        k = data['k']
        ticker = k['s']
        close_price = float(k['c'])
        pump_detected = self.detect_pump(ticker)
        #if isinstance(self.tradingManager, LiveTrading):
        #    now = datetime.datetime.now()
        #elif isinstance(self.tradingManager, BackTesting):
        now = datetime.datetime.fromtimestamp(int(data['E'])/1000)
        if pump_detected:
            cash_used = '10'
            if now.minute % 15 == 0:
                cash_used = '30'
            try:
                self.trading_manager.portfolio.check_buy_sell(
                    'BUY',
                    ticker,
                    float(cash_used)/close_price, close_price
                )
                self.trading_manager.buy(ticker, float(cash_used), close_price, data['E'])
            except AssertionError:
                print(f'Order to buy {ticker} was not send, not enough cash on portfolio.')
            self.parameters.crypto_bought.append(ticker)

        #Les deux dict doivent être fusionnés
        if (ticker in self.trading_manager.portfolio.actifs and
            ticker in self.parameters.ticker_bought_actual_max_price):
            #print(ticker, close_price,
            # self.parameters.ticker_bought_actual_max_price[ticker]['entry_price'])
            if close_price > self.parameters.ticker_bought_actual_max_price[ticker]['entry_price']:

                self.parameters.ticker_bought_actual_max_price[ticker]['entry_price'] = close_price
                step_size = self.parameters.ticker_bought_actual_max_price[ticker]['stepSize']
                tick_size = self.parameters.ticker_bought_actual_max_price[ticker]['tickSize']

                quantity = self.trading_manager.portfolio.actifs[ticker]['quantity']
                quantity_step = quantity // step_size
                quantity_bought = str(round(quantity_step*step_size,8))

                scaled_price = self.parameters.stop_loss_price * close_price
                price_step = scaled_price // tick_size
                new_stop_loss_price = round(price_step*tick_size,8)
                print("NEW STOP LOSS PRICE", new_stop_loss_price)
                self.trading_manager.cancel_replace(ticker, quantity_bought, new_stop_loss_price)

    def update_parameters(self, websocket_stream, k):
        ticker = k['s']
        variation = float(k['h'])-float(k['l'])
        volume = float(k['v'])
        nb_of_trades = k['n']
        row_idx = self.get_ticker_index(ticker)

        self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Variation", websocket_stream)]] = variation
        self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Volume", websocket_stream)]] = volume
        self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("NbOfTrades", websocket_stream)]] = nb_of_trades

        if websocket_stream == '3m':
            price_is_going_up = bool(float(k['c']) > float(k['o']))
            self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Price is going up", "")]] = price_is_going_up
