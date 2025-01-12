import json
from src.strategy.strat2.shared import global_dictionnary, dataframe_storage, crypto_bought, limits, portefeuille_test, ticker_bought_actual_max_price
from src.strategy.strat2.utils import detect_pump, define_stop_losses, binance_api_client
import datetime
import time
import threading
import logging

def messageUserData(_, source):
    message : dict = json.loads(source)
    if message.get('e', None) == 'outboundAccountPosition':
        print(message)
    else:
        if message.get('x', None) == 'NEW':
            print("NOUVEL ORDRE ENVOYE")
            print(f'Ticker {message['s']} | Stop_loss : {message['P']}')
            print('---------------')
        elif message.get('x', None) == 'TRADE' and message['S'] == 'SELL':
            print('VENTE REALISEE')
            print(f'Ticker : {message['s']} | USDT en plus : {message['Z']} | Au prix : {message['L']}')
            print('---------------')

            executedQty = float(message['l'])
            workingTimeOrder = datetime.datetime.fromtimestamp(int(message['T'])/1000)
            excuted_price = float(message['L'])
            ticker = message['s']

            portefeuille_test.transaction_order('SELL', 
                                                workingTimeOrder, 
                                                ticker,
                                                executedQty, 
                                                excuted_price)
            del ticker_bought_actual_max_price[message['s']]
        elif message.get('x', None) == 'TRADE' and message['S'] == 'BUY':
            logging.debug('ACHAT REALISE')
            print(f"Ticker : {message['s']} | Prix d'achat : {message['L']}")
            side = message['S']
            workingTimeOrder = datetime.datetime.fromtimestamp(int(message['T'])/1000)
            ticker = message['s']
            executedQty = float(message['l'])
            excuted_price = float(message['L'])
            portefeuille_test.transaction_order(side, 
                                                workingTimeOrder, 
                                                ticker,
                                                executedQty, 
                                                excuted_price)
            if side == 'BUY':
                threading.Thread(target=define_stop_losses, args = (ticker, excuted_price)).start()
        print()

def messageProcessingkline3m(_, source=None, test_data=None):
    global ticker_bought_actual_max_price
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
    close_price = float(data['c'])
    open_price = float(data['o'])
    price_is_going_up = bool(close_price > open_price)
    global_dictionnary['variation3m'] = variation_3m
    global_dictionnary['volume3m'] = volume_3m
    dataframe_storage.loc[ticker, ('Variation', '3m')] = variation_3m
    dataframe_storage.loc[ticker, ('Volume', '3m')] = volume_3m
    dataframe_storage.loc[ticker, ('Price is going up', '')] = price_is_going_up

    if detect_pump(dataframe_storage, ticker, limits, crypto_bought):
        cash_used = '30'
        if datetime.datetime.now().minute % 15 == 0:
            cash_used = '30'
        crypto_bought.append(ticker)

        binance_api_client.new_order(symbol=ticker,
                                          side="BUY",
                                          type="MARKET",
                                          quoteOrderQty=cash_used,
                                          newClientOrderId=f'buy_market_{ticker}',
                                          newOrderRespType="FULL")
        time.sleep(2)
        #print(f'TICKER : {ticker}')
        #print(f"Variation 3m : {dataframe_storage.loc[ticker, ('Variation', '3m')]} | Volume 3m : {dataframe_storage.loc[ticker, ('Volume', '3m')]}")
        #print(f"Variation 2h : {dataframe_storage.loc[ticker, ('Variation', '2h')]} | Volume 2h : {dataframe_storage.loc[ticker, ('Volume', '2h')]}")

        #A finir : 
        # Gérer la gestion des stepsize pour les ordres qui sont passés. Y'a aussi ça a faire pour le stopprice
        # Changer la méthode transaction_order de place pour la mettre clairement dans le messageProcessing de new_order_test
        # Tester sans order_test mais avec un vrai order en étant sur le test net (donc faut vérifier qu'il y ait de la thune sur le compte lié au testnet)
        # Faire attention ce que la thune ne soit pas sur le compte spot de binance sinon ça va acheter avec en cas de bug (si on était pas sur le testnet)
        # En fait pourquoi j'ai besoin de tester avec des vrais transactions-> c'est pour voir le message FULL reponse du websocket et récupérer des données
        #comme le prix auquel s'est passé le trade ou par exemple la quantité, données qui sont utiles pour les rajouter dans transaction_order mais également
        # pour définir les ordres stoploss

    if ticker in ticker_bought_actual_max_price:
        print(ticker, close_price, ticker_bought_actual_max_price[ticker]['entry_price'])
        if close_price > ticker_bought_actual_max_price[ticker]['entry_price']:
            
            ticker_bought_actual_max_price[ticker]['entry_price'] = close_price
            stepSize = ticker_bought_actual_max_price[ticker]['stepSize']
            tickSize = ticker_bought_actual_max_price[ticker]['tickSize']

            quantity_bought = str(round((portefeuille_test.actifs[ticker]['quantity']//stepSize)*stepSize,8))
            newStopLossPrice = round((0.996*close_price//tickSize)*tickSize,8)

            binance_api_client.cancel_replace_order(ticker,
                                                    side='SELL',
                                                    cancelReplaceMode="ALLOW_FAILURE",
                                                    cancelOrigClientOrderId = f'stop_loss_{ticker}',
                                                    newClientOrderId=f"stop_loss_{ticker}",
                                                    type="STOP_LOSS",
                                                    quantity=quantity_bought,
                                                    stopPrice=newStopLossPrice,
                                                    newOrderRespType="FULL")

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