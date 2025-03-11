import datetime
import logging
import time
import json
from binance.lib.utils import config_logging
from bot.strategy.pump_dump import PumpDump
from bot.utils.helpers import Parameters, Portfolio, generate_parameters_combinaison

config_logging(logging, logging.INFO)


DEFAULT_PROGRAM_MODE = 'TEST'
START_DATE = datetime.datetime(2025, 3, 6, 10, 0,0)
END_DATE = datetime.datetime(2025, 3, 6, 21, 10, 0)
TRADE_LOG_FILE = r"bot\results\TradesLogFile.txt"

def main(parameters_local):
    limits = parameters_local[0]
    stop_loss_price = parameters_local[1]
    t1 = time.time()
    if DEFAULT_PROGRAM_MODE == 'BACKTEST':
        with open(TRADE_LOG_FILE, "a", encoding='utf-8') as f:
            json.dump(limits, f)
            f.write('\t')
            f.write(str(stop_loss_price))
            f.write("\n")
    parameters = Parameters(limits, stop_loss_price, DEFAULT_PROGRAM_MODE, START_DATE, END_DATE)
    portfolio = Portfolio(500, parameters, {})

    logging.info("Lancement de la stratégie avec %s , stop-loss: %s",
                 limits,
                 stop_loss_price)

    strategy = PumpDump(parameters=parameters,
                        portfolio=portfolio,
                        duration_time=15000,
                        is_test_mode=DEFAULT_PROGRAM_MODE,
                        start_date=START_DATE,
                        end_date=END_DATE)

    if DEFAULT_PROGRAM_MODE == 'BACKTEST':
        strategy.trading_manager.datas.set_strategy(strategy)
    else:
        strategy.trading_manager.websocket_manager.message_handler.set_strategy(strategy)
        strategy.trading_manager.get_open_orders_and_cancel()

    strategy.trading_manager.start()
    if DEFAULT_PROGRAM_MODE == 'BACKTEST':
        with open(TRADE_LOG_FILE, "a", encoding='utf-8') as f:
            f.write(f'Durée {time.time()- t1}.\n')
            f.write("------------------------------------------------------------------\n")
            f.write("\n")

if __name__ == '__main__':
    list_parameters = generate_parameters_combinaison()
    for param in list_parameters:
        main(param)
