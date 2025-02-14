from abc import ABC


class Strategy(ABC):
    def __init__(self, durationTime, isTestMode : str):
        self.durationTime = durationTime
        self.isTestMode = isTestMode