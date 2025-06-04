import datetime
import numpy as np
import logging
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
		self.ticker_bought_parameters : dict[str, dict[str, str]] = {}
		#USED FOR SELLING
		self.max_z_score : dict[str, float] = {}
		self.z_score_hits : dict[str, bool] = {}

	def define_stop_losses(self, pair, current_price):
		step_size, tick_size = self.trading_manager.get_ticker_tick_size(pair)
		stop_loss_prct = self.parameters.SPECIFIC_PARAMETERS['stop_loss_prct']
		stop_loss_price = self.get_price_for_stop_loss(current_price, tick_size, stop_loss_prct)
		quantity_bought = self.get_quantity_for_stop_loss(pair, step_size)
		self.trading_manager.place_stop_loss(pair, quantity_bought, stop_loss_price)

		self.ticker_bought_parameters[pair]['max_price'] = current_price
		self.ticker_bought_parameters[pair]['step_size'] = step_size
		self.ticker_bought_parameters[pair]['tick_size'] = tick_size
		self.ticker_bought_parameters[pair]['current_stop_loss_price'] = stop_loss_price


	def get_price_for_stop_loss(self, current_price, tick_size, stop_loss_prct):
		"""Get the price for stop loss according to the tick size"""
		scaled_price = stop_loss_prct * current_price
		price_step = scaled_price // tick_size
		stop_loss_price = round(price_step * tick_size,8)
		return stop_loss_price

	def get_quantity_for_stop_loss(self, ticker, step_size):
		"""Get the quantity for stop loss according to the step size"""
		quantity = self.trading_manager.portfolio.actifs[ticker]['quantity']
		quantity_step = quantity // step_size
		quantity_bought = str(round(quantity_step * step_size, 8))
		return quantity_bought

	def detect_potential_pump(self, pair, data):
		""" This is the first check.
		Detect potential pump based on the data received from the websocket stream."""
		pair_in_usdt = data['k']['s']
		if pair in self.portfolio.actifs:
			return False
		row_idx = self.get_ticker_index(pair_in_usdt)
		variation_1m = self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", '1m')]]
		variation_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", "1h")]]
		if self.parameters.SPECIFIC_PARAMETERS['first_check_variation']*variation_1m <= variation_1h:
			return False

		volume_1m = self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", '1m')]]
		volume_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", "1h")]]

		logging.DEBUG("Volume", volume_1m, volume_1h, pair)

		if self.parameters.SPECIFIC_PARAMETERS['first_check_volume']*volume_1m <= volume_1h:
			return False

		nb_of_trades_1m = self.data_storage[row_idx, self.COLUMN_MAPPING[("NbOfTrades", '1m')]]
		nb_of_trades_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("NbOfTrades", "1h")]]

		logging.DEBUG("NbOftrades", nb_of_trades_1m, nb_of_trades_1h, pair)

		if self.parameters.SPECIFIC_PARAMETERS['first_check_nb_of_trades']*nb_of_trades_1m <= nb_of_trades_1h:
			return False

		price_is_going_up = self.data_storage[
			row_idx, self.COLUMN_MAPPING[("Price is going up", "")]
		]

		logging.DEBUG("NbOftrades", nb_of_trades_1m, nb_of_trades_1h, pair)
		#print('Price is going up', price_is_going_up)

		if not price_is_going_up:
			return False
		if price_is_going_up == np.float32('inf'):
			return False
		self.potential_pump[pair].append(data)

	def confirm_pump(self, data):
		""" This is the second check.
		Confirm the pump based on the last kline data received and the current kline data.
		The idea is to check if their is a real pump dynamic."""
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

			#3. Number of trades must inscrease
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
		For example if USDCTRY = 38 | cash_used = 10
		quantity = 380 which reprents the amount of 10 usdt in TRY
		"""
		if trading_ticker == 'USDC':
			quantity = cash_used
		elif trading_ticker == 'BTC':
			quantity = round(cash_used/self.prices['BTCUSDT'][-1], 8)
		elif trading_ticker == 'TRY':
			quantity = round(cash_used*self.prices['USDCTRY'][-1], 8)
		return str(quantity)

	@staticmethod
	def cash_used(now : datetime.datetime)->float:
		"""
		Calculate the amount of cash used for a given time and data.
		Args:
			now (datetime.datetime): The current time.
		Returns:
			float: The amount of cash used.
		"""
		if now.minute % 15 == 0:
			cash_used = 10#30
		else:
			cash_used = 10
		return cash_used

	def buy_decision(self, data):
		""" Send a buy order to the trading manager. (Make necessary checks and conversions)"""
		now = datetime.datetime.fromtimestamp(int(data['E'])/1000)
		k = data['k']
		original_pair = k['s']
		trading_ticker = self.get_trading_pair(original_pair[:-4])
		pair = original_pair[:-4] + trading_ticker
		if not self.prices[pair]:
			return
		current_price = self.prices[pair][-1] # This is the pair with quote asset in USDC/TRY/BTC
		cash_used = self.cash_used(now)
		quote_order_qty = self.quantity_to_buy(cash_used, trading_ticker)
		try:
			current_price_usdt = float(k['c']) # This is the pair with quote asset in USDT
			self.trading_manager.portfolio.check_buy_sell(
				'BUY',
				pair,
				cash_used/current_price_usdt,
				current_price_usdt
			)
			self.ticker_bought_parameters[pair] = {'date_of_buy' : now}
			self.z_score_hits[pair] = False
			self.trading_manager.buy(pair, float(quote_order_qty), current_price, data['E'])
		except AssertionError:
			print(f'Order to buy {pair} was not send, not enough cash on portfolio.')
			return None
		
		return None

	def compute_z_score(self, prices_series : list[float], mean_window_size : int, std_window_size : int)->float:
		"""
		Computes the z-score for a given price series.
		The z-score is calculated as the difference between the current price and the mean of the last 'mean_window_size' prices,
		divided by the standard deviation of the last 'std_window_size' prices.
		Args:
			prices_series (list[float]): A list of prices for a specific trading pair.
			mean_window_size (int): The size of the rolling window for calculating the mean.
			std_window_size (int): The size of the rolling window for calculating the standard deviation.
		Returns:
			float: The computed z-score.
		"""
		if np.std(prices_series[-std_window_size:]) > 0:
			return ((prices_series[-1] - np.mean(prices_series[-mean_window_size:])) /
					np.std(prices_series[-std_window_size:]))
		else:
			return float('-inf')

	def manage_sell_limits_orders(self, data : dict[str, dict[str, str]])->None:
		"""
		Manages sell limit orders based on price movements and z-score thresholds.
		This method updates stop-loss orders for a given trading pair when certain price or statistical conditions are met.
		It tracks the maximum z-score observed for the ticker and adjusts stop-loss prices accordingly to lock in profits or minimize losses.
		Args:
			data (dict[str, dict[str, str]]):
				A dictionary containing market data.
				Expected to have a 'k' key with sub-keys including 's' (symbol/ticker).
		Returns:
			None
		Workflow:
			- Extracts the trading pair and current price from the data.
			- Calculates the rolling mean and standard deviation for the price to compute the current z-score.
			- Updates the maximum z-score observed for the ticker.
			- If the current price exceeds the previous maximum price and the z-score threshold hasn't been hit, 
			  updates the stop-loss price to a new higher value.
			- If the z-score drops below the threshold after previously exceeding it, 
			  adjusts the stop-loss price to secure profits.
			- Interacts with the trading manager to cancel and replace stop-loss orders as needed.
		"""

		k = data['k']
		ticker_usdt = k['s']
		trading_pair = self.get_trading_pair(ticker_usdt[:-4])
		pair = ticker_usdt[:-4] + trading_pair #Pair in USDC/TRY/BTC
		prices_series = self.prices[pair]
		current_price = prices_series[-1]

		mean_window_size = self.parameters.GLOBAL_PARAMETERS['MEAN_ROLLING_SIZE']
		std_window_size = self.parameters.GLOBAL_PARAMETERS['STD_ROLLING_SIZE']
		current_z_score = self.compute_z_score(prices_series, mean_window_size, std_window_size)

		max_z_score = self.max_z_score.get(ticker_usdt, 0)

		self.max_z_score[ticker_usdt] = max(max_z_score, current_z_score)
		threshold = 1

		step_size = self.ticker_bought_parameters[pair]['step_size']

		stop_loss_prct = None

		if current_price > self.ticker_bought_parameters[pair]['max_price'] and not self.z_score_hits[pair]:
			stop_loss_prct = self.parameters.SPECIFIC_PARAMETERS['stop_loss_prct']
			self.ticker_bought_parameters[pair]['max_price'] = current_price
		elif current_z_score < threshold and self.max_z_score[ticker_usdt] > threshold:
			stop_loss_prct = self.parameters.SPECIFIC_PARAMETERS['stop_loss_adjust_stop_loss']
			self.z_score_hits[pair] = True
		
		if stop_loss_prct is not None:
			tick_size = self.ticker_bought_parameters[pair]['tick_size']
			new_stop_loss_price = self.get_price_for_stop_loss(current_price, tick_size, stop_loss_prct)
			if self.ticker_bought_parameters[pair]['current_stop_loss_price'] < new_stop_loss_price:
				self.ticker_bought_parameters[pair]['current_stop_loss_price'] = new_stop_loss_price
				quantity_bought = self.get_quantity_for_stop_loss(pair, step_size)
				self.trading_manager.cancel_replace(pair, quantity_bought, new_stop_loss_price)
		
		return None

	def take_decision(self, data):
		""" Take decision based on the data received from the websocket stream."""
		pair_in_usdt = data['k']['s']
		pair = pair_in_usdt[:-4] + self.get_trading_pair(pair_in_usdt[:-4]) #Pair in USDC/TRY/BTC
		
		if pair in self.potential_pump:
			date_achat = self.ticker_bought_parameters.get(pair, {}).get('date_of_buy', None)
			now = datetime.datetime.fromtimestamp(int(data['E']) / 1000)
			if date_achat is None or (now - date_achat) >= datetime.timedelta(minutes=30):
				self.confirm_pump(data)

		self.detect_potential_pump(pair, data)

		if pair in self.trading_manager.portfolio.actifs:
			self.manage_sell_limits_orders(data)

	def update_USDT_volume_variation_nb_of_trades(self, websocket_stream, k):
		"""
		Update variation, volume, and number of trades information for a given pair from websocket stream data.

		Args:
			websocket_stream (str): The type of websocket stream (e.g., '1m' for one minute).
			k (dict): Dictionary containing ticker data, including:
				- 's': symbol of the pair (str)
				- 'h': highest price (str or float convertible)
				- 'l': lowest price (str or float convertible)
				- 'v': traded volume (str or float convertible)
				- 'n': number of trades (int or str convertible)
				- 'c': closing price (str or float convertible)
				- 'o': opening price (str or float convertible)
				- 'E': event time (optional, int or str convertible)
		"""
		pair : str = k['s']
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
			
	def update_parameters(self, websocket_stream : str, k):
		"""Update trading parameters such as volume, price variation, and number of trades.
		Uses the most recent window of prices for z-score calculations."""
		pair : str = k['s']
		current_price = float(k['c'])
		if pair.endswith('USDT'):
			self.update_USDT_volume_variation_nb_of_trades(websocket_stream, k)

		#Used to make conversion between USDT and TRY/BTC
		if pair == 'BTCUSDT':
			self.portfolio.current_btc_usdt_price = current_price
		elif pair == 'USDCTRY':
			self.portfolio.current_usdc_try_price = current_price

		#Used to update the price of the pair in the portfolio
		if pair in self.portfolio.actifs:
			self.portfolio.update_portfolio_value(pair, current_price)

		#Used to update store the price of the pair (used later for z-score)
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
