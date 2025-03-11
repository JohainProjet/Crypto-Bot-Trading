import time
from abc import ABC, abstractmethod
from bot.utils.helpers import Portfolio
from config import get_api_keys

class TradingManager(ABC):
    def __init__(self, is_test_mode : str, portfolio : Portfolio, duration_time):
        self.is_test_mode = is_test_mode
        self.api_key, self.api_secret = get_api_keys(environnement=is_test_mode)
        self.portfolio = portfolio
        self.duration_time = duration_time

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

    def periodic_sleep(self, total_duration, interval):
        elapsed_time = 0

        while elapsed_time < total_duration:
            time.sleep(interval)
            elapsed_time += interval

            remaining_time = total_duration - elapsed_time
            print(f"Temps écoulé : {elapsed_time} s. Temps restant : {remaining_time} secondes.")
            self.screenshot()

    def screenshot(self):
        print('-------------------')
        print('Transaction history :')
        print(self.portfolio.df_transaction_history)
        self.portfolio.evaluate_portfolio_value(verbose=True)
