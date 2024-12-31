from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from src.utils import get_api_key

api_key, api_secret = get_api_key()

binance_api_client = SpotWebsocketAPIClient(api_key=api_key, 
                                            api_secret=api_secret)
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
    
    actual_max_price[ticker] = max(actual_max_price[ticker], actual_price)
    #Configurer ordre stop loss doit être beaucoup mieux/doit être fait dans la partie pump dès qu'on achète
    stop_loss_condition = 0.98*entry_price >= actual_price #0.98 et 0.99 en dessous
    
    take_gain_condition = 0.99*actual_max_price[ticker] >= actual_price #pareil pour un order de vente défini dynamiquement
    return stop_loss_condition or take_gain_condition
def add_order(order, order_type, symbol, quantity):
    binance_api_client.new_order_test(symbol=symbol,
                                      side=order,
                                      type=order_type,
                                      quantity=quantity,
                                      newClientOrderId="my_order_id_1",
                                      newOrderRespType="RESULT")