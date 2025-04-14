import datetime
import numpy as np
from collections import defaultdict
from bot.utils.helpers import Portfolio, Parameters
from bot.strategy.base_strategy import Strategy
from bot.trading.base_trading import SimulationSaver
from bot.trading.backtesting import BackTesting
from bot.trading.live_trading import LiveTrading


class PumpDump(Strategy):

    COLUMN_MAPPING = {
        ("Variation", "1m"): 0, ("Variation", "1h"): 1,
        ("Volume", "1m"): 2, ("Volume", "1h"): 3,
        ("NbOfTrades", "1m"): 4, ("NbOfTrades", "1h"): 5,
        ("Price is going up", ""): 6
    }

    def __init__(self, parameters : Parameters, portfolio : Portfolio, simulation_saver : SimulationSaver):
        if parameters.duration_time <= 0:
            raise ValueError("durationTime must be positive.")
        if not isinstance(parameters.program_type, str):
            raise TypeError("isTestMode must be a string.")
        super().__init__(parameters.duration_time)
        self.parameters = parameters
        self.portfolio = portfolio
        self.tickers_pairs = parameters.list_tickers
        self.data_storage = self.create_dataframe_for_storage()
        self.ticker_mapping = {}
        self.next_free_index = 0
        self.prices = defaultdict(list)
        self.max_z_score = {}
        self.z_score_hits = False

        self.start_date = parameters.start_date
        self.end_date = parameters.end_date
        if parameters.program_type in ['TEST', 'PROD']:
            self.trading_manager = LiveTrading(
                parameters,
                portfolio,
                self.tickers_pairs,
                simulation_saver
            )
        else:
            self.trading_manager = BackTesting(
                parameters,
                portfolio,
                self.tickers_pairs,
                simulation_saver)

    def define_stop_losses(self, ticker, entry_price):
        step_size, tick_size = self.trading_manager.get_ticker_tick_size(ticker)
        self.parameters.ticker_bought_actual_max_price[ticker] = {'entry_price' : entry_price,
                                                                'stepSize' : step_size,
                                                                'tickSize' : tick_size}
        scaled_price = self.parameters.stop_loss_prct * entry_price
        price_step = scaled_price // tick_size
        stop_loss_price = round(price_step*tick_size,8)
        quantity = self.trading_manager.portfolio.actifs[ticker]['quantity']
        quantity_step = quantity//step_size
        quantity_bought = str(round(quantity_step*step_size,8))
        print('quantity_bought calculate', quantity_bought)
        print("quantity in portfolio", self.portfolio.actifs[ticker]['quantity'])
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
        variation_3m = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Variation", self.parameters.kline_type)]]
        variation_1h = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Variation", "1h")]]

        if self.parameters.limits['variation']*variation_3m <= variation_1h:
            return False

        volume_3m = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Volume", self.parameters.kline_type)]]
        volume_1h = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Volume", "1h")]]

        #print("Volume", volume_3m, volume_1h)

        if self.parameters.limits['volume']*volume_3m <= volume_1h:
            return False

        nb_of_trades_3m = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("NbOfTrades", self.parameters.kline_type)]]
        nb_of_trades_1h = self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("NbOfTrades", "1h")]]

        print("NbOftrades", nb_of_trades_3m, nb_of_trades_1h)

        if self.parameters.limits['nbOfTrades']*nb_of_trades_3m <= nb_of_trades_1h:
            return False

        price_is_going_up = self.data_storage[
            row_idx, PumpDump.COLUMN_MAPPING[("Price is going up", "")]
        ]

        print('Price is going up', price_is_going_up)

        if not price_is_going_up:
            return False
        if price_is_going_up == np.float32('inf'):
            return False

        return True

    def take_decision(self, data):
        k = data['k']
        ticker = k['s'][:-4]+'USDC'
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
            mean_window_size = self.parameters.mean_rolling_size
            std_window_size = self.parameters.std_rolling_size

            current_z_score = (close_price - np.mean(self.prices[ticker][-mean_window_size:])) / np.std(self.prices[ticker][-std_window_size:])
            max_z_score = self.max_z_score.get(ticker, 0)

            self.max_z_score[ticker] = max(max_z_score, current_z_score)
            threshold = 1
            print(ticker, current_z_score, close_price, np.mean(self.prices[ticker][-mean_window_size:]), np.std(self.prices[ticker][-std_window_size:]))
            if close_price > self.parameters.ticker_bought_actual_max_price[ticker]['entry_price'] and not self.z_score_hits:
                self.parameters.ticker_bought_actual_max_price[ticker]['entry_price'] = close_price
                step_size = self.parameters.ticker_bought_actual_max_price[ticker]['stepSize']
                tick_size = self.parameters.ticker_bought_actual_max_price[ticker]['tickSize']
                #Peut-être récupérer la quantité du portfolio à la place de calculer la quantité achetée
                quantity = self.trading_manager.portfolio.actifs[ticker]['quantity']
                quantity_step = quantity // step_size
                quantity_bought = str(round(quantity_step*step_size,8))

                scaled_price = self.parameters.stop_loss_prct * close_price
                price_step = scaled_price // tick_size
                new_stop_loss_price = round(price_step*tick_size,8)
                print("NEW STOP LOSS PRICE", new_stop_loss_price)
                self.trading_manager.cancel_replace(ticker, quantity_bought, new_stop_loss_price)
            elif current_z_score < threshold and self.max_z_score[ticker] > threshold:
                step_size = self.parameters.ticker_bought_actual_max_price[ticker]['stepSize']
                tick_size = self.parameters.ticker_bought_actual_max_price[ticker]['tickSize']
                #Peut-être récupérer la quantité du portfolio à la place de calculer la quantité achetée
                quantity = self.trading_manager.portfolio.actifs[ticker]['quantity']
                quantity_step = quantity // step_size
                quantity_bought = str(round(quantity_step*step_size,8))
                self.z_score_hits = True
                print('SELLLLLLLL', now)
                scaled_price = 0.995 * close_price
                price_step = scaled_price // tick_size
                new_stop_loss_price = round(price_step*tick_size,8)
                print(new_stop_loss_price)
                self.trading_manager.cancel_replace(ticker, quantity_bought, new_stop_loss_price)

    def update_parameters(self, websocket_stream, k):
        ticker = k['s'][:-4]+'USDC'
        variation = float(k['h'])-float(k['l'])
        volume = float(k['v'])
        nb_of_trades = k['n']
        current_price = float(k['c'])
        row_idx = self.get_ticker_index(ticker)

        self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Variation", websocket_stream)]] = variation
        self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Volume", websocket_stream)]] = volume
        self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("NbOfTrades", websocket_stream)]] = nb_of_trades
        
        self.prices[ticker].append(current_price)
        if len(self.prices[ticker]) > max(self.parameters.mean_rolling_size, self.parameters.std_rolling_size):
            self.prices[ticker].pop(0)
        
        if websocket_stream == self.parameters.kline_type:
            price_is_going_up = bool(float(k['c']) > float(k['o']))
            self.data_storage[row_idx, PumpDump.COLUMN_MAPPING[("Price is going up", "")]] = price_is_going_up
