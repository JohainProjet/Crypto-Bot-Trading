from abc import ABC


class Strategy(ABC):
    def __init__(self, duration_time, is_test_mode : str):
        self.duration_time = duration_time
        self.is_test_mode = is_test_mode
