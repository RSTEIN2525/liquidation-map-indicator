import ccxt
import pandas as pd
from typing import List, Any
from .config import WEIGHT_VOLUME_OI, WEIGHT_HOTZONE, WEIGHT_VWAP
from dataclasses import dataclass
from enum import Enum
import math


class Side(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

@dataclass
class Entry:
    side: Side
    price: float  
    weight: float

'''
WE USE THREE PROXIES TO GUAGE ENTRY:
-> OI + Price Direction Correlation; When Prices Moves Up Sig, and OI Increases (LONGS); OPPOSITE applies for SHORTS
-> HIGH_VOL + OI Spikes; high trading volume with OI increase implies that position is opening UP
-> VWAP: Used in choppy markets without a clear trend that would Implie LONG || SHORT
'''

def aggregate_market_view(df: pd.DataFrame):
    agg_df = df.groupby('timestamp').agg({
        'close' : 'mean',
        'volume': 'sum',        # <--- Add this line!
        'volume_usd' : 'sum',
        'oi_usd_hist' : 'sum',
        'oi_usd_current' : 'sum'
    }).reset_index()

    agg_df['oi_delta'] = agg_df['oi_usd_hist'].diff()
    agg_df['price_return'] = agg_df['close'].pct_change()

    return agg_df

def detect_hotzones(df: pd.DataFrame)->List[Entry]:

    # List of Entires
    entries:List[Entry] = []

    VOLUME_QUANTILE = df['volume_usd'].quantile(0.8)  # top 20% volume
    PRICE_THRESHOLD = 0.005  # 0.5% move
    OI_DELTA_QUANTILE = df['oi_delta'].abs().quantile(0.7) # top 30% move

    # Masks for a likely long entry
    long_conditions = (
    (df['price_return'] > PRICE_THRESHOLD) &
    (df['oi_delta'] > OI_DELTA_QUANTILE) &
    (df['volume_usd'] > VOLUME_QUANTILE))
    
    # Masks for a likely short entry
    short_conditions = (
    (df['price_return'] < -PRICE_THRESHOLD) &   # price DOWN
    (df['oi_delta'] > OI_DELTA_QUANTILE) &      # OI still INCREASING (new shorts)
    (df['volume_usd'] > VOLUME_QUANTILE))

    # Group For Consecutive True Long Periods
    df['long_group'] = (long_conditions != long_conditions.shift()).cumsum()
    hot_long_periods = df[long_conditions].groupby('long_group')

    # Append Longs
    for _, long_period in hot_long_periods:

        entry_price = (long_period['close'] * long_period['volume']).sum() / long_period['volume'].sum()       
        raw_weight = max(long_period['oi_delta'].sum(), 0)
        entries.append(Entry(side=Side.LONG, price=entry_price, weight=raw_weight))
    
    # Group For Consecutive True Short Periods
    df['short_group'] = (short_conditions != short_conditions.shift()).cumsum()
    hot_short_periods = df[short_conditions].groupby('short_group')

    # Append Shorts
    for _, short_period in hot_short_periods:
        
        entry_price = (short_period['close'] * short_period['volume']).sum() / short_period['volume'].sum()
        raw_weight = max(short_period['oi_delta'].sum(), 0)
        entries.append(Entry(side=Side.SHORT, price=entry_price, weight=raw_weight))
    
    # Normalize
    if entries:
        total_weight = sum(e.weight for e in entries)
        if total_weight > 0:
            for e in entries:
                e.weight /= total_weight
        else:
            # fallback: equal weight
            equal_w = 1.0 / len(entries)
            for e in entries:
                e.weight = equal_w

    # Clean Up Columns
    df.drop(columns=['long_group', 'short_group'], errors='ignore', inplace=True)
    
    return entries

def detect_high_vol_and_oi_spike(df: pd.DataFrame)->List[Entry] :
    return []

def detect_vwap(df: pd.DataFrame)->List[Entry] :
    return []

def estimate_entries(input: pd.DataFrame) -> List[Entry]:

    # Aggregate DF by Timestamp, Rather than Exchange
    df = aggregate_market_view(input)

    # Master List Storing Entries; Built From Methodologies
    entry_book: List[Entry] = detect_hotzones(df)  + detect_high_vol_and_oi_spike(df) +detect_vwap(df)

    return entry_book







    