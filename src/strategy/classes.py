from datetime import datetime
import pandas as pd


class Portfeuille:
    def __init__(self, cash : float, actifs : dict):
        self.cash = cash
        self.actifs = actifs
        self.df_transaction_history = pd.DataFrame(columns=['Time', 'Type', 'Ticker', 'Quantity', 'Price'])


    def transaction_order(self, transaction_type, transaction_time, ticker, quantity, price):

        if transaction_type == 'BUY':
            if not ticker in self.actifs:
                self.actifs[ticker] = {"quantity" : quantity,
                                    "price" : price}
            else:
                self.actifs[ticker][quantity]+=quantity
                self.actifs[ticker][price]+=price
            self.add_to_transaction_history(transaction_type, transaction_time, ticker, quantity, price) 
        elif transaction_type == 'SELL':
            if not ticker in self.actifs:
                print("problème l'actif n'est pas possédé")
            elif quantity <= self.actifs[ticker][quantity]:
                print('quantité trop petit à vendre')
            else:
                self.actifs[ticker][quantity]-=quantity
                self.add_to_transaction_history(transaction_type, transaction_time, ticker, quantity, price)
    def add_to_transaction_history(self, transaction_type, transaction_time, ticker, quantity, price):
        dict_ = {'Time' : transaction_time, 
                 'Type' : transaction_type,
                 'Ticker' : ticker,
                 'Quantity' : quantity,
                 'Price' : price}
        
        self.df_transaction_history = pd.concat([self.df_transaction_history, pd.DataFrame(dict_, index=[0])])
        print('inside portefeuille', self.df_transaction_history)