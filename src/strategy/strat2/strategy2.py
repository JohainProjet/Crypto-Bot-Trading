import json
from src.strategy.strat2.shared import global_dictionnary, dataframe_storage, crypto_bought, limits, portefeuille_test
from src.strategy.strat2.utils import detect_pump, detect_dump, binance_api_client, getTickerTickSize
import datetime


def messageProcessingkline3m(_, source=None, test_data=None):

    if test_data:
        message = test_data
    else:
        message : dict = json.loads(source)
    if message.get('result',0) == None:
        print(f'Connection open at {datetime.datetime.now()} with websocket kline 3minutes.')
        return
    
    data = message['data']['k']
    ticker = data['s']
    variation_3m = float(data['h'])-float(data['l'])
    volume_3m = float(data['v'])
    closed_price = float(data['c'])
    open_price = float(data['o'])
    price_is_going_up = bool(closed_price > open_price)
    global_dictionnary['variation3m'] = variation_3m
    global_dictionnary['volume3m'] = volume_3m
    dataframe_storage.loc[ticker, ('Variation', '3m')] = variation_3m
    dataframe_storage.loc[ticker, ('Volume', '3m')] = volume_3m
    dataframe_storage.loc[ticker, ('Price is going up', '')] = price_is_going_up

    if detect_pump(dataframe_storage, ticker, limits, crypto_bought):
        cash_used = '5'
        if datetime.datetime.now().minute % 15 == 0:
            cash_used = '50'
        crypto_bought.append(ticker)


        binance_api_client.new_order(symbol=ticker,
                                          side="BUY",
                                          type="MARKET", 
                                          quoteOrderQty=cash_used,
                                          newClientOrderId=f'buy_market_{ticker}',
                                          newOrderRespType="FULL")
        ticker_price = float(message['data']['k']['c']) #A obtenir par le binance api messagehandler

        print(f'TICKER : {ticker}')
        print(f"Variation 3m : {dataframe_storage.loc[ticker, ('Variation', '3m')]} | Volume 3m : {dataframe_storage.loc[ticker, ('Volume', '3m')]}")
        print(f"Variation 2h : {dataframe_storage.loc[ticker, ('Variation', '2h')]} | Volume 2h : {dataframe_storage.loc[ticker, ('Volume', '2h')]}")

        #Cette ligne est à bouger dans le messageProcessing qui gère les ordres à envoyer (sûr à 100%), faudra récupérer les caractéristiques
        #ticker, cash_used/ticker_price, ticker_price

        #A finir : 
        # Gérer la gestion des stepsize pour les ordres qui sont passés. Y'a aussi ça a faire pour le stopprice
        # Changer la méthode transaction_order de place pour la mettre clairement dans le messageProcessing de new_order_test
        # Tester sans order_test mais avec un vrai order en étant sur le test net (donc faut vérifier qu'il y ait de la thune sur le compte lié au testnet)
        # Faire attention ce que la thune ne soit pas sur le compte spot de binance sinon ça va acheter avec en cas de bug (si on était pas sur le testnet)
        # En fait pourquoi j'ai besoin de tester avec des vrais transactions-> c'est pour voir le message FULL reponse du websocket et récupérer des données
        #comme le prix auquel s'est passé le trade ou par exemple la quantité, données qui sont utiles pour les rajouter dans transaction_order mais également
        # pour définir les ordres stoploss

    if detect_dump(ticker, portefeuille_test, closed_price):

        quantity_bought = portefeuille_test.actifs[ticker]['quantity']
        binance_api_client.new_order(symbol=ticker,
                                          side="SELL", 
                                          type="MARKET", 
                                          quantity=quantity_bought,
                                          newClientOrderId=f'sell_market_{ticker}',
                                          newOrderRespType="FULL")
        #crypto_bought.remove(ticker)
        portefeuille_test.transaction_order("SELL", datetime.datetime.fromtimestamp(message['data']['E']/1000), ticker, quantity_bought, closed_price)
    else:
        pass

def messageProcessingRolling1h(_, source):
    global global_dictionnary

    message : dict = json.loads(source)
    if message.get('result',0) == None:
        print(f'Connection open at {datetime.datetime.now()} with websocket rolling windows 1hour.')
        return

    data = message['data']
    ticker = data['s']
    variation_2h = float(data['h'])-float(data['l'])
    volume_2h = float(data['v'])
    global_dictionnary['variation2h'] = variation_2h
    global_dictionnary['volume2h'] = volume_2h
    dataframe_storage.loc[ticker, ('Variation', '2h')] = variation_2h
    dataframe_storage.loc[ticker, ('Volume', '2h')] = volume_2h
