import datetime
import numpy as np
from collections import defaultdict
from bot.utils.helpers import Portfolio, Parameters
from bot.strategy.base_strategy import Strategy
from bot.trading.base_trading import SimulationSaver
from bot.trading.backtesting import BackTesting
from bot.trading.live_trading import LiveTrading


class PumpDump(Strategy):

	def __init__(self, parameters : Parameters, portfolio : Portfolio, simulation_saver : SimulationSaver):
		if parameters.duration_time <= 0:
			raise ValueError("durationTime must be positive.")
		if not isinstance(parameters.program_type, str):
			raise TypeError("isTestMode must be a string.")
		super().__init__(parameters.duration_time)
		self.parameters = parameters
		self.portfolio = portfolio

		self.COLUMN_MAPPING = {
			("Variation", parameters.kline_type): 0, ("Variation", "1h"): 1,
			("Volume", parameters.kline_type): 2, ("Volume", "1h"): 3,
			("NbOfTrades", parameters.kline_type): 4, ("NbOfTrades", "1h"): 5,
			("Price is going up", ""): 6
		}

		#USED FOR BUY
		#90% des ordres sont des market makers
		#Il y a toujours des achats qui sont réalisés
		self.potential_pump = defaultdict(list)

		self.data_storage = self.create_dataframe_for_storage()
		self.ticker_mapping = {}
		self.next_free_index = 0

		#USED FOR SELLING
		self.prices = defaultdict(list)
		self.max_z_score = {}
		self.z_score_hits = False

		if parameters.program_type in ['TEST', 'PROD']:
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

	def define_stop_losses(self, ticker, current_price):
		step_size, tick_size = self.trading_manager.get_ticker_tick_size(ticker)
		scaled_price = self.parameters.stop_loss_prct * current_price
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

	def create_dataframe_for_storage(self):
		return np.full((300, len(self.COLUMN_MAPPING)), np.inf, dtype=np.float32)

	def get_ticker_index(self, ticker):
		if ticker not in self.ticker_mapping:
			if self.next_free_index >= 300:
				raise ValueError("Plus de place disponible dans le tableau")
			self.ticker_mapping[ticker] = self.next_free_index
			self.next_free_index += 1

		return self.ticker_mapping[ticker]

	def detect_potential_pump(self, data):
		ticker = data['k']['s'][:-4]+'USDC'
		if ticker in self.parameters.crypto_bought:
			return False
		row_idx = self.get_ticker_index(ticker)
		variation_m = self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", self.parameters.kline_type)]]
		variation_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", "1h")]]

		if self.parameters.limits['variation']*variation_m <= variation_1h:
			return False

		volume_m = self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", self.parameters.kline_type)]]
		volume_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", "1h")]]

		#print("Volume", volume_3m, volume_1h)

		if self.parameters.limits['volume']*volume_m <= volume_1h:
			return False

		nb_of_trades_m = self.data_storage[row_idx, self.COLUMN_MAPPING[("NbOfTrades", self.parameters.kline_type)]]
		nb_of_trades_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("NbOfTrades", "1h")]]

		#print("NbOftrades", nb_of_trades_m, nb_of_trades_1h)

		if self.parameters.limits['nbOfTrades']*nb_of_trades_m <= nb_of_trades_1h:
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
		#Open a kline 1s to receive real time orders can be a good idea

		current_event_time = data['E']
		current_k = data['k']
		current_volume = float(current_k['v'])
		current_nb_of_trades = current_k['n']
		current_price = float(current_k['c'])

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
			if current_price < last_current_price:
				continue
			if abs(current_event_time-last_event_time) > 2500:
				print("event_time", current_event_time, last_event_time)
				continue
			if current_nb_of_trades > last_nb_of_trades and (current_nb_of_trades - last_nb_of_trades)/last_nb_of_trades < 0.1:
				print('nb_of_trades', current_nb_of_trades, last_nb_of_trades)
				continue
			if last_nb_of_trades > current_nb_of_trades and current_nb_of_trades/last_nb_of_trades < 0.05:
				print('nb_of_trades', current_nb_of_trades, last_nb_of_trades)
				continue
			if current_volume > last_volume and (current_volume - last_volume)/last_volume < 0.1:
				print('volume', current_volume, last_volume)
				continue
			if last_volume > current_volume and current_volume/last_volume < 0.05:
				print('volume', current_volume, last_volume)
				continue
			self.buy_decision(data)
		for crypto in to_delete:
			del self.potential_pump[crypto]


	def buy_decision(self, data):
		now = datetime.datetime.fromtimestamp(int(data['E'])/1000)
		k = data['k']
		ticker = k['s'][:-4]+'USDC'
		current_price = float(k['c'])

		if True:
			cash_used = '10'
			if now.minute % 15 == 0:
				cash_used = '10'
			try:
				self.trading_manager.portfolio.check_buy_sell(
					'BUY',
					ticker,
					float(cash_used)/current_price, current_price
				)
				self.trading_manager.buy(ticker, float(cash_used), current_price, data['E'])
			except AssertionError:
				print(f'Order to buy {ticker} was not send, not enough cash on portfolio.')
			self.parameters.crypto_bought.append(ticker)

	def manage_sell_limits_orders(self, data):
		k = data['k']
		ticker = k['s'][:-4]+'USDC'
		current_price = float(k['c'])
		now = datetime.datetime.fromtimestamp(int(data['E'])/1000)

		#Les deux dict doivent être fusionnés
		if (ticker in self.trading_manager.portfolio.actifs and
			ticker in self.parameters.ticker_bought_actual_max_price):
			#print(ticker, close_price,
			# self.parameters.ticker_bought_actual_max_price[ticker]['entry_price'])
			mean_window_size = self.parameters.mean_rolling_size
			std_window_size = self.parameters.std_rolling_size

			current_z_score = (current_price - np.mean(self.prices[ticker][-mean_window_size:])) / np.std(self.prices[ticker][-std_window_size:])
			max_z_score = self.max_z_score.get(ticker, 0)

			self.max_z_score[ticker] = max(max_z_score, current_z_score)
			threshold = 1
			#print(ticker, current_z_score, current_price, np.mean(self.prices[ticker][-mean_window_size:]), np.std(self.prices[ticker][-std_window_size:]))
			
			#try to take quantity in portfolio instead ?
			step_size = self.parameters.ticker_bought_actual_max_price[ticker]['step_size']
			tick_size = self.parameters.ticker_bought_actual_max_price[ticker]['tick_size']
			quantity = self.trading_manager.portfolio.actifs[ticker]['quantity']
			quantity_step = quantity // step_size
			quantity_bought = str(round(quantity_step*step_size,8))

			if current_price > self.parameters.ticker_bought_actual_max_price[ticker]['max_price'] and not self.z_score_hits:
				self.parameters.ticker_bought_actual_max_price[ticker]['max_price'] = current_price

				scaled_price = self.parameters.stop_loss_prct * current_price
				price_step = scaled_price // tick_size
				new_stop_loss_price = round(price_step*tick_size,8)
				#print("NEW STOP LOSS PRICE", new_stop_loss_price)
				self.trading_manager.cancel_replace(ticker, quantity_bought, new_stop_loss_price)
			elif current_z_score < threshold and self.max_z_score[ticker] > threshold:
				#Peut-être récupérer la quantité du portfolio à la place de calculer la quantité achetée

				self.z_score_hits = True
				scaled_price = 0.995 * current_price
				price_step = scaled_price // tick_size
				new_stop_loss_price = round(price_step*tick_size,8)
				if self.parameters.ticker_bought_actual_max_price[ticker]['current_stop_loss_price'] < new_stop_loss_price:
					print('SELLLLLLLL', ticker, now, self.parameters.ticker_bought_actual_max_price[ticker]['current_stop_loss_price'], new_stop_loss_price, current_price)
					self.parameters.ticker_bought_actual_max_price[ticker]['current_stop_loss_price'] = new_stop_loss_price
					self.trading_manager.cancel_replace(ticker, quantity_bought, new_stop_loss_price)

	def take_decision(self, data):
		ticker = data['k']['s'][:-4]+'USDC'
		if ticker in self.potential_pump:
			self.confirm_pump(data)
		self.detect_potential_pump(data)
		self.manage_sell_limits_orders(data)


	def update_parameters(self, websocket_stream, k):
		ticker = k['s'][:-4]+'USDC'
		variation = float(k['h'])-float(k['l'])
		volume = float(k['v'])
		nb_of_trades = k['n']
		current_price = float(k['c'])
		row_idx = self.get_ticker_index(ticker)

		self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", websocket_stream)]] = variation
		self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", websocket_stream)]] = volume
		self.data_storage[row_idx, self.COLUMN_MAPPING[("NbOfTrades", websocket_stream)]] = nb_of_trades

		self.prices[ticker].append(current_price)
		if len(self.prices[ticker]) > max(self.parameters.mean_rolling_size, self.parameters.std_rolling_size):
			self.prices[ticker].pop(0)
		
		if websocket_stream == self.parameters.kline_type:
			price_is_going_up = bool(float(k['c']) > float(k['o']))
			self.data_storage[row_idx, self.COLUMN_MAPPING[("Price is going up", "")]] = price_is_going_up
