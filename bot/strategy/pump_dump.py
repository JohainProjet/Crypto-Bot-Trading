import datetime
import numpy as np
from collections import defaultdict
from bot.utils.helpers import Portfolio, Parameters, TRADING_PAIRS
from bot.strategy.base_strategy import Strategy
from bot.trading.base_trading import SimulationSaver
from bot.trading.backtesting import BackTesting
from bot.trading.live_trading import LiveTrading


class PumpDump(Strategy):
	trading_pairs = TRADING_PAIRS
	"""Strategy to detect pump and dump on crypto market."""
	def __init__(self, parameters : Parameters, portfolio : Portfolio, simulation_saver : SimulationSaver):
		duration_time = parameters.GLOBAL_PARAMETERS['DURATION_TIME']
		super().__init__(duration_time)
		program_mode = parameters.GLOBAL_PARAMETERS['DEFAULT_PROGRAM_MODE']

		if program_mode in ['TEST', 'PROD']:
			self.trading_manager = LiveTrading(
				parameters,
				portfolio,
				simulation_saver
			)
		else:
			self.trading_manager = BackTesting(
				parameters,
				portfolio,
				simulation_saver)

		self.parameters = parameters
		self.portfolio = portfolio

		#Used to store the data
		self.COLUMN_MAPPING = {
			("Variation", '1m'): 0, ("Variation", "1h"): 1,
			("Volume", '1m'): 2, ("Volume", "1h"): 3,
			("NbOfTrades", '1m'): 4, ("NbOfTrades", "1h"): 5,
			("Price is going up", ""): 6
		}
		self.data_storage = self.create_dataframe_for_storage()
		self.ticker_mapping : dict[str, int] = {}
		self.next_free_index = 0

		#Used to store the prices and data after pump
		self.prices : defaultdict[str, list[float]] = defaultdict(list)
		self.potential_pump : defaultdict[str, dict[str, float]] = defaultdict(list)

		#USED FOR SELLING
		self.max_z_score : dict[str, float] = {}
		self.z_score_hits = False

	def define_stop_losses(self, ticker, current_price):
		step_size, tick_size = self.trading_manager.get_ticker_tick_size(ticker)
		scaled_price = self.parameters.SPECIFIC_PARAMETERS['stop_loss_prct'] * current_price
		price_step = scaled_price // tick_size
		stop_loss_price = round(price_step*tick_size,8)
		quantity = self.trading_manager.portfolio.actifs[ticker]['quantity']
		quantity_step = quantity//step_size
		quantity_bought = str(round(quantity_step*step_size,8))
		self.parameters.ticker_bought_actual_max_price[ticker] = {'max_price' : current_price,
																'step_size' : step_size,
																'tick_size' : tick_size,
																'current_stop_loss_price' : stop_loss_price}
		self.trading_manager.place_stop_loss(ticker, quantity_bought, stop_loss_price)

	def detect_potential_pump(self, data):
		ticker = data['k']['s']
		if ticker in self.parameters.crypto_bought:
			return False
		row_idx = self.get_ticker_index(ticker)
		variation_1m = self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", '1m')]]
		variation_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", "1h")]]
		if self.parameters.SPECIFIC_PARAMETERS['first_check_variation']*variation_1m <= variation_1h:
			return False

		volume_1m = self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", '1m')]]
		volume_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", "1h")]]

		#print("Volume", volume_m, volume_1h, ticker)

		if self.parameters.SPECIFIC_PARAMETERS['first_check_volume']*volume_1m <= volume_1h:
			return False

		nb_of_trades_1m = self.data_storage[row_idx, self.COLUMN_MAPPING[("NbOfTrades", '1m')]]
		nb_of_trades_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("NbOfTrades", "1h")]]

		#print("NbOftrades", nb_of_trades_m, nb_of_trades_1h)

		if self.parameters.SPECIFIC_PARAMETERS['first_check_nb_of_trades']*nb_of_trades_1m <= nb_of_trades_1h:
			return False

		price_is_going_up = self.data_storage[
			row_idx, self.COLUMN_MAPPING[("Price is going up", "")]
		]

		#print('Price is going up', price_is_going_up)

		if not price_is_going_up:
			return False
		if price_is_going_up == np.float32('inf'):
			return False
		self.potential_pump[ticker].append(data)

	def confirm_pump(self, data):
		current_event_time = data['E']
		current_k = data['k']
		current_volume = float(current_k['v'])
		current_nb_of_trades = current_k['n']
		current_price = float(current_k['c'])
		tolerance_trades = self.parameters.SPECIFIC_PARAMETERS['second_check_nb_of_trades']
		tolerance_volume = self.parameters.SPECIFIC_PARAMETERS['second_check_volume']

		to_delete = []
		for crypto, last_k_line in self.potential_pump.items():
			last_k_line = last_k_line[-1]
			to_delete.append(crypto)
			last_event_time = last_k_line['E']
			last_k = last_k_line['k']
			last_volume = float(last_k['v'])
			last_nb_of_trades = last_k['n']
			last_current_price = float(last_k['c'])
			print(datetime.datetime.now(), ' Could have bought : ', crypto, ' | at : ', last_current_price)
	
			#1. Price must not be lower
			if current_price < last_current_price:
				print("price lower")
				continue

			#2. Kline must be frequent
			if (self.parameters.GLOBAL_PARAMETERS['DEFAULT_PROGRAM_MODE'] != 'BACKTEST' 
	   			and abs(current_event_time-last_event_time) > 2500):
				print("event_time", current_event_time, last_event_time)
				continue

			#3. Number of trades and volume must increase
			if current_nb_of_trades > last_nb_of_trades:
				if (current_nb_of_trades - last_nb_of_trades)/last_nb_of_trades < tolerance_trades:
					print('nb_of_trades', current_nb_of_trades, last_nb_of_trades)
					continue
			else:
				if current_nb_of_trades / last_nb_of_trades < tolerance_trades:
					print('nb_of_trades', current_nb_of_trades, last_nb_of_trades)
					continue
	
			#4. Volume must increase
			if current_volume > last_volume:
				if (current_volume - last_volume) / last_volume < tolerance_volume:
					print('volume', current_volume, last_volume)
					continue
			else:
				if current_volume / last_volume < tolerance_volume:
					print('volume', current_volume, last_volume)
					continue
			#All checks passed : pump confirmed
			self.buy_decision(data)
		
		for crypto in to_delete:
			del self.potential_pump[crypto]

	def get_trading_pair(self, ticker, priority=['USDC', 'TRY', 'BTC']):
		#Possible to change priority if high vol on btc for exemple
		set_trading_pair = self.trading_pairs[ticker]
		for quote in priority:
			if quote in set_trading_pair:
				return quote
		print(self.trading_pairs[ticker])
		raise ValueError('See print statement for debug')

	def quantity_to_buy(self, cash_used, trading_ticker):
		"""Convert USDT cash_used amount in TRY OR BTC
		For example if USDCTRY = 38|cash_used = 10
		quantity = 380 which reprents the amount 10 usdt in TRY
		"""
		if trading_ticker == 'USDC':
			quantity = cash_used
		elif trading_ticker == 'BTC':
			quantity = round(cash_used/self.prices['BTCUSDT'][-1], 8)
		elif trading_ticker == 'TRY':
			quantity = round(cash_used*self.prices['USDCTRY'][-1], 8)
		return str(quantity)

	def buy_decision(self, data):
		now = datetime.datetime.fromtimestamp(int(data['E'])/1000)
		k = data['k']
		original_pair = k['s']
		trading_ticker = self.get_trading_pair(original_pair[:-4])
		pair = original_pair[:-4] + trading_ticker
		if not self.prices[pair]:
			return
		current_price = self.prices[pair][-1] #In quote asset base
		current_price_usdt = float(k['c']) #In USDT

		if now.minute % 15 == 0:
			cash_used = 10 #30
		else:
			cash_used = 10
		quote_order_qty = self.quantity_to_buy(cash_used, trading_ticker)
		try:
			self.trading_manager.portfolio.check_buy_sell(
				'BUY',
				pair,
				cash_used/current_price_usdt,
				current_price_usdt
			)
			self.portfolio.current_btc_usdt_price = self.prices['BTCUSDT'][-1]
			self.portfolio.current_usdc_try_price = self.prices['USDCTRY'][-1]
			self.trading_manager.buy(pair, float(quote_order_qty), current_price, data['E'])
		except AssertionError:
			print(f'Order to buy {pair} was not send, not enough cash on portfolio.')
		self.parameters.crypto_bought[original_pair] = now

	def manage_sell_limits_orders(self, data):
		#Possible de manage_sell a partir de mini ticker au lieu de take get_trading_pair
		k = data['k']
		ticker = k['s']
		trading_pair = self.get_trading_pair(ticker[:-4])
		pair = ticker[:-4] + trading_pair
		current_price = self.prices[pair][-1]

		mean_window_size = self.parameters.GLOBAL_PARAMETERS['MEAN_ROLLING_SIZE']
		std_window_size = self.parameters.GLOBAL_PARAMETERS['STD_ROLLING_SIZE']
		if np.std(self.prices[ticker][-std_window_size:]) > 0:
			current_z_score = ((current_price - np.mean(self.prices[ticker][-mean_window_size:])) 
					  			/ np.std(self.prices[ticker][-std_window_size:]))
		else:
			current_z_score = float('-inf')
		max_z_score = self.max_z_score.get(ticker, 0)

		self.max_z_score[ticker] = max(max_z_score, current_z_score)
		threshold = 1
		#print(ticker, current_z_score, current_price, np.mean(self.prices[ticker][-mean_window_size:]), np.std(self.prices[ticker][-std_window_size:]))

		#try to take quantity in portfolio instead ?
		step_size = self.parameters.ticker_bought_actual_max_price[pair]['step_size']
		tick_size = self.parameters.ticker_bought_actual_max_price[pair]['tick_size']
		quantity = self.trading_manager.portfolio.actifs[pair]['quantity']
		quantity_step = quantity // step_size
		quantity_bought = str(round(quantity_step*step_size,8))

		if current_price > self.parameters.ticker_bought_actual_max_price[pair]['max_price'] and not self.z_score_hits:
			self.parameters.ticker_bought_actual_max_price[pair]['max_price'] = current_price

			scaled_price = self.parameters.SPECIFIC_PARAMETERS['stop_loss_prct'] * current_price
			price_step = scaled_price // tick_size
			new_stop_loss_price = round(price_step*tick_size,8)
			self.trading_manager.cancel_replace(pair, quantity_bought, new_stop_loss_price)
		elif current_z_score < threshold and self.max_z_score[ticker] > threshold:
			#Peut-être, récupérer la quantité du portfolio à la place de calculer la quantité achetée
			self.z_score_hits = True
			scaled_price = self.parameters.SPECIFIC_PARAMETERS['stop_loss_adjust_stop_loss'] * current_price
			price_step = scaled_price // tick_size
			new_stop_loss_price = round(price_step*tick_size,8)
			if self.parameters.ticker_bought_actual_max_price[pair]['current_stop_loss_price'] < new_stop_loss_price:
				self.parameters.ticker_bought_actual_max_price[pair]['current_stop_loss_price'] = new_stop_loss_price
				self.trading_manager.cancel_replace(pair, quantity_bought, new_stop_loss_price)


	def take_decision(self, data):
		original_pair = data['k']['s']
		pair = original_pair[:-4] + self.get_trading_pair(original_pair[:-4])
		if original_pair in self.potential_pump and original_pair not in self.parameters.crypto_bought:
			self.confirm_pump(data)
		self.detect_potential_pump(data)

		if (pair in self.trading_manager.portfolio.actifs and
			pair in self.parameters.ticker_bought_actual_max_price):
		#Les deux dict doivent être fusionnés
			self.manage_sell_limits_orders(data)

	def update_parameters(self, websocket_stream : str, k):
		""" Update parameters (volume/variation/nb of trades) if there is Update parameters"""
		pair : str = k['s']
		current_price = float(k['c'])
		if pair.endswith('USDT'):
			#self.update_USDT_pairs()
			variation = float(k['h'])-float(k['l'])
			volume = float(k['v'])
			nb_of_trades = k['n']
			row_idx = self.get_ticker_index(pair)
			self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", websocket_stream)]] = variation
			self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", websocket_stream)]] = volume
			self.data_storage[row_idx, self.COLUMN_MAPPING[("NbOfTrades", websocket_stream)]] = nb_of_trades
			if websocket_stream == '1m':
				price_is_going_up = bool(float(k['c']) > float(k['o']))
				self.data_storage[row_idx, self.COLUMN_MAPPING[("Price is going up", "")]] = price_is_going_up
			if 'E' in k:
				now = datetime.datetime.fromtimestamp(int(k['E']) / 1000)
				self.parameters.crypto_bought = {
					pair: last_buy_time
					for pair, last_buy_time in self.parameters.crypto_bought.items()
					if now - last_buy_time <= datetime.timedelta(minutes=30)
				}

		if pair == 'BTCUSDT':
			self.portfolio.current_btc_usdt_price = current_price
		elif pair == 'USDCTRY':
			self.portfolio.current_usdc_try_price = current_price

		if pair in self.portfolio.actifs:
			self.portfolio.update_portfolio_value(pair, current_price)
		
		self.prices[pair].append(current_price)
		if (len(self.prices[pair]) > 
	  		max(self.parameters.GLOBAL_PARAMETERS['MEAN_ROLLING_SIZE'], self.parameters.GLOBAL_PARAMETERS['STD_ROLLING_SIZE'])):
			self.prices[pair].pop(0)

	def create_dataframe_for_storage(self):
		return np.full((360, len(self.COLUMN_MAPPING)), np.inf, dtype=np.float32)

	def get_ticker_index(self, ticker):
		if ticker not in self.ticker_mapping:
			self.ticker_mapping[ticker] = self.next_free_index
			self.next_free_index += 1
		return self.ticker_mapping[ticker]
