from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from src.utils import get_api_key
api_key, api_secret = get_api_key()

binance_api_client = SpotWebsocketAPIClient(api_key=api_key, 
                                            api_secret=api_secret)

def detect_pump(dataframe_storage, limits):
    variation_condition = (limits['variation']*dataframe_storage.loc[:,('Variation', '3m')] > 
    dataframe_storage.loc[:,('Variation', '2h')])

    volume_condition = (limits['volume']*dataframe_storage.loc[:,('Volume', '3m')] > 
    dataframe_storage.loc[:,('Volume', '2h')])
    price_is_going_up_condition = dataframe_storage.loc[: , ('Price is going up', '')]
    dataframe_storage.loc[:, ('Order', 'Buy')] = variation_condition & volume_condition & price_is_going_up_condition
    if any(dataframe_storage.loc[:, ('Order', 'Buy')].to_list()):
        return True
    return False

def detect_dump(ticker, portefeuille_test, actual_price):
    if not ticker in portefeuille_test.actifs:
        return False
    entry_price = portefeuille_test.actifs[ticker]['ticker_price']
    actual_max_price = actual_price
    actual_max_price = max(actual_max_price, actual_price)
    #Configurer ordre stop loss doit être beaucoup mieux/doit être fait dans la partie pump dès qu'on achète
    stop_loss_condition = 0.98*entry_price >= actual_price

    take_gain_condition = 0.99*actual_max_price >= actual_price #pareil pour un order de vente défini dynamiquement
    return stop_loss_condition or take_gain_condition
def add_order(order, order_type, symbol, quantity):
    binance_api_client.new_order_test(symbol=symbol,
                                      side=order,
                                      type=order_type,
                                      quantity=quantity,
                                      newClientOrderId="my_order_id_1",
                                      newOrderRespType="RESULT")