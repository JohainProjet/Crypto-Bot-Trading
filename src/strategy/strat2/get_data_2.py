import json
from binance.lib.utils import config_logging
import pprint

global_dictionnary : dict = {'variation2h' : 0,
                      'volume2h' : 0,
                      'variation3m' : 0,
                      'volume3m' : 0} 
limits = {'volume' : 12, 'variation' : 3}
price_is_going_up : bool = False
def message_handler2(_, source):
    global global_dictionnary
    global price_is_going_up
    message : dict = json.loads(source)

    if message['stream'] == 'troyusdt@kline_2h':
        data :dict = message['data']['k']
        variation_2h = float(data['h'])-float(data['l'])
        volume_2h = float(data['v'])
        global_dictionnary['variation2h'] = variation_2h
        global_dictionnary['volume2h'] = volume_2h
    elif message['stream'] == 'troyusdt@kline_3m':
        data :dict = message['data']['k']
        variation_3m = float(data['h'])-float(data['l'])
        volume_3m = float(data['v'])
        closed_price = message['data']['k']['c']
        open_price = message['data']['k']['o']
        price_is_going_up = bool(closed_price > open_price)
        print(float(closed_price) - float(open_price))
        global_dictionnary['variation3m'] = variation_3m
        global_dictionnary['volume3m'] = volume_3m
    #print(price_is_going_up)

    if detect_pump(global_dictionnary, limits) and price_is_going_up:
        print("buy at price ...")
    else:
        print('nothing')

def detect_pump(dictionnary, limits):
    print('volume en 2h : ', dictionnary['volume2h'])
    print('limits * volume en 3m : ', limits['volume']*dictionnary['volume3m'])
    print('limits * variation3m :' , limits['variation']*dictionnary['variation3m'])
    print('variation2h : ', dictionnary['variation2h'])
    if dictionnary['volume2h'] < limits['volume']*dictionnary['volume3m']:
        print('volume verified')
        if limits['variation']*dictionnary['variation3m'] > dictionnary['variation2h']:
            print('variation verified')
            return True
    return False