from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from src.utils import get_api_key
from src.strategy.strat2.shared import client, portefeuille_test
import json
import logging
import pprint
import datetime

api_key, api_secret = get_api_key()

def message_handler(_, source):
    message : dict = json.loads(source)
    result = message["result"]
    if result['status'] == 'FILLED':
        clientOrderId = result['clientOrderId']
        executedBaseQty = float(result['cummulativeQuoteQty'])
        executedQty = float(result['executedQty'])
        workingTimeOrder = int(result['workingTime'])/1000
        side = result['side']
        fills = result['fills'][0]
        excuted_price = float(fills['price'])
        ticker = result['symbol']
        commission = float(fills['commission'])
        commissionAsset = fills['commissionAsset']

        portefeuille_test.transaction_order(side, 
                                            workingTimeOrder, 
                                            ticker,
                                            executedBaseQty, 
                                            excuted_price)
    elif result['status'] != 'FILLED':
        pprint.pprint(message)
        pprint.pprint(result['status'])
        raise ValueError
    pass

binance_api_client = SpotWebsocketAPIClient(stream_url="wss://ws-api.testnet.binance.vision/ws-api/v3",
                                            api_key=api_key, 
                                            api_secret=api_secret,
                                            on_message=message_handler)
actual_max_price = {}

def detect_pump(dataframe_storage, ticker, limits, crypto_bought):
    if ticker in crypto_bought:
        return False
    variation_condition = (limits['variation']*dataframe_storage.loc[ticker,('Variation', '3m')] > 
                            dataframe_storage.loc[ticker,('Variation', '2h')])

    volume_condition = (limits['volume']*dataframe_storage.loc[ticker,('Volume', '3m')] > 
                        dataframe_storage.loc[ticker,('Volume', '2h')])
    
    price_is_going_up_condition = dataframe_storage.loc[ticker, ('Price is going up', '')]

    return variation_condition and volume_condition and price_is_going_up_condition

def detect_dump(ticker, portefeuille_test, actual_price):
    global actual_max_price
    if not ticker in portefeuille_test.actifs:
        return False

    entry_price = portefeuille_test.actifs[ticker]['ticker_price']

    if ticker not in actual_max_price:
        actual_max_price[ticker] = entry_price
    
    stepSize, tickSize = getTickerTickSize(ticker)
    
    actual_max_price[ticker] = max(actual_max_price[ticker], actual_price)
    #Configurer ordre stop loss doit être beaucoup mieux/doit être fait dans la partie pump dès qu'on achète
    stop_loss_condition = 0.98*entry_price >= actual_price #0.98 et 0.99 en dessous
    stopLossPrice = round((0.995*entry_price//tickSize)*tickSize,8)
    take_gain_condition = 0.99*actual_max_price[ticker] >= actual_price #pareil pour un order de vente défini dynamiquement
    take_gain_stop_loss = round((0.998*actual_max_price[ticker]//tickSize)*tickSize,8)
    quantity_bought = str(round((portefeuille_test.actifs[ticker]['quantity']//stepSize)*stepSize,8))
    

    binance_api_client.new_order(symbol=ticker,
                                        side="SELL", 
                                        type="STOP_LOSS",
                                        quantity=quantity_bought,
                                        stopPrice=stopLossPrice,
                                        newClientOrderId=f'stop_loss_{ticker}',
                                        newOrderRespType="FULL")

    binance_api_client.new_order(symbol=ticker,
                                        side="SELL", 
                                        type="STOP_LOSS", 
                                        quantity=quantity_bought,
                                        stopPrice=take_gain_stop_loss,
                                        newClientOrderId=f'take_gain_stop_loss_{ticker}',
                                        newOrderRespType="FULL")

    return stop_loss_condition or take_gain_condition


def getTickerTickSize(symbol):
    resp = client.get_exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return float(elem['filters'][1]['stepSize']), float(elem['filters'][0]['tickSize'])