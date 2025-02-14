import datetime
import logging
from bot.strategy.pump_dump import PumpDump
from bot.utils.helpers import Parameters, Portfolio
from binance.lib.utils import config_logging


config_logging(logging, logging.INFO)

if __name__ == '__main__':
    #Define parameters
    limits = {'volume' : 3,#2
              'variation' : 3,#2.3
              'nbOfTrades' : 4}#6 trop haut # 4 encore trop haut même si mieux ? #3
    stop_loss_price = 0.998 #0.985

    portfolio = Portfolio(500)

    parameters = Parameters(limits, stop_loss_price)

    #BACKTESTING
    PROGRAM_MODE = 'BACKTEST' #TEST/BACKTEST/PROD
    startDate = datetime.datetime(2025, 2, 14, 19, 10)
    endDate = datetime.datetime(2025, 2, 14, 20, 2)
    #TEST
    # startDate = datetime.datetime(2025, 2, 14, 19, 10)
    # endDate = datetime.datetime(2025, 2, 14, 20, 2)
    """ 
    0 2025-02-14 19:29:53.695   BUY  FORTHUSDT       2.6       3.83500      -9.98
    1 2025-02-14 19:38:39.804   BUY    PHAUSDT      56.0       0.17830      -9.99
    2 2025-02-14 19:47:35.889   BUY   WAXPUSDT     300.0       0.03333     -10.01
    3 2025-02-14 19:58:12.168  SELL   WAXPUSDT     300.0       0.03322       9.96
    4 2025-02-14 19:59:59.861   BUY    RAYUSDT       1.7       5.59000      -9.51 
    """
    #BACKTESTING
    # startDate = datetime.datetime(2025, 2, 14, 19, 10)
    # endDate = datetime.datetime(2025, 2, 14, 20, 2)
    #Je pense que déjà le problème des sell vient du fait que la quantité dans le protefeuillle n'est pas 0 donc y'a toujours le ticker peut-être
    #En tout cas on voit bien qu'il essaye de vendre une quantité de 0
    #Par contre ça répond toujours pas au  problème du fait que des fois ça vend alors que pas dans le test et pas à la même heure
    #260ms de décalage pour les achats on dirait
    """ 
    0  2025-02-14 19:29:53.435   BUY  FORTHUSDT    2.601457       3.84400     -10.01
    1  2025-02-14 19:38:39.547   BUY    PHAUSDT   54.644809       0.18300     -10.01
    2  2025-02-14 19:38:49.543  SELL    PHAUSDT   54.000000       0.18450       9.95
    3  2025-02-14 19:38:59.544  SELL    PHAUSDT    0.000000       0.18460       0.00
    4  2025-02-14 19:39:07.426  SELL  FORTHUSDT    2.600000       3.84400       9.98
    5  2025-02-14 19:39:09.547  SELL    PHAUSDT    0.000000       0.18560       0.00
    6  2025-02-14 19:39:25.542  SELL    PHAUSDT    0.000000       0.18720       0.00
    7  2025-02-14 19:39:43.543  SELL    PHAUSDT    0.000000       0.19210       0.00
    8  2025-02-14 19:45:37.543  SELL    PHAUSDT    0.000000       0.19960       0.00
    9  2025-02-14 19:46:19.546  SELL    PHAUSDT    0.000000       0.20010       0.00
    10 2025-02-14 19:46:29.557  SELL    PHAUSDT    0.000000       0.20050       0.00
    11 2025-02-14 19:46:43.556  SELL    PHAUSDT    0.000000       0.20360       0.00
    12 2025-02-14 19:47:35.618   BUY   WAXPUSDT  300.120048       0.03332     -10.01
    13 2025-02-14 19:47:47.550  SELL    PHAUSDT    0.000000       0.20410       0.00
    14 2025-02-14 19:51:11.545  SELL    PHAUSDT    0.000000       0.20430       0.00
    15 2025-02-14 19:53:19.624  SELL   WAXPUSDT  300.000000       0.03328       9.97
    16 2025-02-14 19:59:59.595   BUY    RAYUSDT    1.640151       6.09700     -10.01
    17 2025-02-14 20:00:01.593  SELL    RAYUSDT    1.600000       6.06800       9.70 """
    #BACKTEST
   
    strategy = PumpDump(parameters=parameters, 
                        portfolio=portfolio, 
                        durationTime=4000, 
                        isTestMode=PROGRAM_MODE, 
                        startDate=startDate,
                        endDate=endDate)
    if PROGRAM_MODE == 'BACKTEST': #A ne pas changer
        strategy.tradingManager.datas.set_strategy(strategy)
    else:
        strategy.tradingManager.websocketManager.message_handler.set_strategy(strategy)
        strategy.tradingManager.get_open_orders_and_cancel()

    strategy.tradingManager.start()

    #On commence par créer strategy puis appeler dessus la static method list_tickets pour les avoir et les passer dans livetrading

    

    #Amélioration : faire une classe mère abstraite Datas avec comme classes filles MessageHandler et la classe Data actuelle qui sert au BT.