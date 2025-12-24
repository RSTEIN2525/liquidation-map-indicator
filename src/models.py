from enum import Enum
from typing import Optional, List, Any
import pandas as pd
from pydantic import BaseModel, Field

class CacheStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    READY        = "READY"
    ERROR        = "ERROR"

class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

class Status(str, Enum):
    ACTIVE = "ACTIVE"
    CLEARED = "CLEARED"
    PARTIAL = "PARTIAL"

class Bias(str, Enum):
    UP       = "UP"
    DOWN     = "DOWN"
    UNBIASED = "UNBIASED"

class Entry(BaseModel):
    side: Side
    price: float
    weight: float
    start_time: Any = None
    end_time: Any = None

    class Config:
        arbitrary_types_allowed = True

class Liquidation(BaseModel):
    liq_price: float
    amnt_usd_liq: float
    side: str
    entry_start_time: Any = None

    class Config:
        arbitrary_types_allowed = True

class Direction(BaseModel):
    bias: Bias
    upward_mag: float
    downward_mag: float

class SummaryStats(BaseModel):
    total_oi_usd: float
    close: float
    funding_rate: float
    high: float
    low: float

class BinData(BaseModel):
    bucket: str
    usd: float
    mid_price: float
    intensity: float
    status: Status

class RawLiquidation(BaseModel):
    """Individual liquidation point for granular frontend visualization"""
    price: float
    usd: float
    side: str  # 'long' or 'short'
    status: Status
    entry_time: Optional[float] = None  # Unix timestamp

class LiquidationMapResponse(BaseModel):
    summary: SummaryStats
    direction: Direction
    bins: List[BinData]
    raw_liquidations: Optional[List[RawLiquidation]] = None
    timestamp: float


