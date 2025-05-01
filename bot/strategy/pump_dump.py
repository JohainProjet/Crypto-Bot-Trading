import datetime
import numpy as np
from collections import defaultdict
from bot.utils.helpers import Portfolio, Parameters
from bot.strategy.base_strategy import Strategy
from bot.trading.base_trading import SimulationSaver
from bot.trading.backtesting import BackTesting
from bot.trading.live_trading import LiveTrading
import threading

class PumpDump(Strategy):
	trading_pairs = {'1000CAT': {'USDC', 'TRY', 'USDT'},
					'1000CHEEMS': {'USDC', 'USDT'},
					'1000SATS': {'USDC', 'TRY', 'USDT'},
					'1INCH': {'BTC', 'USDT'},
					'1MBABYDOGE': {'USDC', 'TRY', 'USDT'},
					'AAVE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ACA': {'TRY', 'BTC', 'USDT'},
					'ACE': {'TRY', 'USDT'},
					'ACH': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ACT': {'USDC', 'TRY', 'USDT'},
					'ACX': {'USDC', 'TRY', 'USDT'},
					'ADA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ADX': {'BTC', 'USDT'},
					'AEVO': {'TRY', 'BTC', 'USDT'},
					'AGLD': {'BTC', 'USDT'},
					'AI': {'TRY', 'BTC', 'USDT'},
					'AIXBT': {'USDC', 'TRY', 'USDT'},
					'ALGO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ALICE': {'TRY', 'USDT'},
					'ALPINE': {'TRY', 'USDT'},
					'ALT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AMP': {'TRY', 'USDT'},
					'ANIME': {'USDC', 'TRY', 'USDT'},
					'ANKR': {'TRY', 'BTC', 'USDT'},
					'APE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'API3': {'USDC', 'TRY', 'BTC', 'USDT'},
					'APT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AR': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ARB': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ARDR': {'BTC', 'USDT'},
					'ARK': {'TRY', 'USDT'},
					'ARKM': {'USDC', 'BTC', 'TRY', 'USDT'},
					'ARPA': {'TRY', 'BTC', 'USDT'},
					'ASR': {'TRY', 'USDT'},
					'ASTR': {'BTC', 'USDT'},
					'ATA': {'BTC', 'USDT'},
					'ATM': {'TRY', 'USDT'},
					'ATOM': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AUCTION': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AUDIO': {'TRY', 'BTC', 'USDT'},
					'AVA': {'BTC', 'USDT'},
					'AVAX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'AXL': {'TRY', 'BTC', 'USDT'},
					'AXS': {'TRY', 'BTC', 'USDT'},
					'BABY': {'USDC', 'TRY', 'USDT'},
					'BAKE': {'TRY', 'BTC', 'USDT'},
					'BANANA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BANANAS31': {'USDC', 'USDT'},
					'BAND': {'BTC', 'USDT'},
					'BAR': {'TRY', 'USDT'},
					'BAT': {'BTC', 'USDT'},
					'BB': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BCH': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BEAMX': {'USDC', 'TRY', 'USDT'},
					'BEL': {'TRY', 'BTC', 'USDT'},
					'BERA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BICO': {'BTC', 'USDT'},
					'BIGTIME': {'USDC', 'USDT'},
					'BIO': {'USDC', 'TRY', 'USDT'},
					'BLUR': {'USDC', 'TRY', 'USDT'},
					'BMT': {'USDC', 'TRY', 'USDT'},
					'BNB': {'USDC', 'TRY', 'BTC', 'USDT'},
					'BOME': {'USDC', 'TRY', 'USDT'},
					'BONK': {'USDC', 'TRY', 'USDT'},
					'BROCCOLI714': {'USDC', 'USDT'},
					'BSW': {'TRY', 'USDT'},
					'BTC': {'USDC', 'TRY', 'USDT'},
					'BTTC': {'TRY', 'USDT'},
					'CAKE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'CATI': {'USDC', 'TRY', 'USDT'},
					'CELO': {'TRY', 'BTC', 'USDT'},
					'CETUS': {'USDC', 'TRY', 'USDT'},
					'CFX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'CGPT': {'USDC', 'USDT'},
					'CHESS': {'USDC', 'USDT'},
					'CHR': {'BTC', 'USDT'},
					'CHZ': {'USDC', 'TRY', 'BTC', 'USDT'},
					'CITY': {'TRY', 'USDT'},
					'CKB': {'USDC', 'TRY', 'USDT'},
					'COMP': {'TRY', 'BTC', 'USDT'},
					'COOKIE': {'USDC', 'USDT'},
					'COS': {'TRY', 'USDT'},
					'COTI': {'TRY', 'BTC', 'USDT'},
					'COW': {'USDC', 'TRY', 'USDT'},
					'CRV': {'USDC', 'TRY', 'BTC', 'USDT'},
					'CTK': {'BTC', 'USDT'},
					'CTSI': {'BTC', 'USDT'},
					'CVC': {'USDC', 'USDT'},
					'CYBER': {'TRY', 'BTC', 'USDT'},
					'D': {'TRY', 'USDT'},
					'DASH': {'BTC', 'USDT'},
					'DATA': {'BTC', 'USDT'},
					'DENT': {'TRY', 'USDT'},
					'DEXE': {'USDT'},
					'DF': {'USDC', 'USDT'},
					'DIA': {'BTC', 'USDT'},
					'DODO': {'BTC', 'USDT'},
					'DOGE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'DOGS': {'USDC', 'TRY', 'USDT'},
					'DOT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'DUSK': {'BTC', 'USDT'},
					'DYDX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'DYM': {'TRY', 'USDT'},
					'EDU': {'TRY', 'USDT'},
					'EGLD': {'USDC', 'TRY', 'BTC', 'USDT'},
					'EIGEN': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ENA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ENJ': {'TRY', 'BTC', 'USDT'},
					'ENS': {'USDC', 'TRY', 'BTC', 'USDT'},
					'EOS': {'USDC', 'TRY', 'BTC', 'USDT'},
					'EPIC': {'USDC', 'USDT'},
					'ETC': {'TRY', 'BTC', 'USDT'},
					'ETH': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ETHFI': {'USDC', 'TRY', 'USDT'},
					'EUR': {'USDC', 'USDT'},
					'EURI': {'USDC', 'USDT'},
					'FDUSD': {'USDC', 'TRY', 'USDT'},
					'FET': {'USDC', 'TRY', 'BTC', 'USDT'},
					'FIDA': {'TRY', 'BTC', 'USDT'},
					'FIL': {'USDC', 'TRY', 'BTC', 'USDT'},
					'FIO': {'BTC', 'USDT'},
					'FIS': {'BTC', 'USDT'},
					'FLM': {'BTC', 'USDT'},
					'FLOKI': {'USDC', 'TRY', 'USDT'},
					'FLOW': {'BTC', 'USDT'},
					'FLUX': {'BTC', 'USDT'},
					'FORM': {'TRY', 'USDT', 'USDC'},
					'FORTH': {'BTC', 'USDT'},
					'G': {'TRY', 'USDT'},
					'GALA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'GAS': {'TRY', 'BTC', 'USDT'},
					'GHST': {'USDT'},
					'GLM': {'BTC', 'USDT'},
					'GLMR': {'BTC', 'USDT'},
					'GMT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'GMX': {'USDC', 'USDT'},
					'GPS': {'USDC', 'TRY', 'USDT'},
					'GRT': {'TRY', 'BTC', 'USDT'},
					'GUN': {'USDC', 'TRY', 'USDT'},
					'HBAR': {'USDC', 'TRY', 'BTC', 'USDT'},
					'HEI': {'USDC', 'BTC', 'USDT'},
					'HFT': {'BTC', 'USDT'},
					'HIGH': {'TRY', 'USDT'},
					'HIVE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'HMSTR': {'USDC', 'TRY', 'USDT'},
					'HOT': {'TRY', 'USDT'},
					'HYPER': {'USDC', 'TRY', 'USDT'},
					'ICP': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ICX': {'BTC', 'USDT'},
					'ID': {'TRY', 'BTC', 'USDT'},
					'IDEX': {'USDC', 'USDT'},
					'ILV': {'BTC', 'USDT'},
					'IMX': {'BTC', 'USDT'},
					'INIT': {'USDC', 'TRY', 'USDT'},
					'INJ': {'USDC', 'TRY', 'BTC', 'USDT'},
					'IO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'IOTA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'IOTX': {'BTC', 'USDT'},
					'JASMY': {'TRY', 'USDT'},
					'JOE': {'BTC', 'USDT'},
					'JST': {'BTC', 'USDT'},
					'JTO': {'USDC', 'TRY', 'USDT'},
					'JUP': {'USDC', 'TRY', 'USDT'},
					'JUV': {'USDC', 'TRY', 'USDT'},
					'KAIA': {'USDC', 'USDT'},
					'KAITO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'KAVA': {'BTC', 'USDT'},
					'KDA': {'BTC', 'USDT'},
					'KERNEL': {'TRY', 'USDT', 'USDC'},
					'KMD': {'BTC', 'USDT'},
					'KNC': {'BTC', 'USDT'},
					'KSM': {'TRY', 'BTC', 'USDT'},
					'LAYER': {'USDC', 'TRY', 'BTC', 'USDT'},
					'LAZIO': {'TRY', 'USDT'},
					'LDO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'LEVER': {'TRY', 'USDT'},
					'LINK': {'USDC', 'TRY', 'BTC', 'USDT'},
					'LISTA': {'TRY', 'USDT'},
					'LOKA': {'BTC', 'USDT'},
					'LPT': {'TRY', 'BTC', 'USDT'},
					'LQTY': {'USDT'},
					'LRC': {'TRY', 'BTC', 'USDT'},
					'LSK': {'BTC', 'USDT'},
					'LTC': {'USDC', 'TRY', 'BTC', 'USDT'},
					'LTO': {'BTC', 'USDT'},
					'LUMIA': {'TRY', 'USDT'},
					'LUNA': {'TRY', 'USDT'},
					'LUNC': {'TRY', 'USDT'},
					'MAGIC': {'TRY', 'BTC', 'USDT'},
					'MANA': {'TRY', 'BTC', 'USDT'},
					'MANTA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'MASK': {'TRY', 'USDT'},
					'MAV': {'TRY', 'BTC', 'USDT'},
					'MBOX': {'TRY', 'USDT'},
					'ME': {'TRY', 'BTC', 'USDT'},
					'MEME': {'USDC', 'TRY', 'USDT'},
					'METIS': {'TRY', 'USDT'},
					'MINA': {'TRY', 'BTC', 'USDT'},
					'MKR': {'USDC', 'TRY', 'BTC', 'USDT'},
					'MOVE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'MOVR': {'TRY', 'BTC', 'USDT'},
					'MTL': {'BTC', 'USDT'},
					'MUBARAK': {'USDC', 'USDT'},
					'NEAR': {'USDC', 'TRY', 'BTC', 'USDT'},
					'NEIRO': {'USDC', 'TRY', 'USDT'},
					'NEO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'NEXO': {'BTC', 'USDT'},
					'NFP': {'TRY', 'BTC', 'USDT'},
					'NIL': {'USDC', 'TRY', 'USDT'},
					'NKN': {'BTC', 'USDT'},
					'NMR': {'BTC', 'USDT'},
					'NOT': {'USDC', 'TRY', 'USDT'},
					'NTRN': {'TRY', 'USDT'},
					'OG': {'TRY', 'BTC', 'USDT'},
					'OGN': {'TRY', 'BTC', 'USDT'},
					'OM': {'USDC', 'TRY', 'BTC', 'USDT'},
					'OMNI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ONDO': {'USDC', 'TRY', 'USDT'},
					'ONE': {'TRY', 'BTC', 'USDT'},
					'ONG': {'BTC', 'USDT'},
					'ONT': {'USDC', 'TRY', 'BTC', 'USDT'},
					'OP': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ORCA': {'USDC', 'TRY', 'USDT'},
					'ORDI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'OSMO': {'USDC', 'USDT'},
					'OXT': {'BTC', 'USDT'},
					'PARTI': {'USDC', 'TRY', 'USDT'},
					'PAXG': {'USDC', 'TRY', 'BTC', 'USDT'},
					'PENDLE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'PENGU': {'USDC', 'TRY', 'USDT'},
					'PEOPLE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'PEPE': {'USDC', 'TRY', 'USDT'},
					'PHA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'PHB': {'TRY', 'BTC', 'USDT'},
					'PIVX': {'BTC', 'USDT'},
					'PIXEL': {'USDC', 'TRY', 'USDT'},
					'PNUT': {'USDC', 'BTC', 'TRY', 'USDT'},
					'POL': {'TRY', 'BTC', 'USDT', 'USDC'},
					'POLYX': {'TRY', 'BTC', 'USDT'},
					'PORTAL': {'TRY', 'BTC', 'USDT'},
					'PORTO': {'TRY', 'USDT'},
					'POWR': {'BTC', 'USDT'},
					'PSG': {'TRY', 'USDT'},
					'PYR': {'BTC', 'USDT'},
					'PYTH': {'USDC', 'TRY', 'BTC', 'USDT'},
					'QNT': {'USDC', 'BTC', 'USDT'},
					'QTUM': {'TRY', 'BTC', 'USDT'},
					'RAD': {'TRY', 'USDT'},
					'RARE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'RAY': {'USDC', 'TRY', 'USDT'},
					'RDNT': {'TRY', 'USDT'},
					'RED': {'USDC', 'TRY', 'BTC', 'USDT'},
					'RENDER': {'USDC', 'TRY', 'BTC', 'USDT'},
					'REQ': {'BTC', 'USDT'},
					'REZ': {'USDC', 'TRY', 'USDT'},
					'RIF': {'BTC', 'USDT'},
					'RLC': {'BTC', 'USDT'},
					'RONIN': {'TRY', 'BTC', 'USDT'},
					'ROSE': {'TRY', 'BTC', 'USDT'},
					'RPL': {'USDC', 'USDT'},
					'RSR': {'USDC', 'TRY', 'USDT'},
					'RUNE': {'USDC', 'BTC', 'USDT'},
					'RVN': {'TRY', 'BTC', 'USDT'},
					'S': {'TRY', 'BTC', 'USDT', 'USDC'},
					'SAGA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SAND': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SANTOS': {'TRY', 'BTC', 'USDT'},
					'SCR': {'TRY', 'BTC', 'USDT'},
					'SCRT': {'BTC', 'USDT'},
					'SEI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SFP': {'BTC', 'USDT'},
					'SHELL': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SHIB': {'USDC', 'TRY', 'USDT'},
					'SKL': {'TRY', 'BTC', 'USDT'},
					'SLF': {'TRY', 'BTC', 'USDT', 'USDC'},
					'SLP': {'TRY', 'USDT'},
					'SNX': {'TRY', 'BTC', 'USDT'},
					'SOL': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SOLV': {'TRY', 'USDT'},
					'SPELL': {'TRY', 'USDT'},
					'SSV': {'BTC', 'USDT'},
					'STEEM': {'USDC', 'BTC', 'USDT'},
					'STG': {'BTC', 'USDT'},
					'STORJ': {'TRY', 'BTC', 'USDT'},
					'STPT': {'BTC', 'USDT'},
					'STRAX': {'TRY', 'BTC', 'USDT'},
					'STRK': {'USDC', 'TRY', 'BTC', 'USDT'},
					'STX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SUI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'SUN': {'TRY', 'USDT'},
					'SUPER': {'TRY', 'BTC', 'USDT'},
					'SUSHI': {'TRY', 'BTC', 'USDT'},
					'SXP': {'TRY', 'BTC', 'USDT'},
					'SYN': {'USDC', 'USDT'},
					'SYS': {'BTC', 'USDT'},
					'T': {'USDC', 'USDT'},
					'TAO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TFUEL': {'BTC', 'USDT'},
					'THE': {'USDC', 'TRY', 'BTC', 'USDT'},
					'THETA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TIA': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TLM': {'USDC', 'TRY', 'USDT'},
					'TNSR': {'USDC', 'TRY', 'USDT'},
					'TON': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TRB': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TRU': {'TRY', 'BTC', 'USDT'},
					'TRUMP': {'USDC', 'TRY', 'USDT'},
					'TRX': {'USDC', 'TRY', 'BTC', 'USDT'},
					'TST': {'USDC', 'TRY', 'USDT'},
					'TURBO': {'USDC', 'TRY', 'USDT'},
					'TUT': {'USDC', 'USDT'},
					'TWT': {'TRY', 'USDT'},
					'UMA': {'TRY', 'BTC', 'USDT'},
					'UNI': {'USDC', 'TRY', 'BTC', 'USDT'},
					'USTC': {'TRY', 'USDT'},
					'USUAL': {'USDC', 'TRY', 'BTC', 'USDT'},
					'UTK': {'USDC', 'USDT'},
					'VANA': {'USDC', 'TRY', 'USDT'},
					'VANRY': {'USDC', 'TRY', 'USDT'},
					'VELODROME': {'USDC', 'USDT'},
					'VET': {'USDC', 'TRY', 'BTC', 'USDT'},
					'VIC': {'TRY', 'USDT'},
					'VIRTUAL': {'USDC', 'USDT'},
					'VOXEL': {'USDT'},
					'VTHO': {'TRY', 'USDT'},
					'W': {'USDC', 'TRY', 'BTC', 'USDT'},
					'WAN': {'BTC', 'USDT'},
					'WAXP': {'BTC', 'USDT'},
					'WBETH': {'USDT'},
					'WBTC': {'BTC', 'USDT'},
					'WCT': {'TRY', 'USDT', 'USDC'},
					'WIF': {'USDC', 'TRY', 'BTC', 'USDT'},
					'WLD': {'USDC', 'TRY', 'BTC', 'USDT'},
					'XAI': {'TRY', 'USDT'},
					'XEC': {'TRY', 'USDT'},
					'XLM': {'USDC', 'TRY', 'BTC', 'USDT'},
					'XNO': {'BTC', 'USDT'},
					'XRP': {'USDC', 'TRY', 'BTC', 'USDT'},
					'XTZ': {'USDC', 'BTC', 'USDT'},
					'XVG': {'TRY', 'USDT'},
					'XVS': {'TRY', 'BTC', 'USDT'},
					'YFI': {'BTC', 'USDT'},
					'YGG': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ZEC': {'BTC', 'USDT'},
					'ZEN': {'USDC', 'BTC', 'USDT'},
					'ZIL': {'TRY', 'BTC', 'USDT'},
					'ZK': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ZRO': {'USDC', 'TRY', 'BTC', 'USDT'},
					'ZRX': {'BTC', 'USDT'}}
	
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
		self.prices['BTCUSDT'] = [94000]
		self.prices['USDCTRY'] = [38.41]
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
		return np.full((360, len(self.COLUMN_MAPPING)), np.inf, dtype=np.float32)

	def get_ticker_index(self, ticker):
		if ticker not in self.ticker_mapping:
			self.ticker_mapping[ticker] = self.next_free_index
			self.next_free_index += 1

		return self.ticker_mapping[ticker]

	def detect_potential_pump(self, data):
		ticker = data['k']['s']
		if ticker in self.parameters.crypto_bought:
			return False
		row_idx = self.get_ticker_index(ticker)
		variation_m = self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", self.parameters.kline_type)]]
		variation_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", "1h")]]
		if self.parameters.limits['variation']*variation_m <= variation_1h:
			return False

		volume_m = self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", self.parameters.kline_type)]]
		volume_1h = self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", "1h")]]

		#print("Volume", volume_m, volume_1h, ticker)

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
				print("price lower")
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
			quantity = cash_used/self.prices['BTCUSDT'][-1]
		elif trading_ticker == 'TRY':
			quantity = cash_used*self.prices['USDCTRY'][-1]
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
		print('BUY ORDER')
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
		self.parameters.crypto_bought.append(original_pair)

	def manage_sell_limits_orders(self, data):
		#Possible de manage_sell a partir de mini ticker au lieu de take get_trading_pair
		k = data['k']
		ticker = k['s']
		trading_pair = self.get_trading_pair(ticker[:-4])
		pair = ticker[:-4]+trading_pair
		current_price = self.prices[pair][-1]
		now = datetime.datetime.fromtimestamp(int(data['E'])/1000)

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
		step_size = self.parameters.ticker_bought_actual_max_price[pair]['step_size']
		tick_size = self.parameters.ticker_bought_actual_max_price[pair]['tick_size']
		quantity = self.trading_manager.portfolio.actifs[pair]['quantity']
		quantity_step = quantity // step_size
		quantity_bought = str(round(quantity_step*step_size,8))

		if current_price > self.parameters.ticker_bought_actual_max_price[pair]['max_price'] and not self.z_score_hits:
			self.parameters.ticker_bought_actual_max_price[pair]['max_price'] = current_price

			scaled_price = self.parameters.stop_loss_prct * current_price
			price_step = scaled_price // tick_size
			new_stop_loss_price = round(price_step*tick_size,8)
			self.trading_manager.cancel_replace(pair, quantity_bought, new_stop_loss_price)
		elif current_z_score < threshold and self.max_z_score[ticker] > threshold:
			#Peut-être, récupérer la quantité du portfolio à la place de calculer la quantité achetée
			self.z_score_hits = True
			scaled_price = 0.995 * current_price
			price_step = scaled_price // tick_size
			new_stop_loss_price = round(price_step*tick_size,8)
			if self.parameters.ticker_bought_actual_max_price[pair]['current_stop_loss_price'] < new_stop_loss_price:
				print('SELLLLLLLL', pair, now, self.parameters.ticker_bought_actual_max_price[pair]['current_stop_loss_price'], new_stop_loss_price, current_price)
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

	def update_parameters(self, websocket_stream, k):

		pair = k['s']
		
		current_price = float(k['c'])
		if pair.endswith('USDT'):
			variation = float(k['h'])-float(k['l'])
			volume = float(k['v'])
			nb_of_trades = k['n']

			row_idx = self.get_ticker_index(pair)
			self.data_storage[row_idx, self.COLUMN_MAPPING[("Variation", websocket_stream)]] = variation
			self.data_storage[row_idx, self.COLUMN_MAPPING[("Volume", websocket_stream)]] = volume
			self.data_storage[row_idx, self.COLUMN_MAPPING[("NbOfTrades", websocket_stream)]] = nb_of_trades
			if websocket_stream == self.parameters.kline_type:
				price_is_going_up = bool(float(k['c']) > float(k['o']))
				self.data_storage[row_idx, self.COLUMN_MAPPING[("Price is going up", "")]] = price_is_going_up

		self.prices[pair].append(current_price)
		if len(self.prices[pair]) > max(self.parameters.mean_rolling_size, self.parameters.std_rolling_size):
			self.prices[pair].pop(0)
