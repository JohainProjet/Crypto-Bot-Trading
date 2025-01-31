from dataclasses import dataclass

@dataclass
class Kline:
    ticker: str
    open_time: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    close_time: int
    quote_asset_volume: float
    num_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float


@dataclass
class RollingWindow:
    ticker: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    num_trades: int