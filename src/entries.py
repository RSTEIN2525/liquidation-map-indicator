import ccxt
import pandas as pd
from typing import List, Any
from .config import WEIGHT_VOLUME_OI, WEIGHT_HOTZONE, WEIGHT_VWAP, VOL_MASK, DELTA_MASK, PRICE_MASK
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

def get_summary_stats(df: pd.DataFrame) -> dict:
    agg_df = aggregate_market_view(df)
    
    # SAFETY: Check if empty first
    if agg_df.empty:
        return {"cur_price": 0.0, "total_oi_usd": 0.0}

    # Get the LAST row (most recent timestamp)
    latest = agg_df.iloc[-1]

    return {
        "cur_price": latest['close'], 
        "total_oi_usd": latest['oi_usd_current']
    }

def aggregate_market_view(df: pd.DataFrame):
    agg_df = df.groupby('timestamp').agg({
        'close': 'mean',
        'volume': 'sum',       
        'volume_usd': 'sum',
        'oi_usd_hist': 'sum',
        'oi_usd_current': 'sum'
    }).reset_index()

    agg_df['oi_delta'] = agg_df['oi_usd_hist'].diff()
    agg_df['volume_delta'] = agg_df['volume'].diff()
    agg_df['price_return'] = agg_df['close'].pct_change()

    return agg_df


def detect_hotzones(df: pd.DataFrame) -> List[Entry]:

    # List of Entires
    entries: List[Entry] = []

    VOLUME_QUANTILE = df['volume_usd'].quantile(VOL_MASK)  # top 20% volume
    PRICE_THRESHOLD = PRICE_MASK  # 0.8% move
    OI_DELTA_QUANTILE = df['oi_delta'].abs().quantile(DELTA_MASK)  # top 30% move

    # Masks for a likely long entry
    long_conditions = (
        (df['price_return'] > PRICE_THRESHOLD) &
        (df['oi_delta'] > OI_DELTA_QUANTILE) &
        (df['volume_usd'] > VOLUME_QUANTILE))

    # Masks for a likely short entry
    short_conditions = (
        (df['price_return'] < -PRICE_THRESHOLD) &   # price DOWN
        # OI still INCREASING (new shorts)
        (df['oi_delta'] > OI_DELTA_QUANTILE) &
        (df['volume_usd'] > VOLUME_QUANTILE))

    # Group For Consecutive True Long Periods
    df['long_group'] = (long_conditions != long_conditions.shift()).cumsum()
    hot_long_periods = df[long_conditions].groupby('long_group')

    # Append Longs
    for _, long_period in hot_long_periods:

        entry_price = (
            long_period['close'] * long_period['volume']).sum() / long_period['volume'].sum()
        raw_weight = max(long_period['oi_delta'].sum(), 0)
        entries.append(
            Entry(side=Side.LONG, price=entry_price, weight=raw_weight))

    # Group For Consecutive True Short Periods
    df['short_group'] = (short_conditions != short_conditions.shift()).cumsum()
    hot_short_periods = df[short_conditions].groupby('short_group')

    # Append Shorts
    for _, short_period in hot_short_periods:

        entry_price = (
            short_period['close'] * short_period['volume']).sum() / short_period['volume'].sum()
        raw_weight = max(short_period['oi_delta'].sum(), 0)
        entries.append(
            Entry(side=Side.SHORT, price=entry_price, weight=raw_weight))

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
    df.drop(columns=['long_group', 'short_group'],
            errors='ignore', inplace=True)

    return entries


