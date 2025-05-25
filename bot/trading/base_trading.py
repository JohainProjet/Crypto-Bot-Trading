import time
import sqlite3
import json
import datetime
from abc import ABC, abstractmethod
from bot.utils.helpers import Portfolio, Parameters
from config import get_api_keys


class SimulationSaver:
    def save_to_db(self, portfolio: Portfolio, parameters: Parameters):
        conn = sqlite3.connect(r'bot/results/results.db')
        cursor = conn.cursor()
        # portfolio_perf = (portfolio.portfolio_values[-1]/portfolio.cash_at_start - 1)*100
        if parameters.program_type in ['PROD', 'TEST']:
            start_date = portfolio.creation_date
            end_date = datetime.datetime.now()
        elif parameters.program_type == 'BACKTEST':
            start_date = parameters.start_date
            end_date = parameters.end_date
        cash, assets_value = portfolio.initial_cash, 0
        simulation_type = parameters.program_type
        portfolio_values = json.dumps([cash])
        volume, variation, nb_of_trades = parameters.limits.values()
        stop_loss = parameters.stop_loss_prct
        cursor.execute('''
                       INSERT
                       OR IGNORE INTO Results (
				simulation_type,
				start_date,
				end_date,
				portfolio_values,
				cash,
				assets_value,
				volume,
				variation,
				nb_of_trades,
				stop_loss,
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ''', (
                           simulation_type,
                           start_date,
                           end_date,
                           portfolio_values,
                           cash,
                           assets_value,
                           volume,
                           variation,
                           nb_of_trades,
                           stop_loss,
                       ))
        conn.commit()

    def update_portfolio_in_db(self, portfolio: Portfolio, parameters: Parameters, timestamp=None):
        conn = sqlite3.connect(r'bot/results/results.db')
        cursor = conn.cursor()

        cash, asset_value = portfolio.evaluate_portfolio_value(timestamp, verbose=False)
        portfolio_value = cash + asset_value
        volume, variation, nb_of_trades = parameters.limits.values()
        stop_loss = parameters.stop_loss_prct

        cursor.execute('''
                       SELECT Portfolio_values
                       FROM Results
                       WHERE simulation_type = ?
                         AND start_date = ?
                         AND end_date = ?
                         AND volume = ?
                         AND variation = ?
                         AND nb_of_trades = ?
                         AND stop_loss = ?
                       ''', (
                           parameters.program_type,
                           parameters.start_date,
                           parameters.end_date,
                           volume,
                           variation,
                           nb_of_trades,
                           stop_loss
                       ))
        row = cursor.fetchone()

        portfolio_values = list(json.loads(row[0]))
        portfolio_values.append(portfolio_value)
        portfolio_values = json.dumps(portfolio_values)

        cursor.execute('''
                       UPDATE Results
                       SET Portfolio_values = ?
                       WHERE simulation_type = ?
                         AND start_date = ?
                         AND end_date = ?
                         AND volume = ?
                         AND variation = ?
                         AND nb_of_trades = ?
                         AND stop_loss = ?
                       ''', (
                           portfolio_values,
                           parameters.program_type,
                           parameters.start_date,
                           parameters.end_date,
                           volume,
                           variation,
                           nb_of_trades,
                           stop_loss
                       ))

        conn.commit()
        conn.close()


class TradingManager(ABC):
    def __init__(self, parameters: Parameters, portfolio: Portfolio, simulation_saver: SimulationSaver):
        program_type = parameters.GLOBAL_PARAMETERS['DEFAULT_PROGRAM_MODE']
        self.api_key, self.api_secret = get_api_keys(environnement=program_type)
        self.portfolio = portfolio
        self.parameters = parameters
        # if program_type == 'BACKTEST':
        #	simulation_saver.save_to_db(self.portfolio, self.parameters)
        self.simulation_saver = simulation_saver

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def place_stop_loss(self, ticker, quantity_bought, stop_loss_price):
        pass

    @abstractmethod
    def buy(self, ticker, cash_used, excecuted_price=0, time_=0):
        pass

    @abstractmethod
    def cancel_replace(self, ticker, quantity_bought, new_stop_loss_price):
        pass

    def periodic_sleep(self, total_duration, interval, timestamp=None):
        elapsed_time = 0

        while elapsed_time < total_duration:
            time.sleep(interval)
            elapsed_time += interval
            remaining_time = total_duration - elapsed_time
            print(f"Temps écoulé : {elapsed_time} s. Temps restant : {remaining_time} secondes.")

    # self.screenshot(timestamp)

    def screenshot(self, timestamp=None):
        print('-------------------')
        print('Transaction history :')
        print(self.portfolio.df_transaction_history)
# if self.parameters.program_type == 'BACKTEST':
#	self.simulation_saver.update_portfolio_in_db(self.portfolio, self.parameters, timestamp)
