import datetime
from bot.strategy.pump_dump import PumpDump, MessageHandler, BackTesting, WebsocketManager
from bot.utils.helpers import Parameters, Portfolio


if __name__ == '__main__':
    #Define parameters
    limits = {'volume' : 15,#2
              'variation' : 15,#2.3
              'nbOfTrades' : 20}#6 trop haut # 4 encore trop haut même si mieux ? #3
    stop_loss_price = 0.998 #0.985

    portfolio = Portfolio(500)

    parameters = Parameters(limits, stop_loss_price)

    #BACKTESTING

    startDate = datetime.datetime(2025, 2, 10)
    endDate = datetime.datetime(2025, 2, 13)

    strategy = PumpDump(parameters=parameters, 
                        portfolio=portfolio, 
                        durationTime=4000, 
                        isTestMode='BACKTEST', 
                        startDate=startDate,
                        endDate=endDate)

    strategy.tradingManager.datas.set_strategy(strategy)

    #strategy.tradingManager.get_open_orders_and_cancel()
    strategy.tradingManager.start()

    #On commence par créer strategy puis appeler dessus la static method list_tickets pour les avoir et les passer dans livetrading

    