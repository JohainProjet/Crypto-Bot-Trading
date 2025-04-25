import datetime
import logging
import time
import json
from binance.lib.utils import config_logging
from bot.strategy.pump_dump import PumpDump
from bot.utils.helpers import Parameters, Portfolio, generate_parameters_combinaison, load_tickers_if_empty
from bot.trading.base_trading import SimulationSaver

config_logging(logging, logging.INFO)


DEFAULT_PROGRAM_MODE = 'PROD'
START_DATE = datetime.datetime(2025, 4, 19, 12, 30,0)
END_DATE = datetime.datetime(2025, 4, 19, 21, 10, 0)
TRADE_LOG_FILE = r"bot\results\TradesLogFile.txt"
KLINE_TYPE = '1m'
LIST_TICKERS = load_tickers_if_empty([])
DURATION_TIME = 15000
STD_ROLLING_SIZE = 100 #Used to clean position
MEAN_ROLLING_SIZE = 100 #Used to clean position

def main(simulation_saver : SimulationSaver, params : Parameters):

    portfolio = Portfolio(params.program_type, 500, {})

    logging.info("Lancement de la stratégie avec %s , stop-loss: %s",
                 params.limits,
                 params.stop_loss_prct)

    strategy = PumpDump(params, portfolio, simulation_saver)

    if params.program_type == 'BACKTEST':
        strategy.trading_manager.datas.set_strategy(strategy)
    else:
        strategy.trading_manager.websocket_manager.message_handler.set_strategy(strategy)
        strategy.trading_manager.get_open_orders_and_cancel()

    strategy.trading_manager.start()

    if params.program_type == 'BACKTEST':
        cash, assets_value = portfolio.evaluate_portfolio_value(END_DATE)
    elif params.program_type in ['PROD', 'TEST']:
        cash, assets_value = portfolio.evaluate_portfolio_value()
    performance = cash + assets_value
    return performance

def objective(trial):
    """Définit la fonction de coût pour Optuna."""
    # Optuna choisit dynamiquement les paramètres

    volumes = [1.5, 1.8, 2.1]
    variations = [1.5, 1.8, 2.1]
    nb_of_trades = [3, 4, 5]
    stop_loss_prices = [0.97, 0.98, 0.99]

    volume = trial.suggest_categorical("volume", volumes)
    variation = trial.suggest_categorical("variation", variations)
    nb_of_trades = trial.suggest_categorical("nbOfTrades", nb_of_trades)
    stop_loss_prct = trial.suggest_categorical("stop_loss_prct", stop_loss_prices)

    limits = {'volume': volume, 'variation': variation, 'nbOfTrades': nb_of_trades}

    parameters = Parameters(DURATION_TIME,
                            limits,
                            stop_loss_prct,
                            DEFAULT_PROGRAM_MODE,
                            KLINE_TYPE,
                            STD_ROLLING_SIZE,
                            MEAN_ROLLING_SIZE,
                            START_DATE,
                            END_DATE,
                            LIST_TICKERS)

    simulation_saver = SimulationSaver()
    return main(simulation_saver, parameters)


if __name__ == '__main__':
    """ study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=50)

    print("Meilleurs paramètres :", study.best_params)
    print("Meilleur score :", study.best_value)"
    """

    volume = 2.1
    variation = 1.8
    nb_of_trades = 4
    stop_loss_prct = 0.97

    limits = {'volume': volume, 'variation': variation, 'nbOfTrades': nb_of_trades}

    parameters = Parameters(DURATION_TIME,
                            limits,
                            stop_loss_prct,
                            DEFAULT_PROGRAM_MODE,
                            KLINE_TYPE,
                            STD_ROLLING_SIZE,
                            MEAN_ROLLING_SIZE,
                            START_DATE,
                            END_DATE,
                            LIST_TICKERS)
    simulation_saver = SimulationSaver()
    main(simulation_saver, parameters)




""" 2025-04-19 19:48:51.970 UTC DEBUG root: Code : -1013
2025-04-19 19:48:51.996 UTC DEBUG root: Message : Market is closed.
2025-04-19 19:48:51.996 UTC DEBUG root: data_error : None """