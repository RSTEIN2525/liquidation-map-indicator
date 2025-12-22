from enum import Enum
from dataclasses import dataclass
from typing import Optional
import pandas as pd

class Side(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

class Status(Enum):
    ACTIVE = "ACTIVE"
    CLEARED = "CLEARED"
    PARTIAL = "PARTIAL"

class Bias(Enum):
    UP       = "UP"
    DOWN     = "DOWN"
    UNBIASED = "UNBIASED"

@dataclass
class Entry:
    side: Side
    price: float
    weight: float
    start_time: pd.Timestamp = None
    end_time: pd.Timestamp = None

@dataclass
class Liquidation:
    liq_price: float
    amnt_usd_liq: float
    side: str
    entry_start_time: pd.Timestamp = None

@dataclass
class Direction:
    bias: Bias
    upward_mag: float
    downward_mag: float

@dataclass
class SummaryStats:
    total_oi_usd: float
    close: float
    funding_rate: float
    high: float
    low: float