# TLDR: Hotzones LITE; Huge Move, W/ VOL to backup but OI Unphased -- Lower Sig. But Lev. Def Adj
def detect_high_vol_and_oi_spike(df: pd.DataFrame) -> List[Entry]:

    # List of Entires
    entries: List[Entry] = []

    VOLUME_QUANTILE = df['volume_usd'].quantile(VOL_MASK)  # top 20% volume
    PRICE_THRESHOLD = PRICE_MASK  # 1% move

    # Masks for a likely long entry
    long_conditions = (
        (df['price_return'] > PRICE_THRESHOLD) &  # Price UP
        (df['volume_usd'] > VOLUME_QUANTILE))    # In VOL Bracked (>= 20%)

    # Masks for a likely short entry
    short_conditions = (
        (df['price_return'] < -PRICE_THRESHOLD) &  # price DOWN
        (df['volume_usd'] > VOLUME_QUANTILE))     # In VOL Bracked (>= 20%)

    # Group For Consecutive True Long Periods
    df['long_group'] = (long_conditions != long_conditions.shift()).cumsum()
    hot_long_periods = df[long_conditions].groupby('long_group')

    # Append Longs
    for _, long_period in hot_long_periods:

        entry_price = (
            long_period['close'] * long_period['volume']).sum() / long_period['volume'].sum()
        raw_weight = max(long_period['volume_usd'].sum(), 0)
        entries.append(
            Entry(side=Side.LONG, price=entry_price, weight=raw_weight))

    # Group For Consecutive True Short Periods
    df['short_group'] = (short_conditions != short_conditions.shift()).cumsum()
    hot_short_periods = df[short_conditions].groupby('short_group')

    # Append Shorts
    for _, short_period in hot_short_periods:

        entry_price = (
            short_period['close'] * short_period['volume']).sum() / short_period['volume'].sum()
        raw_weight = max(short_period['volume_usd'].sum(), 0)
        entries.append(
            Entry(side=Side.SHORT, price=entry_price, weight=raw_weight))
    
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
    df.drop(columns=['long_group', 'short_group'],
            errors='ignore', inplace=True)

    return entries

# TODO: No Such Thing as Neutral Leverage always in {LONG< SHORT}, We could CMP w/ a MA as a trend Proxy, if broad +, LONG | if broad -, SHORT


def detect_vwap(df: pd.DataFrame) -> List[Entry]:

    # No Data Passed
    if df.empty:
        return []

    # For Each TF Close; Calculate Vol * Price; To Calc ~"Dollars Moved"
    df['candle_turnover'] = df['close'] * df['volume']

    # Aggregate All Candle Turnovers, and Divide by Total Volume to Vol. Weighted. Price
    vwap_price = df['candle_turnover'].sum() / df['volume'].sum()

    # Only One Entry, So 1.0 Weight
    return [Entry(side=Side.NEUTRAL, price=vwap_price, weight=1.0)]


def scale_entries(entries: List[Entry], method_weight: float):

    # Validate Entries Are Present
    if not entries:
        return []

    # Scale Raw Weights By method Weight

    # Sum Individual Entry Weights (Derrived From Open Interest Change -- DELTA)
    total_raw = sum(entry.weight for entry in entries)

    # Case total_raw 0
    if total_raw == 0:
        # Equal Weighting Calculated From Methodoly/#Entries
        equal = method_weight / len(entries)
        for entry in entries:
            entry.weight = equal  # Assigns Each; Equal Partital
    else:
        for entry in entries:  # Otherwise Just Re:Normalizes
            entry.weight = (entry.weight / total_raw) * method_weight

    return entries


def estimate_entries(input: pd.DataFrame) -> List[Entry]:

    # Aggregate DF by Timestamp, Rather than Exchange
    df = aggregate_market_view(input)

    # Master List Storing Entries; Built From Methodologies
    entry_book: List[Entry] = scale_entries(detect_hotzones(df), WEIGHT_HOTZONE) + \
        scale_entries(detect_high_vol_and_oi_spike(df), WEIGHT_VOLUME_OI) + \
        scale_entries(detect_vwap(df), WEIGHT_VWAP)

    # Safety Normalization
    total = sum(e.weight for e in entry_book)

    if total > 0:
        for e in entry_book:
            e.weight /= total

    return entry_book
