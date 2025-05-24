import datetime
import logging
import optuna
import pytz
from binance.lib.utils import config_logging
from bot.strategy.pump_dump import PumpDump
from bot.utils.helpers import Parameters, Portfolio, generate_parameters_combinaison, load_tickers
from bot.trading.base_trading import SimulationSaver

config_logging(logging, logging.INFO)

DEFAULT_PROGRAM_MODE = 'BACKTEST'
START_DATE = datetime.datetime(2025, 4, 1, 0, 0,0, tzinfo=pytz.utc)
END_DATE = datetime.datetime(2025, 4, 1, 23, 59, 0, tzinfo=pytz.utc)

LIST_TICKERS = load_tickers()
DURATION_TIME = 43200
STD_ROLLING_SIZE = 100
MEAN_ROLLING_SIZE = 100

GLOBAL_PARAMETERS = {'DEFAULT_PROGRAM_MODE' : DEFAULT_PROGRAM_MODE,
                     'START_DATE' : START_DATE,
                     'END_DATE' : END_DATE,
                     'LIST_TICKERS' : LIST_TICKERS,
                     'DURATION_TIME' : DURATION_TIME,
                     'STD_ROLLING_SIZE' : STD_ROLLING_SIZE,
                     'MEAN_ROLLING_SIZE' : MEAN_ROLLING_SIZE
                     }

def main(parameters : Parameters, simulation_saver : SimulationSaver)->float:

    portfolio = Portfolio(DEFAULT_PROGRAM_MODE, 500, {})

    logging.info("Lancement de la stratégie avec les paramètres suivants : %s", parameters.SPECIFIC_PARAMETERS)

    strategy = PumpDump(parameters, portfolio, simulation_saver)

    if DEFAULT_PROGRAM_MODE == 'BACKTEST':
        strategy.trading_manager.datas.set_strategy(strategy)
    elif DEFAULT_PROGRAM_MODE in ['PROD', 'TEST']:
        strategy.trading_manager.websocket_manager.message_handler.set_strategy(strategy)
        strategy.trading_manager.get_open_orders_and_cancel()
    
    strategy.trading_manager.start()
    cash, assets_value = portfolio.evaluate_portfolio_value()
    portfolio_value = cash + assets_value
    return portfolio_value

def objective(trial)-> float:
    """
    Used to optimize non global parameters

    Args:
        trial object from optuna library

    Returns:
        float: Value of the portfolio at the end of the simulation.
    """
    first_check_volume = trial.suggest_float('volume', 1, 5)
    first_check_variation = trial.suggest_float('variation', 1, 5)
    first_check_nb_of_trades = trial.suggest_float('nb_of_trades', 1, 5)

    second_check_volume = trial.suggest_float('volume2', 0.01, 0.2)
    second_check_nb_of_trades = trial.suggest_float('nb_of_trades2', 0.01, 0.2)

    stop_loss_prct = trial.suggest_float("stop_loss", 0.99, 0.995)
    #stop_loss_adjust_stop_loss = trial.suggest_float("stop_loss_adjust", 0.97, 0.998)
    stop_loss_prct = 0.99
    stop_loss_adjust_stop_loss = 0.995
    SPECIFIC_PARAMETERS = {'first_check_volume': first_check_volume, 
            'first_check_variation': first_check_variation, 
            'first_check_nb_of_trades': first_check_nb_of_trades,
            'second_check_volume' : second_check_volume,
            'second_check_nb_of_trades' : second_check_nb_of_trades,
            'stop_loss_prct' : stop_loss_prct,
            'stop_loss_adjust_stop_loss' : stop_loss_adjust_stop_loss}

    parameters = Parameters(GLOBAL_PARAMETERS,
                            SPECIFIC_PARAMETERS)

    simulation_saver = SimulationSaver()
    return main(parameters, simulation_saver)

if __name__ == '__main__':
    # Try to find the best parameters to maximize returns on portfolio for the last month
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=100)

    print("Best trial:")
    trial = study.best_trial
    print(f"  Value: {trial.value}") #Value of the best simulation
    print(f"  Params: {trial.params}") #Parameters values