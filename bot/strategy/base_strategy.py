from abc import abstractmethod
from binance.spot import Spot as Client
from config import get_api_keys

class Strategy:
    def __init__(self, durationTime, isTestMode : bool):
        self.durationTime = durationTime
        self.api_key, self.api_secret = get_api_keys(environnement=isTestMode)
        self.isTestMode = isTestMode

    @abstractmethod
    def start(self, portfolio):
        return