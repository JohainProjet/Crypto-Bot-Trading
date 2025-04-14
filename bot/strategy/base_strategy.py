from abc import ABC


class Strategy(ABC):
    def __init__(self, duration_time):
        self.duration_time = duration_time
