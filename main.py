import datetime
import logging
import time
import json
from bot.strategy.pump_dump import PumpDump
from bot.utils.helpers import Parameters, Portfolio, generate_parameters_combinaison
from binance.lib.utils import config_logging

config_logging(logging, logging.INFO)


def main(parameters_local):
    startDate = datetime.datetime(2025, 2, 22, 0, 0,0)
    endDate = datetime.datetime(2025, 2, 23, 0, 0, 0)
    PROGRAM_MODE = 'PROD' #TEST/BACKTEST/PROD
    limits = parameters_local[0]
    stop_loss_price = parameters_local[1]
    t1 = time.time()
    if PROGRAM_MODE == 'BACKTEST':
        with open("trades.txt", "a") as f:
            json.dump(limits, f)
            f.write('\t')
            f.write(str(stop_loss_price))
            f.write("\n")
    parameters = Parameters(limits, stop_loss_price, PROGRAM_MODE, startDate, endDate)

    portfolio = Portfolio(500, parameters, {})
    print(f"{limits}, {stop_loss_price}")
    strategy = PumpDump(parameters=parameters,
                        portfolio=portfolio,
                        durationTime=15000,
                        isTestMode=PROGRAM_MODE,
                        startDate=startDate,
                        endDate=endDate)
    if PROGRAM_MODE == 'BACKTEST': #A ne pas changer
        strategy.tradingManager.datas.set_strategy(strategy)
    else:
        strategy.tradingManager.websocketManager.message_handler.set_strategy(strategy)
        strategy.tradingManager.get_open_orders_and_cancel()

    strategy.tradingManager.start()
    if PROGRAM_MODE == 'BACKTEST':
        with open("trades.txt", "a") as f:
            f.write(f'Durée {time.time()- t1}.\n')
            f.write("------------------------------------------------------------------\n")
            f.write("\n")

if __name__ == '__main__':
    #Define parameters
    """ limits = {'volume' : 5,#2
              'variation' : 5,#2.3
              'nbOfTrades' : 5}#6 trop haut # 4 encore trop haut même si mieux ? #3
    stop_loss_price = 0.995 #0.985 """
    list_parameters = generate_parameters_combinaison()
    limits = {'volume' : 2.5,
        'variation' : 2.5,
        'nbOfTrades' : 3}
    list_parameters = [(limits, 0.96)]
    for parameters_local in list_parameters:
        main(parameters_local)