from bot.strategy.pump_dump import PumpDump, MessageHandler
from bot.utils.helpers import Parameters
from bot.utils.helpers import Portfolio
from bot.strategy.pump_dump import WebsocketManager
if __name__ == '__main__':
    #Define parameters
    limits = {'volume' : 2,#2
              'variation' : 2.3,
              'nbOfTrades' : 3}#6 trop haut # 4 encore trop haut même si mieux ?
    stop_loss_price = 0.99 #0.985
    portfolio = Portfolio(500)
    parameters = Parameters(limits, stop_loss_price)

    strategy = PumpDump(parameters=parameters, portfolio=portfolio, durationTime=38000, isTestMode=True)

    strategy.websocketManager.message_handler.set_pump_and_dump(strategy)

    strategy.get_open_orders_and_cancel()
    strategy.start()